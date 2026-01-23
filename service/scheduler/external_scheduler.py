"""
External Scheduler for job graph processing.

Coordinates the execution of job sequences by:
1. Reading sequence definitions from JSON files
2. Sending jobs to the incoming queue based on dependencies
3. Monitoring the outgoing queue for completed jobs
4. Triggering next jobs in the sequence when dependencies are met
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger

from constants import SCHEDULER_CONFIG
from service.models.aircraft_daily_sequence_dto import DailySequenceDto
from service.models.job import AggregationJob, CompletedJob, ExecType, IncomingJob

logger = Logger(service="ExternalScheduler")


class ExternalScheduler:
    """
    External scheduler that orchestrates job graph execution.

    Manages the flow of jobs through the system:
    - Sends initial jobs to incoming queue
    - Polls outgoing queue for completed jobs
    - Determines next jobs to run based on completion status
    - Handles aggregation and final notifications
    """

    def __init__(
        self,
        incoming_queue_url: str,
        outgoing_queue_url: str,
        sequences_dir: str = SCHEDULER_CONFIG["sequences_directory"],  # will be S3 later on
        poll_interval: int = SCHEDULER_CONFIG["job_wait_time_seconds"],  # Use configured visibility timeout
    ):
        """
        Initialize the scheduler.

        Args:
            incoming_queue_url: URL of the SQS queue for jobs to process
            outgoing_queue_url: URL of the SQS queue for completed jobs
            sequences_dir: Directory containing sequence JSON files
            poll_interval: Seconds to wait between polling outgoing queue
        """
        self.incoming_queue_url = incoming_queue_url
        self.outgoing_queue_url = outgoing_queue_url
        self.sequences_dir = Path(sequences_dir)
        self.poll_interval = poll_interval

        self.sqs = boto3.client("sqs")

        # Track active sequences: correlation_id -> sequence state
        self.active_sequences: dict[str, dict[str, Any]] = {}

    def load_sequences(self) -> list[DailySequenceDto]:
        """Load all sequence definitions from JSON files."""
        sequences = []

        if not self.sequences_dir.exists():
            logger.warning(f"Sequences directory not found: {self.sequences_dir}")
            return sequences

        for json_file in sorted(self.sequences_dir.glob("*.json")):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    sequence = DailySequenceDto(**data)
                    sequences.append(sequence)
                    logger.info(f"Loaded sequence {sequence.sequence_id} from {json_file.name}")
            except Exception as e:
                logger.error(f"Failed to load sequence from {json_file}: {e}")

        return sequences

    def start_sequence(self, sequence: DailySequenceDto) -> str:
        """
        Start processing a sequence by sending the first job.

        Args:
            sequence: The sequence to process

        Returns:
            correlation_id for tracking this sequence execution
        """
        correlation_id = str(uuid.uuid4())

        # Initialize sequence state
        self.active_sequences[correlation_id] = {
            "sequence_id": sequence.sequence_id,
            "home_airport_iata": sequence.home_airport_iata,
            "total_routes": len(sequence.routes),
            "current_route_index": 0,
            "routes": [route.model_dump() for route in sequence.routes],
            "started_at": time.time(),
        }

        # Send first job
        self._send_job(
            correlation_id=correlation_id,
            sequence_id=sequence.sequence_id,
            exec_type=ExecType.FIRST,
            route_index=0,
            route_data=sequence.routes[0].model_dump(),
            home_airport_iata=sequence.home_airport_iata,
            total_routes=len(sequence.routes),
        )

        logger.info(
            f"Started sequence {sequence.sequence_id} with correlation_id {correlation_id}",
            extra={
                "correlation_id": correlation_id,
                "sequence_id": sequence.sequence_id,
                "total_routes": len(sequence.routes),
            },
        )

        return correlation_id

    def _send_job(
        self,
        correlation_id: str,
        sequence_id: int,
        exec_type: ExecType,
        route_index: int,
        route_data: dict[str, Any],
        home_airport_iata: str,
        total_routes: int,
    ) -> None:
        """Send a job to the incoming queue."""
        job = IncomingJob(
            correlation_id=correlation_id,
            sequence_id=sequence_id,
            exec_type=exec_type,
            route_index=route_index,
            route_data=route_data,
            home_airport_iata=home_airport_iata,
            total_routes=total_routes,
        )

        self.sqs.send_message(
            QueueUrl=self.incoming_queue_url,
            MessageBody=job.model_dump_json(),
        )

        logger.info(
            "Sent job to incoming queue",
            extra={
                "correlation_id": correlation_id,
                "exec_type": exec_type.value,
                "route_index": route_index,
            },
        )

    def _send_aggregation_job(
        self,
        correlation_id: str,
        sequence_id: int,
        total_routes: int,
        home_airport_iata: str,
    ) -> None:
        """Send an aggregation job to the incoming queue."""
        agg_job = AggregationJob(
            correlation_id=correlation_id,
            sequence_id=sequence_id,
            total_routes=total_routes,
            home_airport_iata=home_airport_iata,
        )

        self.sqs.send_message(
            QueueUrl=self.incoming_queue_url,
            MessageBody=agg_job.model_dump_json(),
        )

        logger.info(
            "Sent aggregation job",
            extra={"correlation_id": correlation_id, "sequence_id": sequence_id},
        )

    def process_completed_job(self, completed_job: CompletedJob) -> None:
        """
        Process a completed job and determine next action.

        Args:
            completed_job: The completed job from outgoing queue
        """
        correlation_id = completed_job.correlation_id

        if correlation_id not in self.active_sequences:
            logger.warning(f"Received completed job for unknown correlation_id: {correlation_id}")
            return

        sequence_state = self.active_sequences[correlation_id]

        if completed_job.status != "success":
            logger.error(
                f"Job failed: {completed_job.error_message}",
                extra={
                    "correlation_id": correlation_id,
                    "exec_type": completed_job.exec_type.value,
                    "route_index": completed_job.route_index,
                },
            )
            # Could implement retry logic here
            return

        logger.info(
            "Processing completed job",
            extra={
                "correlation_id": correlation_id,
                "exec_type": completed_job.exec_type.value,
                "route_index": completed_job.route_index,
                "processing_time_ms": completed_job.processing_time_ms,
            },
        )

        # Determine next action based on exec_type
        if completed_job.exec_type in [ExecType.FIRST, ExecType.INTERMEDIATE]:
            # Send next route job
            next_route_index = completed_job.route_index + 1

            if next_route_index < sequence_state["total_routes"]:
                # Determine exec_type for next job
                is_last = next_route_index == sequence_state["total_routes"] - 1
                next_exec_type = ExecType.LAST if is_last else ExecType.INTERMEDIATE

                self._send_job(
                    correlation_id=correlation_id,
                    sequence_id=sequence_state["sequence_id"],
                    exec_type=next_exec_type,
                    route_index=next_route_index,
                    route_data=sequence_state["routes"][next_route_index],
                    home_airport_iata=sequence_state["home_airport_iata"],
                    total_routes=sequence_state["total_routes"],
                )

                sequence_state["current_route_index"] = next_route_index

        elif completed_job.exec_type == ExecType.LAST:
            # All routes completed, send aggregation job
            self._send_aggregation_job(
                correlation_id=correlation_id,
                sequence_id=sequence_state["sequence_id"],
                total_routes=sequence_state["total_routes"],
                home_airport_iata=sequence_state["home_airport_iata"],
            )

        elif completed_job.exec_type == ExecType.AGGREGATION:
            # Final step - sequence complete
            elapsed = time.time() - sequence_state["started_at"]
            logger.info(
                "Sequence completed",
                extra={
                    "correlation_id": correlation_id,
                    "sequence_id": sequence_state["sequence_id"],
                    "total_routes": sequence_state["total_routes"],
                    "elapsed_seconds": elapsed,
                },
            )

            # Remove from active sequences
            del self.active_sequences[correlation_id]

            # Could trigger notification or next orchestration step here
            logger.info(f"Sequence {sequence_state['sequence_id']} orchestration complete")

    def poll_outgoing_queue(self) -> None:
        """Poll the outgoing queue for completed jobs."""
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.outgoing_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,  # Long polling
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            for message in messages:
                try:
                    body = json.loads(message["Body"])
                    completed_job = CompletedJob(**body)

                    self.process_completed_job(completed_job)

                    # Delete message after successful processing
                    self.sqs.delete_message(
                        QueueUrl=self.outgoing_queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )

                except Exception as e:
                    logger.error(f"Error processing completed job: {e}", exc_info=True)
                    # Message will remain in queue for retry

        except Exception as e:
            logger.error(f"Error polling outgoing queue: {e}", exc_info=True)

    def run(self, max_iterations: int | None = None) -> None:
        """
        Run the scheduler.

        Args:
            max_iterations: Maximum number of poll iterations (None = infinite)
        """
        # Load and start all sequences
        sequences = self.load_sequences()

        if not sequences:
            logger.warning("No sequences found to process")
            return

        logger.info(f"Starting {len(sequences)} sequences")

        for sequence in sequences:
            self.start_sequence(sequence)

        # Poll for completed jobs
        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            if not self.active_sequences:
                logger.info("All sequences completed")
                break

            logger.info(f"Polling outgoing queue (active sequences: {len(self.active_sequences)})")
            self.poll_outgoing_queue()

            iteration += 1
            time.sleep(self.poll_interval)

        if self.active_sequences:
            logger.warning(f"Scheduler stopped with {len(self.active_sequences)} active sequences")

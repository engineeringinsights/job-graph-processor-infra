import json
import time
import uuid
from pathlib import Path
from typing import Any

from aws_lambda_powertools import Logger

from service.dal.sqs_jobs import SqsJobsDataAccess
from service.models.aircraft_daily_sequence_dto import DailySequenceDto
from service.models.job import AggregationJob, CompletedJob, ExecType, IncomingJob

logger = Logger(service="ExternalScheduler")


class ExternalScheduler:
    def __init__(
        self,
        sqs_data_access: SqsJobsDataAccess,
        sequences_dir: str = "sequences",
        poll_interval: int = 5,
    ):
        self.sqs_data_access = sqs_data_access
        self.sequences_dir = Path(sequences_dir)
        self.poll_interval = poll_interval

        # Track active sequences: correlation_id -> sequence state
        self.active_sequences: dict[str, dict[str, Any]] = {}

    def load_sequences(self) -> list[DailySequenceDto]:
        sequences: list[DailySequenceDto] = []

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
        job = IncomingJob(
            correlation_id=correlation_id,
            sequence_id=sequence_id,
            exec_type=exec_type,
            route_index=route_index,
            route_data=route_data,
            home_airport_iata=home_airport_iata,
            total_routes=total_routes,
        )

        self.sqs_data_access.add_todo_job(job)

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
        agg_job = AggregationJob(
            correlation_id=correlation_id,
            sequence_id=sequence_id,
            total_routes=total_routes,
            home_airport_iata=home_airport_iata,
        )

        # Create IncomingJob from AggregationJob for consistent interface
        incoming_job = IncomingJob(
            correlation_id=agg_job.correlation_id,
            sequence_id=agg_job.sequence_id,
            exec_type=agg_job.exec_type,
            route_index=-1,  # N/A for aggregation
            route_data={},  # No route data for aggregation
            home_airport_iata=agg_job.home_airport_iata,
            total_routes=agg_job.total_routes,
        )

        self.sqs_data_access.add_todo_job(incoming_job)

        logger.info(
            "Sent aggregation job",
            extra={"correlation_id": correlation_id, "sequence_id": sequence_id},
        )

    def process_completed_job(self, completed_job: CompletedJob) -> None:
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
        try:
            messages = self.sqs_data_access.read_completed_job(
                max_messages=10,
                wait_time_seconds=20,
            )

            for message in messages:
                try:
                    completed_job = CompletedJob(**json.loads(message["Body"]))

                    self.process_completed_job(completed_job)

                    # Delete message after successful processing
                    self.sqs_data_access.delete_message(
                        queue_url=self.sqs_data_access.outgoing_queue_url,
                        receipt_handle=message["ReceiptHandle"],
                    )

                except Exception as e:
                    logger.error(f"Error processing completed job: {e}", exc_info=True)
                    # Message will remain in queue for retry

        except Exception as e:
            logger.error(f"Error polling outgoing queue: {e}", exc_info=True)

    def run(self, max_iterations: int | None = None) -> None:
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

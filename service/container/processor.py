"""
ECS Fargate container entrypoint for job graph processing.

Polls SQS queue for messages and processes them continuously.

Key behaviors:
- Long-polls SQS queue for messages
- Processes messages in batches
- Runs until SIGTERM (manual scale-down)
- Handles SIGTERM for graceful shutdown
"""

import json
import os
import signal
import sys
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)

# Configuration from environment
INCOMING_QUEUE_URL = os.environ["INCOMING_QUEUE_URL"]
OUTGOING_QUEUE_URL = os.environ["OUTGOING_QUEUE_URL"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
TABLE_NAME = os.environ["TABLE_NAME"]
TEST_RUN_ID = os.environ.get("TEST_RUN_ID", "default")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
WAIT_TIME_SECONDS = 20  # SQS long polling (max 20s)

# AWS clients
sqs_client = boto3.client("sqs")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


class GracefulShutdown:
    """Handle graceful shutdown on SIGTERM."""

    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    def _handle_sigterm(self, signum, frame):
        logger.info("Shutdown signal received", signal=signum)
        self.shutdown_requested = True


def process_job(job_data: dict[str, Any]) -> dict[str, Any]:
    """
    Process a job and return results.

    Simulates work with configurable complexity for performance testing.
    """
    start_time = time.perf_counter()

    # Simulate work based on job configuration
    work_duration_ms = job_data.get("work_duration_ms", 100)
    data_size_kb = job_data.get("data_size_kb", 10)

    # Simulate CPU work
    if work_duration_ms > 0:
        time.sleep(work_duration_ms / 1000)

    # Generate result data
    result = {
        "job_id": job_data.get("job_id", str(uuid.uuid4())),
        "test_run_id": TEST_RUN_ID,
        "processed_at": datetime.now(UTC).isoformat(),
        "work_duration_ms": work_duration_ms,
        "result_data": "x" * (data_size_kb * 1024),
        "processor": "ecs-fargate",
    }

    processing_time_ms = (time.perf_counter() - start_time) * 1000
    result["actual_processing_time_ms"] = processing_time_ms

    return result


def process_message(message: dict[str, Any]) -> bool:
    """
    Process a single SQS message.

    Returns True if successful, False otherwise.
    """
    message_id = message["MessageId"]
    receipt_handle = message["ReceiptHandle"]

    try:
        job_data = json.loads(message["Body"])
        job_id = job_data.get("job_id", str(uuid.uuid4()))

        logger.info("Processing job", job_id=job_id, message_id=message_id)

        # Process the job
        result = process_job(job_data)

        # Write output to S3
        timestamp = datetime.now(UTC).strftime("%Y/%m/%d/%H")
        output_key = f"output/{timestamp}/{job_id}.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(result),
            ContentType="application/json",
        )

        # Send completion notification to outgoing queue
        completion_message = {
            "job_id": job_id,
            "status": "completed",
            "output_key": output_key,
            "processing_time_ms": result["actual_processing_time_ms"],
            "completed_at": datetime.now(UTC).isoformat(),
            "test_run_id": TEST_RUN_ID,
            "processor": "ecs-fargate",
        }
        sqs_client.send_message(
            QueueUrl=OUTGOING_QUEUE_URL,
            MessageBody=json.dumps(completion_message),
        )

        # Delete message from queue (acknowledge successful processing)
        sqs_client.delete_message(
            QueueUrl=INCOMING_QUEUE_URL,
            ReceiptHandle=receipt_handle,
        )

        logger.info(
            "Job completed",
            job_id=job_id,
            processing_time_ms=result["actual_processing_time_ms"],
            output_key=output_key,
        )
        return True

    except json.JSONDecodeError as e:
        logger.error("Failed to parse message body", message_id=message_id, error=str(e))
        return False
    except Exception as e:
        logger.error("Failed to process message", message_id=message_id, error=str(e))
        return False


def poll_queue(shutdown: GracefulShutdown) -> int:
    """
    Poll the SQS queue for messages.

    Returns the number of messages processed.
    """
    try:
        response = sqs_client.receive_message(
            QueueUrl=INCOMING_QUEUE_URL,
            MaxNumberOfMessages=BATCH_SIZE,
            WaitTimeSeconds=WAIT_TIME_SECONDS,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
    except Exception as e:
        logger.error("Failed to receive messages", error=str(e))
        return 0

    messages = response.get("Messages", [])

    if not messages:
        return 0

    logger.info("Received messages", count=len(messages))

    processed_count = 0
    for message in messages:
        if shutdown.shutdown_requested:
            logger.info("Shutdown requested, stopping message processing")
            break

        if process_message(message):
            processed_count += 1

    return processed_count


def main():
    """Main entry point for ECS processor."""
    logger.info(
        "Starting ECS processor",
        test_run_id=TEST_RUN_ID,
        batch_size=BATCH_SIZE,
        incoming_queue_url=INCOMING_QUEUE_URL,
    )

    shutdown = GracefulShutdown()
    total_processed = 0

    while not shutdown.shutdown_requested:
        messages_processed = poll_queue(shutdown)
        total_processed += messages_processed

        if messages_processed > 0:
            logger.info("Batch completed", messages_processed=messages_processed, total_processed=total_processed)
        else:
            logger.debug("No messages received, waiting for next poll")

    logger.info(
        "ECS processor shutting down",
        total_processed=total_processed,
        shutdown_requested=shutdown.shutdown_requested,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()

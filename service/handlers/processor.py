"""
Lambda handler for job graph processor.

Processes jobs from incoming queue:
1. Reads job details from S3 (if provided)
2. Performs the job work
3. Writes results to S3
4. Sends completion notification to outgoing queue
"""

import json
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.batch import (
    BatchProcessor,
    EventType,
    process_partial_response,
)
from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext

from service.dal.s3 import S3Handler
from service.dal.sqs import SQSHandler

logger = Logger()
tracer = Tracer()
metrics = Metrics()

processor = BatchProcessor(event_type=EventType.SQS)

BUCKET_NAME = os.environ["BUCKET_NAME"]
OUTGOING_QUEUE_URL = os.environ["OUTGOING_QUEUE_URL"]
TEST_RUN_ID = os.environ.get("TEST_RUN_ID", "default")

# Initialize handlers
s3_handler = S3Handler(BUCKET_NAME)
sqs_handler = SQSHandler(OUTGOING_QUEUE_URL)


@tracer.capture_method
def process_job(
    job_data: dict[str, Any], input_data: dict[str, Any] | None
) -> dict[str, Any]:
    """
    Process a job and return results.

    Simulates work with configurable complexity for performance testing.

    Args:
        job_data: Job configuration from SQS message
        input_data: Optional input data from S3

    Returns:
        Processing results
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
        "input_data_size": len(json.dumps(input_data)) if input_data else 0,
        "result_data": "x" * (data_size_kb * 1024),  # Generate data of specified size
    }

    processing_time_ms = (time.perf_counter() - start_time) * 1000
    result["actual_processing_time_ms"] = processing_time_ms

    return result


@tracer.capture_method
def record_handler(record: SQSRecord) -> None:
    """
    Process a single SQS record (job from incoming queue).

    Args:
        record: SQS record containing job to process
    """
    start_time = time.perf_counter()

    # Parse message body
    try:
        job_data = json.loads(record.body)
    except json.JSONDecodeError:
        logger.error("Failed to parse message body", extra={"body": record.body})
        raise

    job_id = job_data.get("job_id", str(uuid.uuid4()))
    logger.info("Processing job", extra={"job_id": job_id})

    # Read job details from S3 if specified
    input_key = job_data.get("input_key")
    input_data = s3_handler.read_json(input_key) if input_key else None

    # Process the job
    result = process_job(job_data, input_data)

    # Write output to S3
    timestamp = datetime.now(UTC).strftime("%Y/%m/%d/%H")
    output_key = f"output/{timestamp}/{job_id}.json"
    s3_handler.write_json(output_key, result)

    # Send completion notification to outgoing queue
    completion_message = {
        "job_id": job_id,
        "status": "completed",
        "output_key": output_key,
        "processing_time_ms": result["actual_processing_time_ms"],
        "completed_at": datetime.now(UTC).isoformat(),
        "test_run_id": TEST_RUN_ID,
    }
    sqs_handler.send_message(completion_message)

    # Record metrics
    processing_time_ms = (time.perf_counter() - start_time) * 1000
    metrics.add_metric(
        name="ProcessingTimeMs", unit=MetricUnit.Milliseconds, value=processing_time_ms
    )
    metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)

    logger.info(
        "Job completed and sent to outgoing queue",
        extra={
            "job_id": job_id,
            "processing_time_ms": processing_time_ms,
            "output_key": output_key,
        },
    )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(
    event: dict[str, Any], context: LambdaContext
) -> PartialItemFailureResponse:
    """
    Lambda handler for processing SQS messages.

    Uses batch processing with partial failure support.

    Args:
        event: SQS event containing batch of messages
        context: Lambda context

    Returns:
        Partial batch response indicating failed items
    """
    # Add test run dimension to all metrics for cost/perf tracking
    metrics.add_dimension(name="TestRunId", value=TEST_RUN_ID)

    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,
    )

import json
import os
import time
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

from service.dal.dynamodb import DynamoDBHandler
from service.dal.sqs import SQSHandler
from service.models.job import CompletedJob, ExecType, IncomingJob

logger = Logger()
tracer = Tracer()
metrics = Metrics()

processor = BatchProcessor(event_type=EventType.SQS)

BUCKET_NAME = os.environ["BUCKET_NAME"]
TABLE_NAME = os.environ["TABLE_NAME"]
OUTGOING_QUEUE_URL = os.environ["OUTGOING_QUEUE_URL"]
TEST_RUN_ID = os.environ.get("TEST_RUN_ID", "default")

# Initialize handlers
# s3_handler = S3Handler(BUCKET_NAME)
sqs_handler = SQSHandler(OUTGOING_QUEUE_URL)
dynamodb_handler = DynamoDBHandler(TABLE_NAME)


# def get_s3_state_key(correlation_id: str) -> str:
#     """Generate S3 key for storing sequence state."""
#     return f"state/{correlation_id}/route_results.json"


@tracer.capture_method
def process_first_airport(
    job: IncomingJob,
) -> dict[str, Any]:
    logger.info(
        "Processing first airport",
        extra={
            "correlation_id": job.correlation_id,
            "route_index": job.route_index,
            "route": job.route_data,
        },
    )

    # Initialize state with first route result
    state = {
        "correlation_id": job.correlation_id,
        "sequence_id": job.sequence_id,
        "home_airport_iata": job.home_airport_iata,
        "total_routes": job.total_routes,
        "route_results": [
            {
                "route_index": job.route_index,
                "route_data": job.route_data,
                "processed_at": datetime.now(UTC).isoformat(),
                # Add actual processing logic here
                "delay_minutes": 0,  # Placeholder
                "status": "completed",
            }
        ],
    }

    return state


@tracer.capture_method
def process_intermediate_airport(
    job: IncomingJob,
    previous_state: dict[str, Any],
) -> dict[str, Any]:
    logger.info(
        "Processing intermediate airport",
        extra={
            "correlation_id": job.correlation_id,
            "route_index": job.route_index,
            "route": job.route_data,
        },
    )

    # Add new route result to existing state
    route_result = {
        "route_index": job.route_index,
        "route_data": job.route_data,
        "processed_at": datetime.now(UTC).isoformat(),
        # Add actual processing logic here
        "delay_minutes": 0,  # Placeholder
        "status": "completed",
    }

    previous_state["route_results"].append(route_result)

    return previous_state


@tracer.capture_method
def process_last_airport(
    job: IncomingJob,
    previous_state: dict[str, Any],
) -> dict[str, Any]:
    logger.info(
        "Processing last airport",
        extra={
            "correlation_id": job.correlation_id,
            "route_index": job.route_index,
            "route": job.route_data,
        },
    )

    # Validate return to home
    if job.route_data.get("destination_iata") != job.home_airport_iata:
        logger.warning(
            "Last route does not return to home airport",
            extra={
                "expected": job.home_airport_iata,
                "actual": job.route_data.get("destination_iata"),
            },
        )

    # Add final route result
    route_result = {
        "route_index": job.route_index,
        "route_data": job.route_data,
        "processed_at": datetime.now(UTC).isoformat(),
        # Add actual processing logic here
        "delay_minutes": 0,  # Placeholder
        "status": "completed",
    }

    previous_state["route_results"].append(route_result)
    previous_state["completed_at"] = datetime.now(UTC).isoformat()

    return previous_state


@tracer.capture_method
def process_aggregation(
    correlation_id: str,
    sequence_id: int,
) -> dict[str, Any]:
    logger.info(
        "Processing aggregation",
        extra={"correlation_id": correlation_id, "sequence_id": sequence_id},
    )

    # Redo this logic to SQS instead of S3
    # state_key = get_s3_state_key(correlation_id)
    state = None

    if not state:
        raise ValueError(f"No state found for correlation_id: {correlation_id}")

    # Perform aggregation
    total_delay = sum(route.get("delay_minutes", 0) for route in state.get("route_results", []))
    total_routes = len(state.get("route_results", []))

    aggregation_result = {
        "correlation_id": correlation_id,
        "sequence_id": sequence_id,
        "total_routes": total_routes,
        "total_delay_minutes": total_delay,
        "average_delay_minutes": total_delay / total_routes if total_routes > 0 else 0,
        "home_airport_iata": state.get("home_airport_iata"),
        "started_at": state["route_results"][0]["processed_at"],
        "completed_at": state.get("completed_at"),
        "aggregated_at": datetime.now(UTC).isoformat(),
    }

    # Store in DynamoDB
    dynamodb_handler.put_item(
        {
            "pk": f"SEQUENCE#{sequence_id}",
            "sk": f"CORRELATION#{correlation_id}",
            **aggregation_result,
            "ttl": int(time.time()) + (30 * 24 * 60 * 60),  # 30 days TTL
        }
    )

    logger.info(
        "Aggregation completed and stored in DynamoDB",
        extra={
            "correlation_id": correlation_id,
            "total_delay_minutes": total_delay,
        },
    )

    return aggregation_result


@tracer.capture_method
def record_handler(record: SQSRecord) -> None:
    start_time = time.perf_counter()

    # Parse message body
    try:
        job_data = json.loads(record.body)
    except json.JSONDecodeError:
        logger.error("Failed to parse message body", extra={"body": record.body})
        raise

    # Check if this is an aggregation job (has exec_type field)
    exec_type_raw = job_data.get("exec_type")

    # Read job details from S3 if specified
    # input_key = job_data.get("input_key")
    # input_data = None  # s3_handler.read_json(input_key) if input_key else None
    if not exec_type_raw:
        # Legacy job format - process as before (for backwards compatibility)
        logger.warning("Received job without exec_type, treating as legacy format")
        raise ValueError("Legacy job format not supported in graph workflow")

    try:
        # Parse as IncomingJob
        if exec_type_raw == "aggregation":
            # Aggregation job
            correlation_id = job_data["correlation_id"]
            sequence_id = job_data["sequence_id"]

            # Write output to S3
            # timestamp = datetime.now(UTC).strftime("%Y/%m/%d/%H")
            # output_key = f"output/{timestamp}/{job_id}.json"
            # s3_handler.write_json(output_key, result)
            process_aggregation(correlation_id, sequence_id)

            # Send completion notification
            completed_job = CompletedJob(
                correlation_id=correlation_id,
                sequence_id=sequence_id,
                exec_type=ExecType.AGGREGATION,
                route_index=-1,  # N/A for aggregation
                status="success",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        else:
            # Regular route job
            job = IncomingJob(**job_data)

            logger.info(
                "Processing job",
                extra={
                    "correlation_id": job.correlation_id,
                    "exec_type": job.exec_type.value,
                    "route_index": job.route_index,
                },
            )

            # Get S3 state key
            # state_key = get_s3_state_key(job.correlation_id)

            # Process based on exec_type
            if job.exec_type == ExecType.FIRST:
                # No previous state needed
                process_first_airport(job)

            elif job.exec_type == ExecType.INTERMEDIATE:
                # Read previous state
                previous_state = None
                if not previous_state:
                    raise ValueError(f"No previous state found for correlation_id: {job.correlation_id}")
                process_intermediate_airport(job, previous_state)

            elif job.exec_type == ExecType.LAST:
                # Read previous state
                previous_state = None
                if not previous_state:
                    raise ValueError(f"No previous state found for correlation_id: {job.correlation_id}")
                process_last_airport(job, previous_state)

            else:
                raise ValueError(f"Unknown exec_type: {job.exec_type}")

            # Write updated state to S3
            # s3_handler.write_json(state_key, result)

            # Send completion notification
            completed_job = CompletedJob(
                correlation_id=job.correlation_id,
                sequence_id=job.sequence_id,
                exec_type=job.exec_type,
                route_index=job.route_index,
                status="success",
                processing_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Send to outgoing queue
        sqs_handler.send_message(completed_job.model_dump())

        # Record metrics
        processing_time_ms = (time.perf_counter() - start_time) * 1000
        metrics.add_metric(
            name="ProcessingTimeMs",
            unit=MetricUnit.Milliseconds,
            value=processing_time_ms,
        )
        metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)

        logger.info(
            "Job completed and sent to outgoing queue",
            extra={
                "correlation_id": completed_job.correlation_id,
                "exec_type": completed_job.exec_type.value,
                "processing_time_ms": processing_time_ms,
            },
        )

    except Exception as e:
        # Send error notification
        logger.error(f"Job processing failed: {e}", exc_info=True)

        error_job = CompletedJob(
            correlation_id=job_data.get("correlation_id", "unknown"),
            sequence_id=job_data.get("sequence_id", -1),
            exec_type=ExecType(exec_type_raw) if exec_type_raw else ExecType.FIRST,
            route_index=job_data.get("route_index", -1),
            status="error",
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
            error_message=str(e),
        )

        sqs_handler.send_message(error_job.model_dump())
        raise


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> PartialItemFailureResponse:
    # Add test run dimension to all metrics for cost/perf tracking
    metrics.add_dimension(name="TestRunId", value=TEST_RUN_ID)

    return process_partial_response(
        event=event,
        record_handler=record_handler,
        processor=processor,
        context=context,
    )


# """
# Lambda handler for job graph processor.

# Processes jobs from incoming queue:
# 1. Reads job details from S3 (if provided)
# 2. Performs the job work
# 3. Writes results to S3
# 4. Sends completion notification to outgoing queue
# """

# import json
# import os
# import time
# import uuid
# from datetime import UTC, datetime
# from typing import Any

# from aws_lambda_powertools import Logger, Metrics, Tracer
# from aws_lambda_powertools.metrics import MetricUnit
# from aws_lambda_powertools.utilities.batch import (
#     BatchProcessor,
#     EventType,
#     process_partial_response,
# )
# from aws_lambda_powertools.utilities.batch.types import PartialItemFailureResponse
# from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
# from aws_lambda_powertools.utilities.typing import LambdaContext

# from service.dal.s3 import S3Handler
# from service.dal.sqs import SQSHandler

# logger = Logger()
# tracer = Tracer()
# metrics = Metrics()

# processor = BatchProcessor(event_type=EventType.SQS)

# BUCKET_NAME = os.environ["BUCKET_NAME"]
# OUTGOING_QUEUE_URL = os.environ["OUTGOING_QUEUE_URL"]
# TEST_RUN_ID = os.environ.get("TEST_RUN_ID", "default")

# # Initialize handlers
# s3_handler = S3Handler(BUCKET_NAME)
# sqs_handler = SQSHandler(OUTGOING_QUEUE_URL)


# @tracer.capture_method
# def process_job(
#     job_data: dict[str, Any], input_data: dict[str, Any] | None
# ) -> dict[str, Any]:
#     """
#     Process a job and return results.

#     Simulates work with configurable complexity for performance testing.

#     Args:
#         job_data: Job configuration from SQS message
#         input_data: Optional input data from S3

#     Returns:
#         Processing results
#     """
#     start_time = time.perf_counter()

#     # Simulate work based on job configuration
#     work_duration_ms = job_data.get("work_duration_ms", 100)
#     data_size_kb = job_data.get("data_size_kb", 10)

#     # Simulate CPU work
#     if work_duration_ms > 0:
#         time.sleep(work_duration_ms / 1000)

#     # Generate result data
#     result = {
#         "job_id": job_data.get("job_id", str(uuid.uuid4())),
#         "test_run_id": TEST_RUN_ID,
#         "processed_at": datetime.now(UTC).isoformat(),
#         "work_duration_ms": work_duration_ms,
#         "input_data_size": len(json.dumps(input_data)) if input_data else 0,
#         "result_data": "x" * (data_size_kb * 1024),  # Generate data of specified size
#     }

#     processing_time_ms = (time.perf_counter() - start_time) * 1000
#     result["actual_processing_time_ms"] = processing_time_ms

#     return result


# @tracer.capture_method
# def record_handler(record: SQSRecord) -> None:
#     """
#     Process a single SQS record (job from incoming queue).

#     Args:
#         record: SQS record containing job to process
#     """
#     start_time = time.perf_counter()

#     # Parse message body
#     try:
#         job_data = json.loads(record.body)
#     except json.JSONDecodeError:
#         logger.error("Failed to parse message body", extra={"body": record.body})
#         raise

#     job_id = job_data.get("job_id", str(uuid.uuid4()))
#     logger.info("Processing job", extra={"job_id": job_id})

#     # Read job details from S3 if specified
#     input_key = job_data.get("input_key")
#     input_data = s3_handler.read_json(input_key) if input_key else None

#     # Process the job
#     result = process_job(job_data, input_data)

#     # Write output to S3
#     timestamp = datetime.now(UTC).strftime("%Y/%m/%d/%H")
#     output_key = f"output/{timestamp}/{job_id}.json"
#     s3_handler.write_json(output_key, result)

#     # Send completion notification to outgoing queue
#     completion_message = {
#         "job_id": job_id,
#         "status": "completed",
#         "output_key": output_key,
#         "processing_time_ms": result["actual_processing_time_ms"],
#         "completed_at": datetime.now(UTC).isoformat(),
#         "test_run_id": TEST_RUN_ID,
#     }
#     sqs_handler.send_message(completion_message)

#     # Record metrics
#     processing_time_ms = (time.perf_counter() - start_time) * 1000
#     metrics.add_metric(
#         name="ProcessingTimeMs", unit=MetricUnit.Milliseconds, value=processing_time_ms
#     )
#     metrics.add_metric(name="JobsCompleted", unit=MetricUnit.Count, value=1)

#     logger.info(
#         "Job completed and sent to outgoing queue",
#         extra={
#             "job_id": job_id,
#             "processing_time_ms": processing_time_ms,
#             "output_key": output_key,
#         },
#     )


# @logger.inject_lambda_context
# @tracer.capture_lambda_handler
# @metrics.log_metrics(capture_cold_start_metric=True)
# def handler(
#     event: dict[str, Any], context: LambdaContext
# ) -> PartialItemFailureResponse:
#     """
#     Lambda handler for processing SQS messages.

#     Uses batch processing with partial failure support.

#     Args:
#         event: SQS event containing batch of messages
#         context: Lambda context

#     Returns:
#         Partial batch response indicating failed items
#     """
#     # Add test run dimension to all metrics for cost/perf tracking
#     metrics.add_dimension(name="TestRunId", value=TEST_RUN_ID)

#     return process_partial_response(
#         event=event,
#         record_handler=record_handler,
#         processor=processor,
#         context=context,
#     )

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger

from service.models.job import CompletedJob, IncomingJob

logger = Logger()

# Initialize tracer with fallback for testing without aws-xray-sdk
try:
    from aws_lambda_powertools import Tracer

    tracer = Tracer(disabled=os.getenv("POWERTOOLS_TRACE_DISABLED", "false").lower() == "true")
except ImportError:
    # Create a no-op tracer for testing
    class NoOpTracer:
        def capture_method(self, func=None):
            return func if func else lambda f: f

    tracer = NoOpTracer()


class SqsJobsDataAccess:
    def __init__(self, incoming_queue_url: str, outgoing_queue_url: str) -> None:
        self.incoming_queue_url = incoming_queue_url
        self.outgoing_queue_url = outgoing_queue_url
        self.sqs = boto3.client("sqs")

    @tracer.capture_method
    def add_todo_job(self, job: IncomingJob) -> None:
        try:
            self.sqs.send_message(
                QueueUrl=self.incoming_queue_url,
                MessageBody=job.model_dump_json(),
            )
            logger.debug(
                "Added job to incoming queue",
                extra={
                    "correlation_id": job.correlation_id,
                    "exec_type": job.exec_type.value,
                    "route_index": job.route_index,
                },
            )
        except Exception as e:
            logger.error(
                f"Error adding job to incoming queue: {e}",
                extra={
                    "correlation_id": job.correlation_id,
                    "exec_type": job.exec_type.value,
                },
            )
            raise

    @tracer.capture_method
    def read_todo_job(self, max_messages: int = 1, wait_time_seconds: int = 20) -> list[dict[str, Any]]:
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.incoming_queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=["All"],
            )

            messages: list[dict[str, Any]] = response.get("Messages", [])
            logger.debug(
                f"Read {len(messages)} jobs from incoming queue",
                extra={"message_count": len(messages)},
            )
            return messages

        except Exception as e:
            logger.error(f"Error reading from incoming queue: {e}")
            raise

    @tracer.capture_method
    def add_completed_job(self, job: CompletedJob) -> None:
        try:
            self.sqs.send_message(
                QueueUrl=self.outgoing_queue_url,
                MessageBody=job.model_dump_json(),
            )
            logger.debug(
                "Added completed job to outgoing queue",
                extra={
                    "correlation_id": job.correlation_id,
                    "exec_type": job.exec_type.value,
                    "status": job.status,
                },
            )
        except Exception as e:
            logger.error(
                f"Error adding completed job to outgoing queue: {e}",
                extra={
                    "correlation_id": job.correlation_id,
                    "exec_type": job.exec_type.value,
                },
            )
            raise

    @tracer.capture_method
    def read_completed_job(self, max_messages: int = 10, wait_time_seconds: int = 20) -> list[dict[str, Any]]:
        try:
            response = self.sqs.receive_message(
                QueueUrl=self.outgoing_queue_url,
                MaxNumberOfMessages=min(max_messages, 10),
                WaitTimeSeconds=wait_time_seconds,
                MessageAttributeNames=["All"],
            )

            messages: list[dict[str, Any]] = response.get("Messages", [])
            logger.debug(
                f"Read {len(messages)} completed jobs from outgoing queue",
                extra={"message_count": len(messages)},
            )
            return messages

        except Exception as e:
            logger.error(f"Error reading from outgoing queue: {e}")
            raise

    @tracer.capture_method
    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        try:
            self.sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
            logger.debug("Deleted message from queue", extra={"queue_url": queue_url})
        except Exception as e:
            logger.error(f"Error deleting message from queue: {e}")
            raise

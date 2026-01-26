"""
SQS data access handler.
"""

import json
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()


class SQSHandler:
    """Handler for SQS send operations."""

    def __init__(self, queue_url: str) -> None:
        self.queue_url = queue_url
        self.client = boto3.client("sqs")

    @tracer.capture_method
    def send_message(self, message: dict[str, Any], message_group_id: str | None = None) -> str:
        """
        Send a message to the SQS queue.

        Args:
            message: Message data to send (will be JSON serialized)
            message_group_id: Optional group ID for FIFO queues

        Returns:
            Message ID
        """
        params: dict[str, Any] = {
            "QueueUrl": self.queue_url,
            "MessageBody": json.dumps(message),
        }

        if message_group_id:
            params["MessageGroupId"] = message_group_id

        response = self.client.send_message(**params)
        message_id: str = response["MessageId"]

        logger.debug(
            "Sent message to SQS",
            extra={"message_id": message_id, "queue_url": self.queue_url},
        )
        return message_id

    @tracer.capture_method
    def send_message_batch(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Send multiple messages to the SQS queue.

        Args:
            messages: List of message data to send

        Returns:
            Response with successful and failed message IDs
        """
        entries = [
            {
                "Id": str(i),
                "MessageBody": json.dumps(msg),
            }
            for i, msg in enumerate(messages)
        ]

        response = self.client.send_message_batch(
            QueueUrl=self.queue_url,
            Entries=entries,
        )

        successful = len(response.get("Successful", []))
        failed = len(response.get("Failed", []))

        logger.debug(
            "Sent message batch to SQS",
            extra={
                "successful": successful,
                "failed": failed,
                "queue_url": self.queue_url,
            },
        )

        return dict(response)

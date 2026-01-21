"""
S3 data access handler.
"""

import json
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()


class S3Handler:
    """Handler for S3 read/write operations."""

    def __init__(self, bucket_name: str) -> None:
        self.bucket_name = bucket_name
        self.client = boto3.client("s3")

    @tracer.capture_method
    def read_json(self, key: str) -> dict[str, Any] | None:
        """
        Read JSON data from S3.

        Args:
            key: S3 object key

        Returns:
            Parsed JSON data or None if not found
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data: dict[str, Any] = json.loads(response["Body"].read().decode("utf-8"))
            logger.debug("Read data from S3", extra={"key": key})
            return data
        except self.client.exceptions.NoSuchKey:
            logger.warning("S3 key not found", extra={"key": key})
            return None

    @tracer.capture_method
    def write_json(self, key: str, data: dict[str, Any]) -> None:
        """
        Write JSON data to S3.

        Args:
            key: S3 object key
            data: Data to write
        """
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        logger.debug("Wrote data to S3", extra={"key": key})

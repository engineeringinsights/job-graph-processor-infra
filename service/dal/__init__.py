"""
Data access layer for service.
"""

from service.dal.dynamodb import DynamoDBHandler
from service.dal.s3 import S3Handler
from service.dal.sqs import SQSHandler

__all__ = ["DynamoDBHandler", "S3Handler", "SQSHandler"]

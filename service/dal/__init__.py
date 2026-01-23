"""
Data access layer for service.
"""

from service.dal.dynamodb import DynamoDBHandler
from service.dal.sqs import SQSHandler

__all__ = ["DynamoDBHandler", "SQSHandler"]

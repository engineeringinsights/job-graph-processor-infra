"""
DynamoDB data access layer.

This module provides a clean interface for DynamoDB operations.
"""

from typing import Any, cast

import boto3
from aws_lambda_powertools import Logger, Tracer
from boto3.dynamodb.conditions import ConditionBase, Key

logger = Logger()
tracer = Tracer()


class DynamoDBHandler:
    """Handler for DynamoDB operations."""

    def __init__(self, table_name: str) -> None:
        """
        Initialize the DynamoDB handler.

        Args:
            table_name: Name of the DynamoDB table
        """
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    @tracer.capture_method
    def create_item(self, pk: str, sk: str, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new item in the table.

        Args:
            pk: Partition key
            sk: Sort key
            data: Item data

        Returns:
            The created item
        """
        item: dict[str, Any] = {
            "pk": pk,
            "sk": sk,
            **data,
        }

        self.table.put_item(Item=item)
        logger.info("Created item", extra={"pk": pk, "sk": sk})

        return item

    @tracer.capture_method
    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        """
        Get an item from the table.

        Args:
            pk: Partition key
            sk: Sort key

        Returns:
            The item if found, None otherwise
        """
        response = self.table.get_item(
            Key={
                "pk": pk,
                "sk": sk,
            }
        )

        item = response.get("Item")
        if item:
            logger.info("Retrieved item", extra={"pk": pk, "sk": sk})
            return cast(dict[str, Any], item)

        logger.info("Item not found", extra={"pk": pk, "sk": sk})
        return None

    @tracer.capture_method
    def query_items(self, pk: str, sk_prefix: str | None = None) -> list[dict[str, Any]]:
        """
        Query items by partition key and optional sort key prefix.

        Args:
            pk: Partition key
            sk_prefix: Optional sort key prefix for begins_with condition

        Returns:
            List of matching items
        """
        key_condition: ConditionBase = Key("pk").eq(pk)

        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        response = self.table.query(KeyConditionExpression=key_condition)
        items = response.get("Items", [])

        logger.info("Queried items", extra={"pk": pk, "count": len(items)})

        return cast(list[dict[str, Any]], items)

    @tracer.capture_method
    def delete_item(self, pk: str, sk: str) -> None:
        """
        Delete an item from the table.

        Args:
            pk: Partition key
            sk: Sort key
        """
        self.table.delete_item(
            Key={
                "pk": pk,
                "sk": sk,
            }
        )
        logger.info("Deleted item", extra={"pk": pk, "sk": sk})

"""
DynamoDB data access handler for job metadata.
"""

from typing import Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from boto3.dynamodb.conditions import ConditionBase, Key

logger = Logger()
tracer = Tracer()


class DynamoDBHandler:
    """Handler for DynamoDB operations on job metadata."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(table_name)

    @tracer.capture_method
    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        """
        Get an item by primary key.

        Args:
            pk: Partition key value
            sk: Sort key value

        Returns:
            Item data or None if not found
        """
        response = self.table.get_item(Key={"pk": pk, "sk": sk})
        item: dict[str, Any] | None = response.get("Item")
        if item:
            logger.debug("Retrieved item from DynamoDB", extra={"pk": pk, "sk": sk})
        else:
            logger.debug("Item not found in DynamoDB", extra={"pk": pk, "sk": sk})
        return item

    @tracer.capture_method
    def put_item(self, item: dict[str, Any]) -> None:
        """
        Put an item into the table.

        Args:
            item: Item to store (must include pk and sk)
        """
        self.table.put_item(Item=item)
        logger.debug("Stored item in DynamoDB", extra={"pk": item.get("pk"), "sk": item.get("sk")})

    @tracer.capture_method
    def update_item(
        self,
        pk: str,
        sk: str,
        update_expression: str,
        expression_values: dict[str, Any],
        expression_names: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Update an item in the table.

        Args:
            pk: Partition key value
            sk: Sort key value
            update_expression: DynamoDB update expression
            expression_values: Expression attribute values
            expression_names: Expression attribute names (optional)

        Returns:
            Updated item attributes
        """
        kwargs: dict[str, Any] = {
            "Key": {"pk": pk, "sk": sk},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_values,
            "ReturnValues": "ALL_NEW",
        }
        if expression_names:
            kwargs["ExpressionAttributeNames"] = expression_names

        response = self.table.update_item(**kwargs)
        logger.debug("Updated item in DynamoDB", extra={"pk": pk, "sk": sk})
        attributes: dict[str, Any] = response.get("Attributes", {})
        return attributes

    @tracer.capture_method
    def delete_item(self, pk: str, sk: str) -> None:
        """
        Delete an item from the table.

        Args:
            pk: Partition key value
            sk: Sort key value
        """
        self.table.delete_item(Key={"pk": pk, "sk": sk})
        logger.debug("Deleted item from DynamoDB", extra={"pk": pk, "sk": sk})

    @tracer.capture_method
    def query(
        self,
        pk: str,
        sk_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query items by partition key with optional sort key prefix.

        Args:
            pk: Partition key value
            sk_prefix: Optional sort key prefix to filter by
            limit: Maximum number of items to return

        Returns:
            List of matching items
        """
        key_condition: ConditionBase = Key("pk").eq(pk)
        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        kwargs: dict[str, Any] = {"KeyConditionExpression": key_condition}
        if limit:
            kwargs["Limit"] = limit

        response = self.table.query(**kwargs)
        items: list[dict[str, Any]] = response.get("Items", [])
        logger.debug("Queried DynamoDB", extra={"pk": pk, "sk_prefix": sk_prefix, "count": len(items)})
        return items

    @tracer.capture_method
    def batch_write(self, items: list[dict[str, Any]]) -> None:
        """
        Write multiple items in batch.

        Args:
            items: List of items to write (each must include pk and sk)
        """
        with self.table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
        logger.debug("Batch wrote items to DynamoDB", extra={"count": len(items)})

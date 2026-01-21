"""
Get item Lambda handler.

This handler retrieves an item from the DynamoDB table.
"""

import json
import os
from http import HTTPStatus
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from service.dal.dynamodb import DynamoDBHandler

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for getting items.

    Args:
        event: API Gateway event or direct invocation payload
        context: Lambda context

    Returns:
        Response dict with statusCode and body
    """
    logger.info("Processing get item request", extra={"event": event})

    try:
        # Extract pk and sk from path parameters or body
        path_params = event.get("pathParameters", {}) or {}
        query_params = event.get("queryStringParameters", {}) or {}

        pk = path_params.get("pk") or query_params.get("pk") or event.get("pk")
        sk = path_params.get("sk") or query_params.get("sk") or event.get("sk")

        if not pk or not sk:
            return {
                "statusCode": HTTPStatus.BAD_REQUEST,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "pk and sk are required"}),
            }

        # Get item from DynamoDB
        table_name = os.environ["TABLE_NAME"]
        db_handler = DynamoDBHandler(table_name)

        item = db_handler.get_item(pk=pk, sk=sk)

        if item is None:
            logger.info("Item not found", extra={"pk": pk, "sk": sk})
            return {
                "statusCode": HTTPStatus.NOT_FOUND,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Item not found"}),
            }

        logger.info("Item retrieved successfully", extra={"pk": pk, "sk": sk})

        return {
            "statusCode": HTTPStatus.OK,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(item, default=str),
        }

    except Exception:
        logger.exception("Unexpected error getting item")
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }

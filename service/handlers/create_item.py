"""
Create item Lambda handler.

This handler creates a new item in the DynamoDB table.
"""

import json
import os
from http import HTTPStatus
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from service.dal.dynamodb import DynamoDBHandler
from service.models.item import CreateItemRequest

logger = Logger()
tracer = Tracer()


@logger.inject_lambda_context
@tracer.capture_lambda_handler(capture_response=False)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Lambda handler for creating items.

    Args:
        event: API Gateway event or direct invocation payload
        context: Lambda context

    Returns:
        Response dict with statusCode and body
    """
    logger.info("Processing create item request", extra={"event": event})

    try:
        # Parse and validate request
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event
        request = CreateItemRequest(**body)

        # Create item in DynamoDB
        table_name = os.environ["TABLE_NAME"]
        db_handler = DynamoDBHandler(table_name)

        item = db_handler.create_item(
            pk=request.pk,
            sk=request.sk,
            data=request.data,
        )

        logger.info("Item created successfully", extra={"pk": request.pk, "sk": request.sk})

        return {
            "statusCode": HTTPStatus.CREATED,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(item, default=str),
        }

    except ValueError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }

    except Exception:
        logger.exception("Unexpected error creating item")
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }

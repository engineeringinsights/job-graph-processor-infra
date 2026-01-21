"""
Unit tests for the AppStack.
"""

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

from cdk.app_stack import AppStack


@pytest.fixture
def template() -> Template:
    """Create a CDK template for testing."""
    app = App()
    stack = AppStack(
        app,
        "TestStack",
        stage="dev",
        table_name="test-table",
    )
    return Template.from_stack(stack)


def test_dynamodb_table_created(template: Template) -> None:
    """Test that a DynamoDB table is created."""
    template.resource_count_is("AWS::DynamoDB::Table", 1)


def test_lambda_functions_created(template: Template) -> None:
    """Test that Lambda functions are created."""
    template.resource_count_is("AWS::Lambda::Function", 2)


def test_lambda_layer_created(template: Template) -> None:
    """Test that a Lambda layer is created."""
    template.resource_count_is("AWS::Lambda::LayerVersion", 1)


def test_dynamodb_table_has_correct_key_schema(template: Template) -> None:
    """Test that DynamoDB table has pk and sk keys."""
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
        },
    )


def test_lambda_uses_x86_64_architecture(template: Template) -> None:
    """Test that Lambda functions use x86_64 architecture."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Architectures": ["x86_64"],
        },
    )


def test_lambda_has_tracing_enabled(template: Template) -> None:
    """Test that Lambda functions have X-Ray tracing enabled."""
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "TracingConfig": {"Mode": "Active"},
        },
    )

"""
Unit tests for Scenario1Stack.
"""

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

from cdk.scenario1_stack import Scenario1Stack


@pytest.fixture
def app() -> App:
    """Create a CDK app for testing."""
    return App()


@pytest.fixture
def stack(app: App) -> Scenario1Stack:
    """Create a Scenario1Stack for testing."""
    return Scenario1Stack(
        app,
        "TestStack",
        stage="test",
        test_run_id="unit-test",
    )


@pytest.fixture
def template(stack: Scenario1Stack) -> Template:
    """Create a CDK template for testing."""
    return Template.from_stack(stack)


class TestScenario1StackCreation:
    """Test that the stack can be created successfully."""

    def test_stack_creates_successfully(self, stack: Scenario1Stack) -> None:
        """Test that the stack can be instantiated."""
        assert stack is not None
        assert stack.stage == "test"
        assert stack.test_run_id == "unit-test"
        assert stack.resource_prefix == "scenario-1-test"

    def test_stack_has_bucket(self, stack: Scenario1Stack) -> None:
        """Test that the stack has a bucket."""
        assert stack.bucket is not None

    def test_stack_has_table(self, stack: Scenario1Stack) -> None:
        """Test that the stack has a DynamoDB table."""
        assert stack.table is not None

    def test_stack_has_queues(self, stack: Scenario1Stack) -> None:
        """Test that the stack has queues."""
        assert stack.incoming_queue is not None
        assert stack.outgoing_queue is not None
        assert stack.dlq is not None

    def test_stack_has_processor_function(self, stack: Scenario1Stack) -> None:
        """Test that the stack has a processor Lambda function."""
        assert stack.processor_function is not None

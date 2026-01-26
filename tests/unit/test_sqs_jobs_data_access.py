from unittest.mock import patch

import pytest

from service.dal.sqs_jobs import SqsJobsDataAccess
from service.models.job import CompletedJob, ExecType, IncomingJob


@pytest.fixture
def mock_sqs_client():
    with patch("boto3.client") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def sqs_data_access(mock_sqs_client):
    return SqsJobsDataAccess(
        incoming_queue_url="https://sqs.eu-west-1.amazonaws.com/123456789/incoming-queue",
        outgoing_queue_url="https://sqs.eu-west-1.amazonaws.com/123456789/outgoing-queue",
    )


def test_add_todo_job(sqs_data_access, mock_sqs_client):
    job = IncomingJob(
        correlation_id="test-123",
        sequence_id=0,
        exec_type=ExecType.FIRST,
        route_index=0,
        route_data={"origin_iata": "DUB", "destination_iata": "OSL"},
        home_airport_iata="DUB",
        total_routes=3,
    )

    sqs_data_access.add_todo_job(job)

    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    assert call_args["QueueUrl"] == sqs_data_access.incoming_queue_url
    assert "correlation_id" in call_args["MessageBody"]
    assert "test-123" in call_args["MessageBody"]


def test_read_todo_job(sqs_data_access, mock_sqs_client):
    mock_sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "Body": '{"correlation_id": "test-123"}',
                "ReceiptHandle": "receipt-handle-1",
            }
        ]
    }

    messages = sqs_data_access.read_todo_job(max_messages=5, wait_time_seconds=10)

    assert len(messages) == 1
    assert messages[0]["Body"] == '{"correlation_id": "test-123"}'
    mock_sqs_client.receive_message.assert_called_once_with(
        QueueUrl=sqs_data_access.incoming_queue_url,
        MaxNumberOfMessages=5,
        WaitTimeSeconds=10,
        MessageAttributeNames=["All"],
    )


def test_read_todo_job_empty_queue(sqs_data_access, mock_sqs_client):
    mock_sqs_client.receive_message.return_value = {}

    messages = sqs_data_access.read_todo_job(max_messages=10, wait_time_seconds=20)

    assert len(messages) == 0


def test_add_completed_job(sqs_data_access, mock_sqs_client):
    job = CompletedJob(
        correlation_id="test-123",
        sequence_id=0,
        exec_type=ExecType.FIRST,
        route_index=0,
        status="success",
        processing_time_ms=150,
    )

    sqs_data_access.add_completed_job(job)

    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    assert call_args["QueueUrl"] == sqs_data_access.outgoing_queue_url
    assert "correlation_id" in call_args["MessageBody"]
    assert "test-123" in call_args["MessageBody"]
    assert "success" in call_args["MessageBody"]


def test_read_completed_job(sqs_data_access, mock_sqs_client):
    mock_sqs_client.receive_message.return_value = {
        "Messages": [
            {
                "Body": '{"correlation_id": "test-123", "status": "success"}',
                "ReceiptHandle": "receipt-handle-1",
            },
            {
                "Body": '{"correlation_id": "test-456", "status": "failed"}',
                "ReceiptHandle": "receipt-handle-2",
            },
        ]
    }

    messages = sqs_data_access.read_completed_job(max_messages=10, wait_time_seconds=20)

    assert len(messages) == 2
    assert messages[0]["Body"] == '{"correlation_id": "test-123", "status": "success"}'
    assert messages[1]["Body"] == '{"correlation_id": "test-456", "status": "failed"}'
    mock_sqs_client.receive_message.assert_called_once_with(
        QueueUrl=sqs_data_access.outgoing_queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,
        MessageAttributeNames=["All"],
    )


def test_delete_message(sqs_data_access, mock_sqs_client):
    queue_url = "https://sqs.eu-west-1.amazonaws.com/123456789/test-queue"
    receipt_handle = "receipt-handle-123"

    sqs_data_access.delete_message(queue_url=queue_url, receipt_handle=receipt_handle)

    mock_sqs_client.delete_message.assert_called_once_with(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )


def test_read_todo_job_respects_max_messages_limit(sqs_data_access, mock_sqs_client):
    mock_sqs_client.receive_message.return_value = {"Messages": []}

    # Test that max_messages is capped at 10
    sqs_data_access.read_todo_job(max_messages=50, wait_time_seconds=5)

    call_args = mock_sqs_client.receive_message.call_args[1]
    assert call_args["MaxNumberOfMessages"] == 10


def test_add_todo_job_error_handling(sqs_data_access, mock_sqs_client):
    mock_sqs_client.send_message.side_effect = Exception("SQS error")

    job = IncomingJob(
        correlation_id="test-123",
        sequence_id=0,
        exec_type=ExecType.FIRST,
        route_index=0,
        route_data={},
        home_airport_iata="DUB",
        total_routes=3,
    )

    with pytest.raises(Exception, match="SQS error"):
        sqs_data_access.add_todo_job(job)


def test_read_completed_job_error_handling(sqs_data_access, mock_sqs_client):
    mock_sqs_client.receive_message.side_effect = Exception("SQS connection error")

    with pytest.raises(Exception, match="SQS connection error"):
        sqs_data_access.read_completed_job(max_messages=5, wait_time_seconds=10)

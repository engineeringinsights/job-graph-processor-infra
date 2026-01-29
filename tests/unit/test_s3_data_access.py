import io
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from service.dal.s3 import DelayDataAccess, PercentilesS3DataAccess, SequenceS3DataAccess
from service.models.aircraft_daily_sequence_dto import DailySequenceDto


@pytest.fixture
def mock_s3_client():
    with patch("boto3.client") as mock_client:
        yield mock_client.return_value


class TestDelayDataAccess:
    @pytest.fixture
    def delay_access(self, mock_s3_client):
        return DelayDataAccess(bucket="test-bucket", prefix="test-prefix")

    def test_init(self, delay_access):
        assert delay_access.bucket == "test-bucket"
        assert delay_access.prefix == "test-prefix"

    def test_init_with_trailing_slashes(self, mock_s3_client):
        access = DelayDataAccess(bucket="test-bucket", prefix="/test-prefix/")
        assert access.prefix == "test-prefix"

    def test_key_generation(self, delay_access):
        key = delay_access._key("ABC123", 42)
        assert key == "test-prefix/delays/ABC123/sequence_42.parquet"

    def test_store_delays(self, delay_access, mock_s3_client):
        df = pd.DataFrame({"delay": [10, 20, 30], "airport": ["DUB", "OSL", "DME"]})

        result = delay_access.store_delays(df, "ABC123", 42)

        assert result == "test-prefix/delays/ABC123/sequence_42.parquet"
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "test-bucket"
        assert call_args.kwargs["Key"] == "test-prefix/delays/ABC123/sequence_42.parquet"

        body = call_args.kwargs["Body"]
        result_df = pd.read_parquet(io.BytesIO(body))
        pd.testing.assert_frame_equal(result_df, df)

    def test_get_delays(self, delay_access, mock_s3_client):
        df = pd.DataFrame({"delay": [10, 20, 30], "airport": ["DUB", "OSL", "DME"]})
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)

        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = buffer.read()
        mock_s3_client.get_object.return_value = mock_response

        result = delay_access.get_delays("test-prefix/delays/ABC123/sequence_42.parquet")

        pd.testing.assert_frame_equal(result, df)
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-prefix/delays/ABC123/sequence_42.parquet"
        )

    def test_get_delays_not_found(self, delay_access, mock_s3_client):
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(FileNotFoundError) as exc_info:
            delay_access.get_delays("non-existent-key")

        assert "s3://test-bucket/non-existent-key not found" in str(exc_info.value)


class TestPercentilesS3DataAccess:
    @pytest.fixture
    def percentiles_access(self, mock_s3_client):
        return PercentilesS3DataAccess(bucket="test-bucket", prefix="test-prefix")

    def test_init(self, percentiles_access):
        assert percentiles_access.bucket == "test-bucket"
        assert percentiles_access.prefix == "test-prefix"

    def test_init_with_empty_prefix(self, mock_s3_client):
        access = PercentilesS3DataAccess(bucket="test-bucket", prefix="")
        assert access.prefix == ""

    def test_key_generation(self, percentiles_access):
        key = percentiles_access._key(42)
        assert key == "test-prefix/percentiles/sequence_42.json"

    def test_store_percentiles(self, percentiles_access, mock_s3_client):
        percentile_data = {"p50": 10.5, "p95": 25.3, "p99": 45.7}

        percentiles_access.store_percentiles(42, percentile_data)

        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "test-bucket"
        assert call_args.kwargs["Key"] == "test-prefix/percentiles/sequence_42.json"

        body = call_args.kwargs["Body"]
        stored_data = json.loads(body.decode("utf-8"))
        assert stored_data == percentile_data

    def test_get_percentiles(self, percentiles_access, mock_s3_client):
        percentile_data = {"p50": 10.5, "p95": 25.3, "p99": 45.7}

        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = json.dumps(percentile_data).encode("utf-8")
        mock_s3_client.get_object.return_value = mock_response

        result = percentiles_access.get_percentiles(42)

        assert result == percentile_data
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-prefix/percentiles/sequence_42.json"
        )

    def test_get_percentiles_not_found(self, percentiles_access, mock_s3_client):
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(FileNotFoundError) as exc_info:
            percentiles_access.get_percentiles(999)

        assert "s3://test-bucket/test-prefix/percentiles/sequence_999.json not found" in str(exc_info.value)

    def test_get_percentiles_other_error(self, percentiles_access, mock_s3_client):
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(ClientError):
            percentiles_access.get_percentiles(42)


class TestSequenceS3DataAccess:
    @pytest.fixture
    def sequence_access(self, mock_s3_client):
        return SequenceS3DataAccess(bucket="test-bucket", prefix="test-prefix")

    def test_init(self, sequence_access):
        assert sequence_access.bucket == "test-bucket"
        assert sequence_access.prefix == "test-prefix"

    def test_key_generation(self, sequence_access):
        key = sequence_access._key(42)
        assert key == "test-prefix/sequences/sequence_42.json"

    def test_get_sequence(self, sequence_access, mock_s3_client):
        sequence_data = {
            "sequence_id": 42,
            "home_airport_iata": "DUB",
            "routes": [
                {
                    "origin_iata": "DUB",
                    "destination_iata": "OSL",
                    "estimated_gate_open_time": "00:25:00",
                    "estimated_takeoff_time": "02:04:00",
                    "estimated_arrival_time": "03:41:00",
                }
            ],
        }

        mock_response = {"Body": MagicMock()}
        mock_response["Body"].read.return_value = json.dumps(sequence_data).encode("utf-8")
        mock_s3_client.get_object.return_value = mock_response

        result = sequence_access.get_sequence(42)

        assert isinstance(result, DailySequenceDto)
        assert result.sequence_id == 42
        assert result.home_airport_iata == "DUB"
        assert len(result.routes) == 1
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-prefix/sequences/sequence_42.json"
        )

    def test_get_sequence_not_found(self, sequence_access, mock_s3_client):
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(FileNotFoundError) as exc_info:
            sequence_access.get_sequence(999)

        assert "s3://test-bucket/test-prefix/sequences/sequence_999.json not found" in str(exc_info.value)

    def test_get_sequence_other_error(self, sequence_access, mock_s3_client):
        error_response = {"Error": {"Code": "InternalError", "Message": "Internal error"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(ClientError):
            sequence_access.get_sequence(42)

    def test_get_sequence_with_empty_prefix(self, mock_s3_client):
        access = SequenceS3DataAccess(bucket="test-bucket", prefix="")
        key = access._key(42)
        assert key == "/sequences/sequence_42.json"

    def test_store_sequence(self, sequence_access, mock_s3_client):
        from service.models.aircraft_daily_sequence_dto import RouteDto

        sequence = DailySequenceDto(
            sequence_id=42,
            home_airport_iata="DUB",
            routes=[
                RouteDto(
                    origin_iata="DUB",
                    destination_iata="OSL",
                    estimated_gate_open_time="00:25:00",
                    estimated_takeoff_time="02:04:00",
                    estimated_arrival_time="03:41:00",
                )
            ],
        )

        result = sequence_access.store_sequence(sequence)

        assert result == 42
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "test-bucket"
        assert call_args.kwargs["Key"] == "test-prefix/sequences/sequence_42.json"

        body = call_args.kwargs["Body"].decode("utf-8")
        stored_data = json.loads(body)
        assert stored_data["sequence_id"] == 42
        assert stored_data["home_airport_iata"] == "DUB"
        assert len(stored_data["routes"]) == 1

import io
import json

import boto3
import pandas as pd
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError

from service.dal.interface import (
    IDelayDataAccess,
    IMergedPercentilesDataAccess,
    IModelDataAccess,
    IPercentilesDataAccess,
    ISequenceDataAccess,
)
from service.models.aircraft_daily_sequence_dto import DailySequenceDto

logger = Logger()
tracer = Tracer()


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix.strip("/")


class S3Handler:
    def __init__(self, bucket_name: str) -> None:
        self.bucket_name = bucket_name
        self.s3 = boto3.client("s3")

    @tracer.capture_method
    def read_json(self, key: str) -> dict | None:
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            content = response["Body"].read().decode("utf-8")
            data: dict = json.loads(content)
            logger.debug("Read JSON from S3", extra={"bucket": self.bucket_name, "key": key})
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.debug("S3 object not found", extra={"bucket": self.bucket_name, "key": key})
                return None
            logger.error(
                f"Error reading from S3: {e}",
                extra={"bucket": self.bucket_name, "key": key},
            )
            raise

    @tracer.capture_method
    def write_json(self, key: str, data: dict) -> None:
        try:
            json_str = json.dumps(data, indent=2, default=str)
            self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=json_str.encode("utf-8"))
            logger.debug("Wrote JSON to S3", extra={"bucket": self.bucket_name, "key": key})
        except Exception as e:
            logger.error(
                f"Error writing to S3: {e}",
                extra={"bucket": self.bucket_name, "key": key},
            )
            raise


class ModelS3DataAccess(IModelDataAccess):
    def __init__(self, bucket: str, prefix: str, model_id: int):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.model_id = model_id

    def _setup_client(self):
        if not self.s3:
            self.s3 = boto3.client("s3")

    def _key(self, *parts: str) -> str:
        stripped_parts = [p.strip("/") for p in parts if p is not None and p != ""]
        if self.prefix:
            return "/".join([self.prefix] + stripped_parts)
        return "/".join(stripped_parts)

    def _get_parquet_df(self, key: str) -> pd.DataFrame:
        try:
            self._setup_client()
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            # Translate not found to a Pythonic error
            raise FileNotFoundError(f"S3 object s3://{self.bucket}/{key} not found: {e}") from e
        body = resp["Body"].read()
        bio = io.BytesIO(body)
        bio.seek(0)
        df = pd.read_parquet(bio)
        return df

    def get_landing_model(self, airport_iata: str) -> pd.DataFrame:
        key = self._key("landing_delay_models", str(self.model_id), f"{airport_iata}.parquet")
        return self._get_parquet_df(key)

    def get_departure_model(self, airport_iata: str) -> pd.DataFrame:
        key = self._key("departure_delay_models", str(self.model_id), f"{airport_iata}.parquet")
        return self._get_parquet_df(key)

    def store_landing_model(self, delays: pd.DataFrame, airport_iata: str):
        self._setup_client()
        key = self._key("landing_delay_models", str(self.model_id), f"{airport_iata}.parquet")

        # Convert DataFrame to parquet in memory
        buffer = io.BytesIO()
        delays.to_parquet(buffer, index=False)
        buffer.seek(0)

        # Upload to S3
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())

    def store_departure_model(self, delays: pd.DataFrame, airport_iata: str):
        self._setup_client()
        key = self._key("departure_delay_models", str(self.model_id), f"{airport_iata}.parquet")

        # Convert DataFrame to parquet in memory
        buffer = io.BytesIO()
        delays.to_parquet(buffer, index=False)
        buffer.seek(0)

        # Upload to S3
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())


class DelayDataS3Access(IDelayDataAccess):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.s3 = boto3.client("s3")

    def _key(self, run_id: str, job_id: str) -> str:
        return f"{self.prefix}/{run_id}/delays/{job_id}.parquet"

    def store_delays(self, delays: pd.DataFrame, run_id: str, job_id: str) -> str:
        key = self._key(run_id, job_id)

        # Convert DataFrame to parquet in memory
        buffer = io.BytesIO()
        delays.to_parquet(buffer, index=False)
        buffer.seek(0)

        # Upload to S3
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())
        return key

    def get_delays(self, run_id: str, job_id: str) -> pd.DataFrame:
        key = self._key(run_id, job_id)
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            raise FileNotFoundError(f"S3 object s3://{self.bucket}/{key} not found: {e}") from e

        body = resp["Body"].read()
        bio = io.BytesIO(body)
        bio.seek(0)
        df = pd.read_parquet(bio)
        return df


class PercentilesS3DataAccess(IPercentilesDataAccess):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.s3 = boto3.client("s3")

    def _key(self, run_id: str, sequence_id: int) -> str:
        return f"{self.prefix}/{run_id}/percentiles/{sequence_id}.json"

    def store_percentiles(self, run_id: str, sequence_id: int, percentile: dict):
        key = self._key(run_id, sequence_id)
        json_str = json.dumps(percentile, indent=2, default=str)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json_str.encode("utf-8"))

    def get_percentiles(self, run_id: str, sequence_id: int) -> dict:
        key = self._key(run_id, sequence_id)
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            data: dict = json.loads(content)
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"S3 object s3://{self.bucket}/{key} not found: {e}") from e
            raise


class MergedPercentilesS3DataAccess(IMergedPercentilesDataAccess):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.s3 = boto3.client("s3")

    def _key(self, run_id: str) -> str:
        return f"{self.prefix}/{run_id}/merged_percentiles/merged_percentiles.json"

    def store_merged_percentiles(self, run_id: str, percentile: dict):
        key = self._key(run_id)
        json_str = json.dumps(percentile, indent=2, default=str)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json_str.encode("utf-8"))

    def get_merged_percentiles(self, run_id: str) -> dict:
        key = self._key(run_id)
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            data: dict = json.loads(content)
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"S3 object s3://{self.bucket}/{key} not found: {e}") from e
            raise


class SequenceS3DataAccess(ISequenceDataAccess):
    def __init__(self, bucket: str, prefix: str):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.s3 = boto3.client("s3")

    def _key(self, sequence_id: int) -> str:
        return f"{self.prefix}/sequences/sequence_{sequence_id}.json"

    def get_sequence(self, sequence_id: int) -> DailySequenceDto:
        key = self._key(sequence_id)
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            data: dict = json.loads(content)
            return DailySequenceDto(**data)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"S3 object s3://{self.bucket}/{key} not found: {e}") from e
            raise

    def store_sequence(self, sequence: DailySequenceDto) -> int:
        key = self._key(sequence.sequence_id)
        json_str = json.dumps(sequence.model_dump(), indent=2, default=str)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=json_str.encode("utf-8"))
        return sequence.sequence_id

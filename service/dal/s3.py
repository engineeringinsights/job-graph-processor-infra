import io

import boto3
import pandas as pd
from botocore.exceptions import ClientError

from service.dal.interface import (
    IModelDataAccess,
)


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix.strip("/")


class ModelS3DataAccess(IModelDataAccess):
    def __init__(self, bucket: str, prefix: str, model_id: int):
        self.bucket = bucket
        self.prefix = _normalize_prefix(prefix)
        self.model_id = model_id
        self.s3 = None

    def _setup_client(self):
        if not self.s3:
            self.s3 = boto3.client("s3")

    def _key(self, *parts: str) -> str:
        parts = [p.strip("/") for p in parts if p is not None and p != ""]
        if self.prefix:
            return "/".join([self.prefix] + parts)
        return "/".join(parts)

    def _get_parquet_df(self, key: str) -> pd.DataFrame:
        try:
            self._setup_client()
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            # Translate not found to a Pythonic error
            raise FileNotFoundError(
                f"S3 object s3://{self.bucket}/{key} not found: {e}"
            ) from e
        body = resp["Body"].read()
        bio = io.BytesIO(body)
        bio.seek(0)
        df = pd.read_parquet(bio)
        return df

    def get_landing_model(self, airport_iata: str) -> pd.DataFrame:
        key = self._key(
            "landing_delay_models", str(self.model_id), f"{airport_iata}.parquet"
        )
        return self._get_parquet_df(key)

    def get_departure_model(self, airport_iata: str) -> pd.DataFrame:
        key = self._key(
            "departure_delay_models", str(self.model_id), f"{airport_iata}.parquet"
        )
        return self._get_parquet_df(key)

    def store_landing_model(self, delays: pd.DataFrame, airport_iata: str):
        """Store landing delay model DataFrame as parquet file on S3."""
        self._setup_client()
        key = self._key(
            "landing_delay_models", str(self.model_id), f"{airport_iata}.parquet"
        )

        # Convert DataFrame to parquet in memory
        buffer = io.BytesIO()
        delays.to_parquet(buffer, index=False)
        buffer.seek(0)

        # Upload to S3
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())

    def store_departure_model(self, delays: pd.DataFrame, airport_iata: str):
        """Store departure delay model DataFrame as parquet file on S3."""
        self._setup_client()
        key = self._key(
            "departure_delay_models", str(self.model_id), f"{airport_iata}.parquet"
        )

        # Convert DataFrame to parquet in memory
        buffer = io.BytesIO()
        delays.to_parquet(buffer, index=False)
        buffer.seek(0)

        # Upload to S3
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=buffer.getvalue())

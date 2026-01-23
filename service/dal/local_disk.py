import json
import os
import uuid

import pandas as pd

from service.dal.interface import (
    IDelayDataAccess,
    IModelDataAccess,
    IPercentilesDataAccess,
    ISequenceDataAccess,
)
from service.models.aircraft_daily_sequence_dto import DailySequenceDto


class ModelLocalDiskDataAccess(IModelDataAccess):
    def __init__(self, path: str, model_id: int):
        self.path = path
        self.model_id = model_id

    def get_landing_model(self, airport_iata: str) -> pd.DataFrame:
        full_path = (
            self.path + f"/landing_delay_models/{self.model_id}/{airport_iata}.parquet"
        )
        df = pd.read_parquet(full_path)
        return df

    def get_departure_model(self, airport_iata: str) -> pd.DataFrame:
        full_path = (
            self.path
            + f"/departure_delay_models/{self.model_id}/{airport_iata}.parquet"
        )
        df = pd.read_parquet(full_path)
        return df

    def store_landing_model(self, delays: pd.DataFrame, airport_iata: str):
        full_path = (
            self.path + f"/landing_delay_models/{self.model_id}/{airport_iata}.parquet"
        )
        os.makedirs(self.path + f"/landing_delay_models/{self.model_id}", exist_ok=True)
        delays.to_parquet(full_path)

    def store_departure_model(self, delays: pd.DataFrame, airport_iata: str):
        full_path = (
            self.path
            + f"/departure_delay_models/{self.model_id}/{airport_iata}.parquet"
        )
        os.makedirs(
            self.path + f"/departure_delay_models/{self.model_id}", exist_ok=True
        )
        delays.to_parquet(full_path)


class DelayLocalDiskDataAccess(IDelayDataAccess):
    def __init__(self, path: str):
        self.path = path

    def store_delays(self, delays: pd.DataFrame, code: str, sequence_id: int) -> str:
        uid = uuid.uuid4()
        name = f"{code}_{sequence_id}_{uid}"
        os.makedirs(self.path + "/calculated_delays", exist_ok=True)
        full_path = self.path + f"/calculated_delays/{name}.parquet"
        delays.to_parquet(full_path)
        return name

    def get_delays(self, reference: str) -> pd.DataFrame:
        full_path = self.path + f"/calculated_delays/{reference}.parquet"
        df = pd.read_parquet(full_path)
        return df


class SequenceLocalDiskDataAccess(ISequenceDataAccess):
    def __init__(self, path: str):
        self.path = path

    def get_sequence(self, sequence_id: int) -> DailySequenceDto:
        full_path = self.path + f"/sequences/{sequence_id}.json"
        with open(full_path) as file:
            data = json.load(file)
        dto = DailySequenceDto(**data)
        return dto


class PercentileslLocalDiskDataAccess(IPercentilesDataAccess):
    def __init__(self, path: str):
        self.path = path

    def store_percentiles(self, sequence_id: int, percentile: dict):
        os.makedirs(self.path + "/percentiles", exist_ok=True)
        full_path = self.path + f"/percentiles/{sequence_id}.json"
        with open(full_path, "w") as file:
            json.dump(percentile, file)

    def get_percentiles(self, sequence_id: int) -> dict:
        full_path = self.path + f"/percentiles/{sequence_id}.json"
        with open(full_path) as file:
            data = json.load(file)
        return data

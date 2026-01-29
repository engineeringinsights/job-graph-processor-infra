import json
import os

import pandas as pd

from service.dal.interface import (
    IDelayDataAccess,
    IMergedPercentilesDataAccess,
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
        full_path = self.path + f"/landing_delay_models/{self.model_id}/{airport_iata}.parquet"
        df = pd.read_parquet(full_path)
        return df

    def get_departure_model(self, airport_iata: str) -> pd.DataFrame:
        full_path = self.path + f"/departure_delay_models/{self.model_id}/{airport_iata}.parquet"
        df = pd.read_parquet(full_path)
        return df

    def store_landing_model(self, delays: pd.DataFrame, airport_iata: str):
        full_path = self.path + f"/landing_delay_models/{self.model_id}/{airport_iata}.parquet"
        os.makedirs(self.path + f"/landing_delay_models/{self.model_id}", exist_ok=True)
        delays.to_parquet(full_path)

    def store_departure_model(self, delays: pd.DataFrame, airport_iata: str):
        full_path = self.path + f"/departure_delay_models/{self.model_id}/{airport_iata}.parquet"
        os.makedirs(self.path + f"/departure_delay_models/{self.model_id}", exist_ok=True)
        delays.to_parquet(full_path)


class DelayLocalDiskDataAccess(IDelayDataAccess):
    def __init__(self, path: str):
        self.path = path

    def store_delays(self, delays: pd.DataFrame, code: str, run_id: str, sequence_id: int) -> str:
        os.makedirs(f"{self.path}/{run_id}/delays/{sequence_id}/", exist_ok=True)
        full_path = f"{self.path}/{run_id}/delays/{sequence_id}/{code}.parquet"
        delays.to_parquet(full_path)
        return full_path

    def get_delays(self, reference: str, run_id: str) -> pd.DataFrame:
        df = pd.read_parquet(reference)
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

    def store_sequence(self, sequence: DailySequenceDto) -> int:
        os.makedirs(self.path + "/sequences", exist_ok=True)
        full_path = self.path + f"/sequences/{sequence.sequence_id}.json"
        with open(full_path, "w") as file:
            json.dump(sequence.model_dump(), file, indent=2, default=str)
        return sequence.sequence_id


class PercentileslLocalDiskDataAccess(IPercentilesDataAccess):
    def __init__(self, path: str):
        self.path = path

    def store_percentiles(self, run_id: str, sequence_id: int, percentile: dict):
        os.makedirs(f"{self.path}/{run_id}/percentiles/{sequence_id}", exist_ok=True)
        full_path = f"{self.path}/{run_id}/percentiles/{sequence_id}/{sequence_id}.json"
        with open(full_path, "w") as file:
            json.dump(percentile, file)

    def get_percentiles(self, run_id: str, sequence_id: int) -> dict:
        full_path = f"{self.path}/{run_id}/percentiles/{sequence_id}/{sequence_id}.json"
        with open(full_path) as file:
            data: dict = json.load(file)
        return data


class MergedPercentilesLocalDiskDataAccess(IMergedPercentilesDataAccess):
    def __init__(self, path: str):
        self.path = path

    def store_merged_percentiles(self, run_id: str, sequence_id: int, percentile: dict):
        os.makedirs(f"{self.path}/{run_id}/merged_percentiles", exist_ok=True)
        full_path = f"{self.path}/{run_id}/merged_percentiles/{sequence_id}.json"
        with open(full_path, "w") as file:
            json.dump(percentile, file)

    def get_merged_percentiles(self, run_id: str, sequence_id: int) -> dict:
        full_path = f"{self.path}/{run_id}/merged_percentiles/{sequence_id}.json"
        with open(full_path) as file:
            data: dict = json.load(file)
        return data

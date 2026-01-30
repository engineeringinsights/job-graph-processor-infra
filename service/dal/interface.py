from abc import ABC, abstractmethod

import pandas as pd

from service.models.aircraft_daily_sequence_dto import DailySequenceDto


class IModelDataAccess(ABC):
    @abstractmethod
    def get_landing_model(self, airport_iata: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_departure_model(self, airport_iata: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def store_landing_model(self, delays: pd.DataFrame, airport_iata: str):
        pass

    @abstractmethod
    def store_departure_model(self, delays: pd.DataFrame, airport_iata: str):
        pass


class IDelayDataAccess(ABC):
    @abstractmethod
    def store_delays(self, delays: pd.DataFrame, run_id: str, job_id: str) -> str:
        pass

    @abstractmethod
    def get_delays(self, run_id: str, job_id: str) -> pd.DataFrame:
        pass


class IPercentilesDataAccess(ABC):
    @abstractmethod
    def store_percentiles(self, run_id: str, sequence_id: int, percentile: dict):
        pass

    @abstractmethod
    def get_percentiles(self, run_id: str, sequence_id: int) -> dict:
        pass


class IMergedPercentilesDataAccess(ABC):
    @abstractmethod
    def store_merged_percentiles(self, run_id: str, percentile: dict):
        pass

    @abstractmethod
    def get_merged_percentiles(self, run_id: str) -> dict:
        pass


class ISequenceDataAccess(ABC):
    @abstractmethod
    def get_sequence(self, sequence_id: int) -> DailySequenceDto:
        pass

    @abstractmethod
    def store_sequence(self, sequence: DailySequenceDto) -> int:
        pass


class DataAccess:
    def __init__(
        self,
        model_data_access: IModelDataAccess,
        percentiles_access: IPercentilesDataAccess,
        delay_data_access: IDelayDataAccess,
        sequence_data_access: ISequenceDataAccess,
        merged_percentiles_data_access: IMergedPercentilesDataAccess,
    ):
        self.model_data_access: IModelDataAccess = model_data_access
        self.percentiles_access: IPercentilesDataAccess = percentiles_access
        self.delay_data_access: IDelayDataAccess = delay_data_access
        self.sequence_data_access: ISequenceDataAccess = sequence_data_access
        self.merged_percentiles_data_access: IMergedPercentilesDataAccess = merged_percentiles_data_access

from abc import ABC, abstractmethod

import pandas as pd

from service.models.aircraft_daily_sequence_dto import DailySequenceDto
from service.models.job import JobDto, JobStatus


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
    def store_delays(self, delays: pd.DataFrame, code: str, sequence_id: int) -> str:
        pass

    @abstractmethod
    def get_delays(self, reference: str) -> pd.DataFrame:
        pass


class IPercentilesDataAccess(ABC):
    @abstractmethod
    def store_percentiles(self, sequence_id: int, percentile: dict):
        pass

    @abstractmethod
    def get_percentiles(self, sequence_id: int) -> dict:
        pass


class ISequenceDataAccess(ABC):
    @abstractmethod
    def get_sequence(self, sequence_id: int) -> DailySequenceDto:
        pass

    @abstractmethod
    def store_sequence(self, sequence: DailySequenceDto) -> int:
        pass

class IJobDataAccess(ABC):
    @abstractmethod
    def get_job(self, job_id: str) -> JobDto:
        pass

    @abstractmethod
    def get_jobs(self, run_id: str) -> list[JobDto]:
        pass

    @abstractmethod
    def insert_job(self, job_dto: JobDto):
        pass

    @abstractmethod
    def insert_jobs(self, job_dtos: list[JobDto]):
        pass

    @abstractmethod
    def get_all_aggregation_job_predaccessors(self, run_id: str) -> list[JobDto]:
        pass

    @abstractmethod
    def get_all_successors(self, job_id: str) -> list[JobDto]:
        pass

    @abstractmethod
    def get_all_leaves(self, run_id: str) -> list[JobDto]:
        pass
    
    @abstractmethod
    def update_status(self, job_id: str, status: JobStatus):
        pass


class DataAccess:
    def __init__(
        self,
        model_data_access: IModelDataAccess,
        percentiles_access: IPercentilesDataAccess,
        delay_data_access: IDelayDataAccess,
        sequence_data_access: ISequenceDataAccess,
        job_data_access: IJobDataAccess,
    ):
        self.model_data_access: IModelDataAccess = model_data_access
        self.percentiles_access: IPercentilesDataAccess = percentiles_access
        self.delay_data_access: IDelayDataAccess = delay_data_access
        self.sequence_data_access: ISequenceDataAccess = sequence_data_access
        self.jobs_data_access: IJobDataAccess = job_data_access

from service.models.job import JobDto, JobStatus    
from service.dal.interface import IJobDataAccess

class JobDataAccessInMemory(IJobDataAccess):
    def __init__(self):
        self._jobs: list[JobDto] = []

    def get_job(self, job_id: str) -> JobDto:
        for job in self._jobs:
            if job.job_id == job_id:
                return job
        raise ValueError(f"Job with id {job_id} not found")

    def get_jobs(self, run_id: str) -> list[JobDto]:
        return [job for job in self._jobs if job.run_id == run_id]

    def insert_job(self, job_dto: JobDto):
        self._jobs.append(job_dto)

    def insert_jobs(self, job_dtos: list[JobDto]):
        self._jobs.extend(job_dtos)

    def get_all_aggregation_job_predaccessors(self, run_id: str) -> list[JobDto]:
        aggregation_jobs = [
            job for job in self._jobs 
            if job.run_id == run_id and job.exec_type.value == "aggregation"
        ]
        predaccessor_ids: set[str] = set()
        for agg_job in aggregation_jobs:
            predaccessor_ids.update(agg_job.predaccessors)
        return [job for job in self._jobs if job.job_id in predaccessor_ids]

    def get_all_successors(self, job_id: str) -> list[JobDto]:
        job = self.get_job(job_id)
        return [j for j in self._jobs if j.job_id in job.successors]

    def get_all_leaves(self, run_id: str) -> list[JobDto]:
        return [
            job for job in self._jobs 
            if job.run_id == run_id and len(job.predaccessors) == 0
        ]

    def update_status(self, job_id: str, status: JobStatus):
        for job in self._jobs:
            if job.job_id == job_id:
                job.job_state = status
                return
        raise ValueError(f"Job with id {job_id} not found")
from uuid import uuid4

from service.models.aircraft_daily_sequence_dto import DailySequenceDto
from service.models.job import ExecType, JobDto, JobStatus


def initialize_job_with_sequence_data(run_id: str, sequence: DailySequenceDto) -> JobDto:
    job = JobDto(
        run_id=run_id,
        job_id=uuid4().hex,
        status=JobStatus.PENDING,
        exec_type=None,
        route_index=None,
        payload={"sequence_id": sequence.id},
        # exec_type: ExecType
        # successors: list[str]
        # predaccessors: list[str]
        # job_arguments: dict
        # job_state: JobStatus = JobStatus.PENDING
    )
    return job


def sequences_to_jobs(run_id: str, sequences: list[DailySequenceDto]) -> list[JobDto]:
    jobs: list[JobDto] = []

    # Map first job
    is_first = True
    for sequence in sequences:
        if is_first:
            job = initialize_job_with_sequence_data(run_id, sequence)
            job.exec_type = ExecType.FIRST
            job.status = JobStatus.PENDING

            jobs.append(job)
            is_first = False
            continue

    # Map intermediate jobs

    # Map last jobs

    return [initialize_job_with_sequence_data(run_id, sequence) for sequence in sequences]

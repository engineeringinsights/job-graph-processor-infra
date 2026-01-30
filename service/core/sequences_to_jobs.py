from service.models.job import JobDto, JobStatus    
from service.models.aircraft_daily_sequence_dto import DailySequenceDto

def sequences_to_jobs(sequences: list[DailySequenceDto]) -> list[JobDto]:
    return []

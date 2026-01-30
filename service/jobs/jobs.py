from service.models.job import JobDto
from service.dal.container import s3_for_models
from service.core.delay_modelling import model_departure_delays, merge_percentiles

def proces_first_job(job_dto):
    job = # from args
    
    da = s3_for_models(model_id)
    departure_model = da.model_data_access.get_departure_model(airport_iata)
    departure_delays = model_departure_delays(departure_model, take_off_time, ...)
    da.delay_data_access.store_delays(delays, run_id, job_Id)

def process_merge(job_dto: JobDto):
    da = s3_for_models(model_id)
    
    percentiles = []
    for predaccessor in job_dto.predaccessors:
        p = da.percentiles_access.get_percentiles(dto.run_id, predaccessor)
        percentiles.append(p)
    merged = merge_percentiles(percentiles)
    da.merged_percentiles_data_access.store_merged_percentiles(dto.run_id, merged)


def process_job(dto: JobDto) -> JobDto:
    if dto.exec_type == ExecType.FIrST:
        iata = dto.job_arguments["airport_iata"]
        process_first_job(dto.job_arguments)
        
from service.dal.container import s3_for_models
from service.core.sequences_to_jobs import sequences_to_jobs
from service.jobs.jobs import process_job

MODEL_ID = 1

def main(sequences: list, run_id: str) -> dict:
    
    jobs = sequences_to_jobs(run_id, sequences)
    data_access = s3_for_models(MODEL_ID)
    data_access.job_data_access.insert_jobs(jobs)
    
    leaves = data_access.job_data_access.get_all_leaves(run_id)
    
    for job in leaves:
        process_job(job)
        data_access.jobs_data_access.update_status(job.job_id, JobStatus.DONE)
        
    done = False
    while not done:
        data_access.jobs_data_access.
        
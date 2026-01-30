import pytest

from service.dal.in_memory import JobDataAccessInMemory
from service.models.job import ExecType, JobDto, JobStatus


@pytest.fixture
def job_data_access():
    return JobDataAccessInMemory()


@pytest.fixture
def sample_job():
    return JobDto(
        run_id="run-1",
        job_id="job-1",
        exec_type=ExecType.FIRST,
        successors=["job-2"],
        predaccessors=[],
        job_arguments={"arg1": "value1"},
    )


class TestJobDataAccessInMemory:
    def test_insert_and_get_job(self, job_data_access, sample_job):
        job_data_access.insert_job(sample_job)
        retrieved = job_data_access.get_job("job-1")
        assert retrieved.job_id == "job-1"
        assert retrieved.run_id == "run-1"

    def test_get_job_not_found(self, job_data_access):
        with pytest.raises(ValueError, match="Job with id nonexistent not found"):
            job_data_access.get_job("nonexistent")

    def test_get_jobs_by_run_id(self, job_data_access):
        job1 = JobDto(
            run_id="run-1",
            job_id="job-1",
            exec_type=ExecType.FIRST,
            successors=[],
            predaccessors=[],
            job_arguments={},
        )
        job2 = JobDto(
            run_id="run-1",
            job_id="job-2",
            exec_type=ExecType.INTERMEDIATE,
            successors=[],
            predaccessors=[],
            job_arguments={},
        )
        job3 = JobDto(
            run_id="run-2",
            job_id="job-3",
            exec_type=ExecType.LAST,
            successors=[],
            predaccessors=[],
            job_arguments={},
        )
        job_data_access.insert_jobs([job1, job2, job3])
        
        run1_jobs = job_data_access.get_jobs("run-1")
        assert len(run1_jobs) == 2
        assert all(j.run_id == "run-1" for j in run1_jobs)

    def test_insert_jobs_batch(self, job_data_access):
        jobs = [
            JobDto(
                run_id="run-1",
                job_id=f"job-{i}",
                exec_type=ExecType.FIRST,
                successors=[],
                predaccessors=[],
                job_arguments={},
            )
            for i in range(5)
        ]
        job_data_access.insert_jobs(jobs)
        assert len(job_data_access.get_jobs("run-1")) == 5

    def test_get_all_aggregation_job_predaccessors(self, job_data_access):
        leaf1 = JobDto(
            run_id="run-1",
            job_id="leaf-1",
            exec_type=ExecType.LAST,
            successors=["agg-1"],
            predaccessors=[],
            job_arguments={},
        )
        leaf2 = JobDto(
            run_id="run-1",
            job_id="leaf-2",
            exec_type=ExecType.LAST,
            successors=["agg-1"],
            predaccessors=[],
            job_arguments={},
        )
        agg_job = JobDto(
            run_id="run-1",
            job_id="agg-1",
            exec_type=ExecType.AGGREGATION,
            successors=[],
            predaccessors=["leaf-1", "leaf-2"],
            job_arguments={},
        )
        job_data_access.insert_jobs([leaf1, leaf2, agg_job])
        
        predaccessors = job_data_access.get_all_aggregation_job_predaccessors("run-1")
        assert len(predaccessors) == 2
        pred_ids = {p.job_id for p in predaccessors}
        assert pred_ids == {"leaf-1", "leaf-2"}

    def test_get_all_successors(self, job_data_access):
        job1 = JobDto(
            run_id="run-1",
            job_id="job-1",
            exec_type=ExecType.FIRST,
            successors=["job-2", "job-3"],
            predaccessors=[],
            job_arguments={},
        )
        job2 = JobDto(
            run_id="run-1",
            job_id="job-2",
            exec_type=ExecType.INTERMEDIATE,
            successors=[],
            predaccessors=["job-1"],
            job_arguments={},
        )
        job3 = JobDto(
            run_id="run-1",
            job_id="job-3",
            exec_type=ExecType.LAST,
            successors=[],
            predaccessors=["job-1"],
            job_arguments={},
        )
        job_data_access.insert_jobs([job1, job2, job3])
        
        successors = job_data_access.get_all_successors("job-1")
        assert len(successors) == 2
        succ_ids = {s.job_id for s in successors}
        assert succ_ids == {"job-2", "job-3"}

    def test_get_all_leaves(self, job_data_access):
        job1 = JobDto(
            run_id="run-1",
            job_id="job-1",
            exec_type=ExecType.FIRST,
            successors=["job-2"],
            predaccessors=[],
            job_arguments={},
        )
        job2 = JobDto(
            run_id="run-1",
            job_id="job-2",
            exec_type=ExecType.LAST,
            successors=[],
            predaccessors=["job-1"],
            job_arguments={},
        )
        job3 = JobDto(
            run_id="run-1",
            job_id="job-3",
            exec_type=ExecType.AGGREGATION,
            successors=[],
            predaccessors=["job-2"],
            job_arguments={},
        )
        job_data_access.insert_jobs([job1, job2, job3])
        
        leaves = job_data_access.get_all_leaves("run-1")
        assert len(leaves) == 1
        leaf_ids = {leaf.job_id for leaf in leaves}
        assert leaf_ids == {"job-1"}

    def test_update_status(self, job_data_access, sample_job):
        job_data_access.insert_job(sample_job)
        assert job_data_access.get_job("job-1").job_state == JobStatus.PENDING
        
        job_data_access.update_status("job-1", JobStatus.IN_PROGRESS)
        assert job_data_access.get_job("job-1").job_state == JobStatus.IN_PROGRESS
        
        job_data_access.update_status("job-1", JobStatus.DONE)
        assert job_data_access.get_job("job-1").job_state == JobStatus.DONE

    def test_update_status_not_found(self, job_data_access):
        with pytest.raises(ValueError, match="Job with id nonexistent not found"):
            job_data_access.update_status("nonexistent", JobStatus.DONE)

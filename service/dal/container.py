import os

from constants import PROJECT_ROOT
from service.dal.interface import DataAccess
from service.dal.local_disk import (
    DelayLocalDiskDataAccess,
    PercentileslLocalDiskDataAccess,
    SequenceLocalDiskDataAccess,
)
from service.dal.s3 import ModelS3DataAccess

# Get the absolute path to data directory
LOCAL_PATH = os.path.join(PROJECT_ROOT, "data_generators", "airline_delay", "data")
from constants import S3_BUCKET


def s3_for_models(model_id: int):
    return DataAccess(
        model_data_access=ModelS3DataAccess(
            bucket=S3_BUCKET,
            prefix="data",
            model_id=model_id,
        ),
        percentiles_access=PercentileslLocalDiskDataAccess(path=LOCAL_PATH),
        delay_data_access=DelayLocalDiskDataAccess(path=LOCAL_PATH),
        sequence_data_access=SequenceLocalDiskDataAccess(path=LOCAL_PATH),
    )

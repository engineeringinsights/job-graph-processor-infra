import os

from constants import PROJECT_ROOT
from service.dal.interface import DataAccess
from service.dal.s3 import DelayDataS3Access, ModelS3DataAccess, PercentilesS3DataAccess, SequenceS3DataAccess

BUCKET_NAME = os.environ["BUCKET_NAME"]

# Get the absolute path to data directory
LOCAL_PATH = os.path.join(PROJECT_ROOT, "data_generators", "airline_delay", "data")


def s3_for_models(model_id: int):
    return DataAccess(
        model_data_access=ModelS3DataAccess(
            bucket=BUCKET_NAME,
            prefix="data",
            model_id=model_id,
        ),
        percentiles_access=PercentilesS3DataAccess(bucket=BUCKET_NAME, prefix="data"),
        delay_data_access=DelayDataS3Access(bucket=BUCKET_NAME, prefix="data"),
        sequence_data_access=SequenceS3DataAccess(bucket=BUCKET_NAME, prefix="data"),
    )

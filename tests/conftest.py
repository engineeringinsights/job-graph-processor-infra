import os

# Set environment variables before any imports to disable AWS Lambda Powertools features
# This must be done before importing any service modules that use Tracer/Metrics
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "true")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "test")
os.environ.setdefault("POWERTOOLS_SERVICE_NAME", "test")


def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    Ensures environment variables are set before any service modules are imported.
    """
    os.environ["POWERTOOLS_TRACE_DISABLED"] = "true"
    os.environ["POWERTOOLS_METRICS_NAMESPACE"] = "test"
    os.environ["POWERTOOLS_SERVICE_NAME"] = "test"

"""
CDK constants for performance testing infrastructure.
"""

# Service configuration
SERVICE_NAME = "PerfTesting"
POWERTOOLS_SERVICE_NAME = "POWERTOOLS_SERVICE_NAME"
POWERTOOLS_LOG_LEVEL = "LOG_LEVEL"

# Build paths
SERVICE_BUILD_FOLDER = ".build/service"
LAYER_BUILD_FOLDER = ".build/layer"

# IAM
LAMBDA_BASIC_EXECUTION_ROLE = "AWSLambdaBasicExecutionRole"

# Tag keys for cost allocation
TAG_SCENARIO = "PerfTestScenario"
TAG_TEST_RUN = "PerfTestRun"
TAG_ARCHITECTURE = "Architecture"
TAG_COMPONENT = "Component"

# Scenario identifiers (used for cost allocation tags)
SCENARIO_SQS_LAMBDA_S3 = "sqs-lambda-s3"
SCENARIO_SQS_FARGATE_S3 = "sqs-fargate-s3"  # Future
SCENARIO_STEPFUNCTIONS_LAMBDA_S3 = "stepfunctions-lambda-s3"  # Future
SCENARIO_KINESIS_LAMBDA_S3 = "kinesis-lambda-s3"  # Future

# Lambda configuration
PERF_LAMBDA_MEMORY_SIZE = 256  # MB - adjust for performance testing
PERF_LAMBDA_TIMEOUT = 60  # seconds
PERF_LAMBDA_RESERVED_CONCURRENCY = 10  # Limit concurrency for controlled testing

# SQS configuration
SQS_VISIBILITY_TIMEOUT = 120  # seconds (should be > Lambda timeout)
SQS_BATCH_SIZE = 10  # Messages per Lambda invocation
SQS_MAX_BATCHING_WINDOW = 5  # seconds

# CloudWatch metrics
METRICS_NAMESPACE = "PerfTesting"

# S3 lifecycle
S3_EXPIRATION_DAYS = 7

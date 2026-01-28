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
SCENARIO_SQS_FARGATE_S3 = "sqs-fargate-s3"  # ECS Fargate scenario
SCENARIO_KINESIS_LAMBDA_S3 = "kinesis-lambda-s3"  # Future

# Lambda configuration
PERF_LAMBDA_MEMORY_SIZE = 512  # MB
PERF_LAMBDA_TIMEOUT = 60  # seconds
PERF_LAMBDA_RESERVED_CONCURRENCY = 10  # Limit concurrency for controlled testing

# ECS Fargate configuration
ECS_CPU = 256  # 0.25 vCPU (closest match to Lambda's)
ECS_MEMORY = 512  # MB (matches Lambda memory allocation)

# SQS configuration
SQS_VISIBILITY_TIMEOUT = 120  # seconds (should be > Lambda timeout)
SQS_BATCH_SIZE = 1  # Messages per Lambda invocation (no batching for performance testing)
SQS_MAX_BATCHING_WINDOW = 0  # seconds (disabled batching)

# CloudWatch metrics
METRICS_NAMESPACE = "PerfTesting"

# S3 lifecycle
S3_EXPIRATION_DAYS = 7

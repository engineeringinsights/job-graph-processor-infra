"""
CDK constants for the Lambda DynamoDB service.
"""

# Service configuration
SERVICE_NAME = "MyService"
POWERTOOLS_SERVICE_NAME = "POWERTOOLS_SERVICE_NAME"
POWERTOOLS_LOG_LEVEL = "LOG_LEVEL"

# Lambda configuration
LAMBDA_MEMORY_SIZE = 256  # MB
LAMBDA_TIMEOUT = 30  # seconds
LAMBDA_RUNTIME_PYTHON = "3.13"

# Build paths
SERVICE_BUILD_FOLDER = ".build/service"
LAYER_BUILD_FOLDER = ".build/layer"

# IAM
LAMBDA_BASIC_EXECUTION_ROLE = "AWSLambdaBasicExecutionRole"

# DynamoDB
TABLE_NAME_ENV_VAR = "TABLE_NAME"

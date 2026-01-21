# =============================================================================
# PROJECT CONFIGURATION TEMPLATE
# =============================================================================
# Copy this file to constants.py and fill in your values
# =============================================================================

# Environment-specific AWS account configuration
ENV_CONFIG = {
    "dev": {
        "account": "123456789012",  # Your AWS dev account ID
        "region": "eu-west-1",  # AWS region
    },
    "prod": {
        "account": "123456789013",  # Your AWS prod account ID
        "region": "eu-west-1",  # AWS region
    },
}

# Project prefix used for resource naming (keep short, lowercase, alphanumeric)
PREFIX = "myproject"

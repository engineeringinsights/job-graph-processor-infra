# AWS CDK Lambda DynamoDB Template

A reusable AWS CDK template for deploying serverless applications with:
- Lambda functions with Python 3.13
- DynamoDB table with pk/sk pattern
- Lambda Layer for shared dependencies (aws-lambda-powertools)
- CloudWatch logging with JSON format
- X-Ray tracing
- CDK-nag security checks

## 🚀 Quick Start

### 1. Create New Repository from Template

Click **"Use this template"** button on GitHub, or:
```bash
gh repo create my-new-service --template your-org/cdk-lambda-dynamodb-template
```

### 2. Configure Your Project

Edit `constants.py` with your values:

```python
# constants.py
ENV_CONFIG = {
    "dev": {
        "account": "YOUR_DEV_ACCOUNT_ID",
        "region": "eu-west-1",
    },
    "prod": {
        "account": "YOUR_PROD_ACCOUNT_ID",
        "region": "eu-west-1",
    },
}

PREFIX = "your-project-prefix"  # Used for resource naming
```

### 3. Bootstrap & Install Dependencies

```bash
# Activate your Python 3.13 environment
micromamba activate py313

# Install dependencies and setup project
make bootstrap
```

### 4. Deploy

```bash
# Deploy to dev
make deploy ENV=dev

# Deploy to prod
make deploy ENV=prod
```

## 📁 Project Structure

```
├── app.py                     # CDK app entry point
├── constants.py               # 🔧 CONFIGURE THIS - Environment config
├── cdk/
│   ├── app_stack.py           # Main application stack
│   ├── lambda_dynamodb_construct.py  # Lambda + DynamoDB construct
│   └── constants.py           # CDK constants (timeouts, memory, etc.)
├── service/                   # Lambda handlers (deployed to AWS)
│   ├── handlers/
│   │   ├── create_item.py     # POST handler
│   │   └── get_item.py        # GET handler
│   ├── dal/
│   │   └── dynamodb.py        # Data access layer
│   └── models/
│       └── item.py            # Pydantic/dataclass models
├── layer/                     # Lambda layer dependencies
│   └── requirements.txt       # aws-lambda-powertools, etc.
├── tests/
│   └── unit/                  # Unit tests
├── .github/workflows/         # CI/CD pipelines
├── Makefile                   # Common commands
└── pyproject.toml             # Python dependencies
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AWS Account                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  Lambda Layer                           ││
│  │         (aws-lambda-powertools, boto3)                  ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│           ┌───────────────┴───────────────┐                 │
│           ▼                               ▼                  │
│  ┌─────────────────┐             ┌─────────────────┐        │
│  │  CreateItem     │             │   GetItem       │        │
│  │  Lambda (ARM64) │             │  Lambda (ARM64) │        │
│  └────────┬────────┘             └────────┬────────┘        │
│           │                               │                  │
│           └───────────────┬───────────────┘                 │
│                           ▼                                  │
│              ┌─────────────────────────┐                    │
│              │      DynamoDB Table     │                    │
│              │   (pk/sk, on-demand)    │                    │
│              └─────────────────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Development

### Make Commands

| Command | Description |
|---------|-------------|
| `make bootstrap` | Install all dependencies |
| `make build` | Build Lambda code for deployment |
| `make synth` | Synthesize CloudFormation template |
| `make deploy ENV=dev` | Deploy to dev environment |
| `make destroy-dev` | Destroy dev environment (with confirmation) |
| `make lint` | Run linting checks |
| `make lint-fix` | Auto-fix linting issues |
| `make test-unit` | Run unit tests |
| `make clean` | Clean build artifacts |

### Adding New Lambda Handlers

1. Create handler in `service/handlers/your_handler.py`
2. Add function to `cdk/lambda_dynamodb_construct.py`
3. Grant appropriate DynamoDB permissions

### Modifying the Layer

Edit `layer/requirements.txt` and redeploy. The layer is built automatically during CDK deployment.

## 📦 Dependencies

### CDK Dependencies (pyproject.toml)
- `aws-cdk-lib` - CDK core library
- `aws-cdk-aws-lambda-python-alpha` - Python Lambda layer support
- `cdk-nag` - Security checks

### Lambda Runtime Dependencies (layer/requirements.txt)
- `aws-lambda-powertools` - Logging, tracing, metrics
- `boto3` - AWS SDK

## 🔒 Security

This template includes:
- CDK-nag security checks with AwsSolutionsChecks
- Least-privilege IAM policies
- DynamoDB point-in-time recovery enabled
- CloudWatch log retention policies
- X-Ray tracing enabled

## 📝 License

MIT

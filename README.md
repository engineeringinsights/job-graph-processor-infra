# Job Graph Processor Infrastructure

AWS CDK infrastructure for performance testing job graph processing architectures.

## Overview

This project provides infrastructure for comparing different approaches to processing job graphs - where jobs have dependencies on other jobs and an external scheduler determines execution order.

**Key Concept**: Deploy once, run many tests. Track costs over time using AWS Cost Allocation Tags.

## Scenarios

| Scenario | Stack Name | Description | Status |
|----------|------------|-------------|--------|
| **Scenario 1** | `scenario-1-{env}` | SQS → Lambda → S3 (serverless) | ✅ Available |
| **Scenario 2** | `scenario-2-{env}` | SQS → ECS Fargate → S3 (containers) | ✅ Available |
| Scenario 3 | `scenario-3-{env}` | Step Functions orchestration | 🔜 Coming soon |

## Quick Start

### 1. Configure Environment

Edit `constants.py` with your AWS account details:

```python
ENV_CONFIG = {
    "dev": {
        "account": "YOUR_ACCOUNT_ID",
        "region": "eu-west-1",
    },
}
```

### 2. Bootstrap & Deploy

```bash
# Activate Python environment
micromamba activate py312

# Install dependencies
make bootstrap

# Deploy Scenario 1
make deploy ENV=dev
```

### 3. Run Performance Test

```bash
# Send 1000 test messages
make run MESSAGES=1000 ENV=dev
```

### 4. Track Costs

Use `TEST_RUN_ID` to tag test runs for cost comparison:

```bash
# Deploy with cost tracking tag
TEST_RUN_ID=baseline-256mb make deploy ENV=dev
make run MESSAGES=1000 ENV=dev

# Change configuration and redeploy with new tag
TEST_RUN_ID=test-512mb make deploy ENV=dev
make run MESSAGES=1000 ENV=dev

# Compare costs in AWS Cost Explorer by PerfTestRun tag
```

## Project Structure

```
├── perf_app.py              # CDK app entry point
├── constants.py             # 🔧 CONFIGURE THIS - AWS account config
├── cdk/
│   ├── scenario1_stack.py   # Scenario 1: Lambda + S3
│   ├── scenario2_stack.py   # Scenario 2: ECS Fargate + S3
│   ├── shared/
│   │   └── vpc_stack.py     # Shared VPC (public subnets, no NAT)
│   ├── constants.py         # Stack configuration
│   └── README.md            # Detailed documentation
├── docker/
│   └── Dockerfile           # ECS Fargate container image
├── service/
│   ├── handlers/
│   │   └── processor.py     # Lambda processor
│   ├── container/
│   │   └── processor.py     # ECS Fargate processor
│   └── dal/
│       ├── dynamodb.py      # DynamoDB helper
│       ├── s3.py            # S3 helper
│       └── sqs.py           # SQS helper
├── scripts/
│   └── run_perf_test.py     # Test runner
└── Makefile                 # Build commands
```

## Make Commands

### Scenario 1 (Lambda)

| Command | Description |
|---------|-------------|
| `make deploy ENV=dev` | Deploy Lambda stack |
| `make destroy ENV=dev` | Destroy Lambda stack |
| `make run MESSAGES=N ENV=dev` | Send N test messages |

### Scenario 2 (ECS Fargate)

| Command | Description |
|---------|-------------|
| `make deploy-ecs ENV=dev` | Deploy VPC + ECS stack |
| `make destroy-ecs ENV=dev` | Destroy ECS stack |
| `make scale-up DESIRED_COUNT=2 ENV=dev` | Scale ECS service up |
| `make scale-down ENV=dev` | Scale ECS service to 0 |
| `make ecs-status ENV=dev` | Check ECS service status |
| `make run-ecs MESSAGES=N ENV=dev` | Send N test messages |

### Common

| Command | Description |
|---------|-------------|
| `make bootstrap` | Install dependencies |
| `make synth` | Synthesize CloudFormation |
| `make lint` | Run linting |
| `make test-unit` | Run tests |
| `make help` | Show all commands |

## Documentation

See [cdk/README.md](cdk/README.md) for detailed documentation on:
- Architecture diagrams
- Cost tracking with tags
- Message formats
- Configuration options
- Troubleshooting

## License

MIT

# Job Graph Processor Infrastructure - AI Agent Guide

## Project Architecture

**Core Concept**: Performance testing infrastructure for job graph processing systems where jobs have dependencies and an external scheduler feeds work based on completion status.

```
External Scheduler ──┐
                     ├──> Incoming Queue ──> Lambda Processor ──┬──> Outgoing Queue
                     │                                           │
                     └─────────────────────────────────────────┘
                                                                 ├──> S3 (job details)
                                                                 └──> DynamoDB (metadata)
```

**Deploy Once, Run Many**: Single infrastructure deployment supports multiple test runs tagged with `TEST_RUN_ID` for cost tracking via AWS Cost Allocation Tags.

## Critical Configuration Pattern

**Always configure `constants.py` first** - it's a template requiring AWS account details:

```python
ENV_CONFIG = {
    "dev": {"account": "YOUR_ACCOUNT_ID", "region": "eu-west-1"},
}
PREFIX = "myproject"  # Keep short, lowercase, alphanumeric
```

## Build & Deployment Workflow

### Bootstrap (One-time per environment)
```bash
micromamba activate py312  # Python environment management via micromamba
make bootstrap             # Installs Poetry, CDK, pre-commit, deps
```

**Dependency Management Convention**:
- `pyproject.toml`: Separates Lambda runtime deps from dev/CDK deps
- Lambda deps exported via `poetry export` to `.build/layer/requirements.txt`
- Dev dependencies include CDK constructs, linters, testing tools

### Deploy with Cost Tracking
```bash
TEST_RUN_ID=baseline-256mb make deploy ENV=dev
make run MESSAGES=1000 ENV=dev
```

**Cost Tracking Mechanism**: 
- `TEST_RUN_ID` env var tags ALL resources via `PerfTestRun` tag
- Enables cost comparison in AWS Cost Explorer by filtering on tag values
- Must activate tags in AWS Billing Console (24hr lag before visible)

## CDK Stack Structure

**Stack Naming**: `scenario-1-{env}` (hardcoded pattern in `cdk/scenario1_stack.py`, `scripts/run_perf_test.py`)

**Key Resources Created**:
- Incoming Queue: `scenario-1-{env}-incoming`
- Outgoing Queue: `scenario-1-{env}-outgoing` 
- Lambda: `scenario-1-{env}-processor`
- S3 Bucket: `scenario-1-{env}-data-{account}`
- DynamoDB: `scenario-1-{env}-jobs`

**Lambda Configuration** in `cdk/constants.py`:
```python
PERF_LAMBDA_MEMORY_SIZE = 256  # Adjust for perf testing
PERF_LAMBDA_TIMEOUT = 60
PERF_LAMBDA_RESERVED_CONCURRENCY = 10  # Controlled concurrency
SQS_BATCH_SIZE = 10  # Messages per Lambda invocation
```

## Service Handler Pattern

**Location**: `service/handlers/processor.py`

**AWS Lambda Powertools Integration**:
- Uses `BatchProcessor` for SQS batch handling with partial failure support
- Structured logging via `Logger`, metrics via `Metrics`, tracing via `Tracer`
- Environment variables: `BUCKET_NAME`, `OUTGOING_QUEUE_URL`, `TEST_RUN_ID`

**Job Processing Flow**:
1. Lambda receives batch from Incoming Queue
2. Reads job details from S3 (if `s3_key` provided)
3. Simulates work based on `work_duration_ms` and `data_size_kb`
4. Writes results to S3 with path: `results/{job_id}.json`
5. Sends completion notification to Outgoing Queue

## Testing Patterns

**Unit Tests** (`tests/unit/`):
- Uses `syrupy` for snapshot testing CDK templates
- Fixtures pattern: `app` → `stack` → `template`
- Update snapshots: `make snapshot-update`

**Performance Tests** (`scripts/run_perf_test.py`):
- Fetches queue URL from CloudFormation stack outputs
- Sends messages in batches (max 10 per SQS API call)
- Configurable: `--messages`, `--work-duration-ms`, `--data-size-kb`
- Concurrent senders for high-throughput testing

## Makefile Conventions

**Environment Variables**:
- `ENV` (default: `dev`): Target AWS environment
- `TEST_RUN_ID` (default: `default`): Cost allocation tag value
- `MESSAGES`: Number of test messages to send

**Build Process**:
```bash
make build  # Creates .build/ with service code + layer requirements
make synth  # Builds + generates CloudFormation
make deploy # Builds + deploys stack
```

**CDK Bootstrap Context**: Uses custom qualifier `renre` (see `--toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre"`)

## Linting & Code Quality

**Pre-commit Integration**: Runs on commit via `.pre-commit-config.yaml`

**Tools Stack**:
- `ruff`: Primary linter (replaces flake8, isort, pyupgrade)
- `black`: Code formatting
- `mypy`: Type checking (use `make lint-strict`)
- `bandit`: Security scanning (configured in `pyproject.toml`)

**Configuration**: All tools configured in `pyproject.toml` under `[tool.*]` sections

## Data Models & Business Logic

**Models in `service/models/`**: Uses Pydantic for data validation
- `aircraft_daily_sequence_dto.py`: Route planning models (time-based validation)
- `airport.py`: Airport data structures

**Core Logic in `service/core/`**:
- `delay_modelling.py`: Pandas-based delay calculation (departure/landing scenarios)
- Aggregates events grouped by `scenario_id`, computes delay metrics

## DAL (Data Access Layer) Pattern

**Location**: `service/dal/` - Abstraction over AWS services

**Handlers**:
- `s3.py`: `S3Handler` with methods for `get_object`, `put_object`
- `sqs.py`: `SQSHandler` for queue operations
- `dynamodb.py`: DynamoDB helper utilities

**Usage Pattern**: Initialize handlers at module level in Lambda for reuse across invocations

## Future Scenarios (Placeholder Structure)

**Scenario 2**: SQS → ECS (containers) - coming soon
**Scenario 3**: Step Functions orchestration - coming soon

When adding scenarios, follow pattern:
1. Create `cdk/scenario{N}_stack.py`
2. Add scenario constant to `cdk/constants.py`
3. Update `perf_app.py` to deploy new stack
4. Add Makefile target for scenario-specific deployment

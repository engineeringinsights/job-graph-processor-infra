# Performance Testing Infrastructure

## Overview

This module provides infrastructure for performance testing a **job graph processor**. Jobs have dependencies on other jobs, and an external scheduler determines which jobs can run based on completed dependencies.

**Key Concept**: Deploy once, run many tests. Track costs over time using AWS Cost Allocation Tags.

## Scenarios

| Scenario | Stack Name | Description |
|----------|------------|-------------|
| **Scenario 1** | `scenario-1-{env}` | SQS → Lambda → S3 (serverless, event-driven) |
| Scenario 2 | `scenario-2-{env}` | SQS → ECS → S3 (container-based) - *coming soon* |
| Scenario 3 | `scenario-3-{env}` | Step Functions orchestration - *coming soon* |

## Scenario 1 Architecture (Lambda + S3)

```
┌────────────────────┐
│  External          │
│  Scheduler         │◄───────────────────────────────────┐
│  (feeds jobs based │                                    │
│   on dependencies) │                                    │
└────────┬───────────┘                                    │
         │                                                │
         ▼                                                │
┌─────────────────┐     ┌─────────────────┐     ┌─────────┴───────┐
│    Incoming     │────▶│     Lambda      │────▶│    Outgoing     │
│     Queue       │     │    Processor    │     │     Queue       │
│  (jobs to run)  │     │                 │     │ (completed jobs)│
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────┐    ┌─────────────┐
               │     S3      │    │  DynamoDB   │
               │(job details)│    │(job metadata)│
               └─────────────┘    └─────────────┘
```

### Flow

1. **External Scheduler** reads completed jobs from **Outgoing Queue**
2. Scheduler determines which jobs can now run (dependencies satisfied)
3. Scheduler sends ready jobs to **Incoming Queue**
4. **Lambda Processor** picks up jobs, processes them
5. Processor writes results to **S3** and sends completion to **Outgoing Queue**
6. Repeat until all jobs in the graph are complete

### Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| Incoming Queue | `scenario-1-{env}-incoming` | Jobs waiting to be processed |
| Outgoing Queue | `scenario-1-{env}-outgoing` | Completed job notifications |
| DLQ | `scenario-1-{env}-dlq` | Failed jobs |
| Lambda | `scenario-1-{env}-processor` | Processes jobs |
| S3 Bucket | `scenario-1-{env}-data-{account}` | Job details storage |
| DynamoDB Table | `scenario-1-{env}-jobs` | Job metadata (accessible by Lambda and scheduler) |

## Cost Tracking with Tags

All resources are tagged with `PerfTestRun` which you set via the `TEST_RUN_ID` environment variable.

### How It Works

1. **Deploy with a tag**: `TEST_RUN_ID=baseline-256mb make deploy`
2. **Run your test**: `make run MESSAGES=1000`
3. **Update tag for next test**: `TEST_RUN_ID=test-512mb make deploy`
4. **Run another test**: `make run MESSAGES=1000`
5. **Compare costs in AWS Cost Explorer** by filtering on `PerfTestRun` tag

### Activating Cost Allocation Tags

Before you can filter by tags in Cost Explorer:

1. Go to **AWS Billing Console** → **Cost Allocation Tags**
2. Find and activate `PerfTestRun` tag
3. Wait ~24 hours for tags to appear in Cost Explorer

### Tags Applied

| Tag | Value | Purpose |
|-----|-------|---------|
| `PerfTestRun` | From `TEST_RUN_ID` env var | Identify test run for cost tracking |
| `Purpose` | `PerformanceTesting` | Filter all perf testing resources |
| `Environment` | `dev` or `prod` | Environment separation |
| `Project` | From `constants.PREFIX` | Project identification |

## Usage

### Prerequisites

```bash
# Bootstrap the project (if not done)
make bootstrap

# Ensure AWS credentials are configured
aws sts get-caller-identity
```

### Deploy Infrastructure

```bash
# Deploy with default tag
make deploy ENV=dev

# Deploy with custom test run ID (for cost tracking)
TEST_RUN_ID=baseline-001 make deploy ENV=dev
```

### Run Performance Tests

```bash
# Send 100 messages (default)
make run MESSAGES=100 ENV=dev

# Send 1000 messages
make run MESSAGES=1000 ENV=dev

# Advanced: customize workload
poetry run python scripts/run_perf_test.py \
    --messages 1000 \
    --work-duration-ms 200 \
    --data-size-kb 50 \
    --env dev
```

### Monitor Results

- **CloudWatch Metrics**: Namespace `PerfTesting`
  - `ProcessingTimeMs` - Time to process each job
  - `JobsCompleted` - Count of completed jobs
  - Dimension: `TestRunId` to filter by test run

- **Lambda Metrics**: Standard AWS/Lambda metrics
  - Duration, Invocations, Errors, ConcurrentExecutions

- **SQS Metrics**: Standard AWS/SQS metrics
  - Incoming queue depth, outgoing queue depth, message age

### Clean Up

```bash
make destroy ENV=dev
```

## Message Formats

### Incoming Queue (jobs to process)

```json
{
    "job_id": "unique-id",           // Required: unique job identifier
    "work_duration_ms": 100,         // Simulated processing time (ms)
    "data_size_kb": 10,              // Size of output data to generate (KB)
    "input_key": "jobs/job-123.json" // Optional: S3 key with job details
}
```

### Outgoing Queue (completed jobs)

```json
{
    "job_id": "unique-id",
    "status": "completed",
    "output_key": "output/2026/01/21/12/unique-id.json",
    "processing_time_ms": 105.2,
    "completed_at": "2026-01-21T12:34:56.789Z",
    "test_run_id": "baseline-001"
}
```

The external scheduler reads these completion messages to determine which dependent jobs can now run.

## Configuration

### Lambda Settings

Edit `cdk/constants.py`:

```python
PERF_LAMBDA_MEMORY_SIZE = 256          # MB
PERF_LAMBDA_TIMEOUT = 60               # seconds
SQS_BATCH_SIZE = 10                    # Messages per Lambda invocation
```

### Stack Parameters

You can also pass parameters when creating the stack in `perf_app.py`:

```python
Scenario1Stack(
    app,
    "scenario-1-dev",
    stage="dev",
    test_run_id="my-test",
    lambda_memory_size=512,      # Override memory
    lambda_timeout=120,          # Override timeout
    batch_size=5,                # Override batch size
    env=environment,
)
```

## File Structure

```
cdk/                             # CDK infrastructure
├── __init__.py
├── constants.py                 # Configuration constants
├── scenario1_stack.py           # Scenario 1 stack definition
└── README.md                    # This file

service/                         # Lambda code
├── handlers/
│   └── processor.py             # SQS message handler
└── dal/
    ├── dynamodb.py              # DynamoDB helper
    ├── s3.py                    # S3 read/write helper
    └── sqs.py                   # SQS send helper

scripts/
└── run_perf_test.py             # Test runner script
```

## Example Workflow: Compare Memory Configurations

```bash
# 1. Deploy with 256MB memory (edit constants.py or pass to stack)
TEST_RUN_ID=memory-256mb make deploy ENV=dev

# 2. Run test
make run MESSAGES=5000 ENV=dev

# 3. Wait for processing to complete, note the time

# 4. Change memory to 512MB in constants.py
# 5. Deploy with new tag
TEST_RUN_ID=memory-512mb make deploy ENV=dev

# 6. Run same test
make run MESSAGES=5000 ENV=dev

# 7. Compare in Cost Explorer:
#    - Filter by Tag: PerfTestRun
#    - Group by: PerfTestRun
#    - View costs for memory-256mb vs memory-512mb
```

## Troubleshooting

### Messages not processing?
- Check DLQ for failed messages
- Check Lambda CloudWatch logs: `/aws/lambda/perf-testing-{env}-processor`

### Can't see costs by tag?
- Ensure tag is activated in Billing Console
- Wait 24 hours after activation
- Costs only appear after resources incur charges

### Stack deployment fails?
- Run `make synth` first to validate
- Check for CDK bootstrap: `cdk bootstrap`

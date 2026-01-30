# Performance Testing Infrastructure

## Overview

This module provides infrastructure for performance testing a **job graph processor**. Jobs have dependencies on other jobs, and an external scheduler determines which jobs can run based on completed dependencies.

**Key Concept**: Deploy once, run many tests. Track costs over time using AWS Cost Allocation Tags.

## Scenarios

| Scenario | Stack Name | Description |
|----------|------------|-------------|
| **Scenario 1** | `scenario-1-{env}` | SQS → Lambda → S3 (serverless, event-driven) |
| **Scenario 2** | `scenario-2-{env}` | SQS → ECS Fargate → S3 (container-based) |
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
| DynamoDB Table | `scenario-1-{env}-jobs` | Job metadata |

## Scenario 2 Architecture (ECS Fargate + S3)

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
│    Incoming     │────▶│  ECS Fargate    │────▶│    Outgoing     │
│     Queue       │     │   (polling)     │     │     Queue       │
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

### Key Differences from Scenario 1

| Aspect | Scenario 1 (Lambda) | Scenario 2 (ECS Fargate) |
|--------|---------------------|--------------------------|
| **Triggering** | Event-driven (SQS triggers Lambda) | Polling (container polls SQS) |
| **Scaling** | Automatic (Lambda concurrency) | Manual (`make scale-up/down`) |
| **Idle behavior** | No cost when idle | Runs until manual scale-down |
| **Cold start** | ~100-500ms | ~30-60s (container startup) |
| **Max runtime** | 15 minutes | Unlimited |
| **VPC** | Optional | Required (public subnet) |

### Flow

1. **Scale up** the ECS service: `make scale-up DESIRED_COUNT=2 ENV=dev`
2. **Fargate tasks** start and poll the **Incoming Queue**
3. Tasks process messages, write to **S3**, send completion to **Outgoing Queue**
4. **Scale down** when done: `make scale-down ENV=dev`

### Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| VPC | `perf-shared-{env}-vpc` | Public subnets only (no NAT) |
| ECS Cluster | `scenario-2-{env}-cluster` | Fargate cluster |
| ECS Service | `scenario-2-{env}-service` | Service with desired_count=0 |
| Task Definition | `scenario-2-{env}-processor` | Container config |
| ECR Image | (auto-built by CDK) | Docker image from `docker/Dockerfile` |
| Incoming Queue | `scenario-2-{env}-incoming` | Jobs waiting to be processed |
| Outgoing Queue | `scenario-2-{env}-outgoing` | Completed job notifications |
| DLQ | `scenario-2-{env}-dlq` | Failed jobs |
| S3 Bucket | `scenario-2-{env}-data-{account}` | Job details storage |
| DynamoDB Table | `scenario-2-{env}-jobs` | Job metadata |

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

### Scenario 1: Deploy Lambda Infrastructure

```bash
# Deploy with default tag
make deploy ENV=dev

# Deploy with custom test run ID (for cost tracking)
TEST_RUN_ID=baseline-001 make deploy ENV=dev

# Run performance test
make run MESSAGES=1000 ENV=dev

# Destroy when done
make destroy ENV=dev
```

### Scenario 2: Deploy ECS Fargate Infrastructure

```bash
# Deploy VPC + ECS stack
make deploy-ecs ENV=dev

# Scale up to start processing (starts with 0 tasks)
make scale-up DESIRED_COUNT=2 ENV=dev

# Check service status
make ecs-status ENV=dev

# Run performance test
make run-ecs MESSAGES=1000 ENV=dev

# Scale down when done
make scale-down ENV=dev

# Destroy when done
make destroy-ecs ENV=dev
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

### Lambda Settings (Scenario 1)

Edit `cdk/constants.py`:

```python
PERF_LAMBDA_MEMORY_SIZE = 256          # MB
PERF_LAMBDA_TIMEOUT = 60               # seconds
SQS_BATCH_SIZE = 10                    # Messages per Lambda invocation
```

### ECS Fargate Settings (Scenario 2)

Edit `cdk/constants.py`:

```python
ECS_CPU = 256                          # 0.25 vCPU (256, 512, 1024, 2048, 4096)
ECS_MEMORY = 512                       # MB (must match CPU)
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

Scenario2Stack(
    app,
    "scenario-2-dev",
    stage="dev",
    vpc=vpc_stack.vpc,
    test_run_id="my-test",
    cpu=512,                     # Override CPU
    memory=1024,                 # Override memory
    desired_count=0,             # Start with 0 tasks
    env=environment,
)
```

## File Structure

```
cdk/                             # CDK infrastructure
├── __init__.py
├── constants.py                 # Configuration constants
├── scenario1_stack.py           # Scenario 1: Lambda + S3
├── scenario2_stack.py           # Scenario 2: ECS Fargate + S3
├── shared/
│   └── vpc_stack.py             # Shared VPC (public subnets)
└── README.md                    # This file

docker/
└── Dockerfile                   # ECS Fargate container image

service/
├── handlers/
│   └── processor.py             # Lambda handler (Powertools)
├── container/
│   └── processor.py             # ECS Fargate processor (structlog)
└── dal/
    ├── dynamodb.py              # DynamoDB helper
    ├── s3.py                    # S3 read/write helper
    └── sqs.py                   # SQS send helper

scripts/
└── run_perf_test.py             # Test runner script (--scenario 1|2)
```

### Result Folder structure on multiple runs

We want to solve same job graph using multiple implementations. That means we will have multiple RUNs, in which every RUN will have multiple JOBs with corresponding JOB IDs.

The folder structure organizes results by `run_id` (top level), then by result type:

```
<run_id>/                                    # Top-level folder for a given test run
├── delays/
│   └── <job_id>.parquet                    # Delay data for each job
├── percentiles/
│   └── <sequence_id>.json                  # Percentiles for each sequence
└── merged_percentiles.json             # Final aggregated results for entire run
```

#### Data Access Layer Classes

**S3 Implementation** (`service/dal/s3.py`):
- `DelayDataS3Access`: Stores/retrieves delay parquet files
  - Path pattern: `<prefix>/<run_id>/delays/<job_id>.parquet`
  - Methods: `store_delays(delays, run_id, job_id)`, `get_delays(run_id, job_id)`

- `PercentilesS3DataAccess`: Stores/retrieves percentile JSON files per sequence
  - Path pattern: `<prefix>/<run_id>/percentiles/<sequence_id>.json`
  - Methods: `store_percentiles(run_id, sequence_id, percentile)`, `get_percentiles(run_id, sequence_id)`

- `MergedPercentilesS3DataAccess`: Stores/retrieves final aggregated percentiles
  - Path pattern: `<prefix>/<run_id>/merged_percentiles/merged_percentiles.json`
  - Methods: `store_merged_percentiles(run_id, percentile)`, `get_merged_percentiles(run_id)`
  - Note: Single file per run_id, aggregates all sequence results

**Local Disk Implementation** (`service/dal/local_disk.py`):
- `DelayLocalDiskDataAccess`: Mirrors S3 structure on local filesystem
  - Path pattern: `<path>/<run_id>/delays/<job_id>.parquet`

- `PercentileslLocalDiskDataAccess`: Mirrors S3 percentiles structure
  - Path pattern: `<path>/<run_id>/percentiles/<sequence_id>.json`

- `MergedPercentilesLocalDiskDataAccess`: Mirrors S3 merged percentiles structure
  - Path pattern: `<path>/<run_id>/merged_percentiles/merged_percentiles.json`

#### Key Concepts

- **`run_id`**: Identifies a complete test run (e.g., "baseline-256mb", "optimized-512mb")
- **`job_id`**: Unique identifier for each job in the test run
- **`sequence_id`**: Identifies a specific aircraft daily sequence

The simplified structure enables efficient storage and retrieval of results, with job_id providing unique identification for delay data and sequence_id organizing percentile results.

## Aircraft Daily Sequence Generator

The `generate_aircraft_daily_sequences` function creates realistic daily flight sequences for aircraft with the following constraints:

- **Start time**: Gate opens at home airport between 00:05 and 02:00
- **Takeoff timing**: Occurs 80-110 minutes after gate opens
- **Flight duration**: Calculated using haversine distance between airports with average speed of 800 km/h
- **Turnaround time**: Next gate opens 10-40 minutes after landing
- **Daily flights**: Aircraft performs 2-8 flights per day
- **End of day**: Aircraft returns to home airport with last landing after 16:00
- **Maintenance window**: Aircraft must land back at home airport before 23:00 on the same day

The generator uses the `calculate_flight_duration` method to compute realistic flight times based on geographic coordinates.

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

### Messages not processing? (Scenario 1 - Lambda)
- Check DLQ for failed messages
- Check Lambda CloudWatch logs: `/aws/lambda/scenario-1-{env}-processor`

### Messages not processing? (Scenario 2 - ECS)
- Ensure service is scaled up: `make ecs-status ENV=dev`
- Scale up if needed: `make scale-up DESIRED_COUNT=1 ENV=dev`
- Check ECS CloudWatch logs: `/ecs/scenario-2-{env}-processor`

### ECS tasks not starting?
- Check ECS service events: AWS Console → ECS → Clusters → scenario-2-{env}-cluster
- Verify public IP assignment and internet access
- Check security group allows outbound traffic

### Can't see costs by tag?
- Ensure tag is activated in Billing Console
- Wait 24 hours after activation
- Costs only appear after resources incur charges

### Stack deployment fails?
- Run `make synth` first to validate
- Check for CDK bootstrap: `cdk bootstrap`

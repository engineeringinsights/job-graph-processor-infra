"""
Performance testing CDK app.

Deploys infrastructure for performance testing job graph processing:
- Scenario 1: SQS → Lambda → S3 (serverless)
- Scenario 2: SQS → ECS Fargate → S3 (containers)

Use TEST_RUN_ID to tag different test runs for cost tracking.

Usage:
    # Deploy Scenario 1 (Lambda)
    cdk deploy scenario-1-dev --app "python perf_app.py"

    # Deploy Scenario 2 (ECS) - includes shared VPC
    cdk deploy perf-shared-dev scenario-2-dev --app "python perf_app.py"

    # Update tag for a new test run
    TEST_RUN_ID=baseline-001 cdk deploy scenario-1-dev --app "python perf_app.py"
"""

import os

from aws_cdk import App, Aspects, Environment, Tags
from cdk_nag import AwsSolutionsChecks

from cdk.scenario1_stack import Scenario1Stack
from cdk.scenario2_stack import Scenario2Stack
from cdk.shared.vpc_stack import SharedVpcStack
from constants import ENV_CONFIG, PREFIX

app = App()

# Get configuration
stage = os.getenv("ENV", "dev")
test_run_id = os.getenv("TEST_RUN_ID")
config = ENV_CONFIG.get(stage)

if config is None:
    raise ValueError(f"Environment '{stage}' is not defined in constants.py")

environment = Environment(account=config["account"], region=config["region"])

# =============================================================================
# Shared Infrastructure
# =============================================================================
vpc_stack = SharedVpcStack(
    app,
    f"perf-shared-{stage}",
    stage=stage,
    env=environment,
    description="Shared VPC for performance testing (public subnets only)",
)

# =============================================================================
# Scenario 1: Lambda + S3
# =============================================================================
scenario1_stack = Scenario1Stack(
    app,
    f"scenario-1-{stage}",
    stage=stage,
    test_run_id=test_run_id,
    env=environment,
    description="Scenario 1: Lambda + S3 job processor (SQS -> Lambda -> S3)",
)

# =============================================================================
# Scenario 2: ECS Fargate + S3
# =============================================================================
scenario2_stack = Scenario2Stack(
    app,
    f"scenario-2-{stage}",
    stage=stage,
    vpc=vpc_stack.vpc,
    test_run_id=test_run_id,
    env=environment,
    description="Scenario 2: ECS Fargate + S3 job processor (SQS -> ECS -> S3)",
)
scenario2_stack.add_dependency(vpc_stack)

# Global tags
Tags.of(app).add("Project", PREFIX)
Tags.of(app).add("ManagedBy", "CDK")

Aspects.of(app).add(AwsSolutionsChecks())

app.synth()

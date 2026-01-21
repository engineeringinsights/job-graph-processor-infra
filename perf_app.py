"""
Performance testing CDK app.

Deploys shared infrastructure (SQS → Lambda → S3) for performance testing.
Use TEST_RUN_ID to tag different test runs for cost tracking.

Usage:
    # Deploy infrastructure
    cdk deploy perf-testing-dev --app "python perf_app.py"

    # Update tag for a new test run (updates the TEST_RUN_ID tag on all resources)
    TEST_RUN_ID=baseline-001 cdk deploy perf-testing-dev --app "python perf_app.py"
"""

import os

from aws_cdk import App, Aspects, Environment, Tags
from cdk_nag import AwsSolutionsChecks

from cdk.scenario1_stack import Scenario1Stack
from constants import ENV_CONFIG, PREFIX

app = App()

# Get configuration
stage = os.getenv("ENV", "dev")
test_run_id = os.getenv("TEST_RUN_ID")
config = ENV_CONFIG.get(stage)

if config is None:
    raise ValueError(f"Environment '{stage}' is not defined in constants.py")

environment = Environment(account=config["account"], region=config["region"])

# Deploy performance testing infrastructure
perf_stack = Scenario1Stack(
    app,
    f"scenario-1-{stage}",
    stage=stage,
    test_run_id=test_run_id,
    env=environment,
    description="Scenario 1: Lambda + S3 job processor (SQS -> Lambda -> S3)",
)

# Global tags
Tags.of(app).add("Project", PREFIX)
Tags.of(app).add("ManagedBy", "CDK")

Aspects.of(app).add(AwsSolutionsChecks())

app.synth()

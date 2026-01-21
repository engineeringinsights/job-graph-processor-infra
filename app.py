import os

from aws_cdk import App, Aspects, Environment, Tags
from cdk_nag import AwsSolutionsChecks

from cdk.app_stack import AppStack
from constants import ENV_CONFIG, PREFIX

app = App()

stage = os.getenv("ENV", "dev")
config = ENV_CONFIG.get(stage)

# Ensure config exists for the specified environment
if config is None:
    raise ValueError(f"Environment '{stage}' is not defined in constants.py")

# Define the environment
account = config["account"]
region = config["region"]

environment = Environment(account=account, region=region)

# Create the main application stack
app_stack = AppStack(
    app,
    f"app-{stage}",
    stage=stage,
    table_name=PREFIX,
    env=environment,
)

# Add tags to all resources
Tags.of(app).add("Environment", stage)
Tags.of(app).add("Project", PREFIX)

# Add cdk-nag checks
Aspects.of(app).add(AwsSolutionsChecks())

app.synth()

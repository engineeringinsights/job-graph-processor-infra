"""
Lambda DynamoDB Construct.

A construct that creates Lambda functions with a shared layer and DynamoDB table,
following AWS best practices from the Lambda handler cookbook pattern.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from cdk_nag import NagSuppressions
from constructs import Construct

from cdk import constants


class LambdaDynamoDBConstruct(Construct):
    """
    A construct that creates Lambda functions with a DynamoDB table.

    Features:
    - DynamoDB table with pk/sk pattern
    - Lambda layer for shared dependencies (aws-lambda-powertools, boto3)
    - Create and Get Lambda handlers
    - Proper IAM permissions
    - CloudWatch log groups with retention
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        stage: str,
        table_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.stage = stage
        self.table_name = table_name

        # Create DynamoDB table
        self.table = self._create_table()

        # Create Lambda layer with shared dependencies
        self.layer = self._create_layer()

        # Create Lambda role
        self.lambda_role = self._create_lambda_role()

        # Create Lambda functions
        self.create_function = self._create_lambda_function(
            function_id="CreateItem",
            handler="service.handlers.create_item.handler",
            description="Creates items in DynamoDB",
        )

        self.get_function = self._create_lambda_function(
            function_id="GetItem",
            handler="service.handlers.get_item.handler",
            description="Gets items from DynamoDB",
        )

        # Grant DynamoDB permissions
        self.table.grant_read_write_data(self.create_function)
        self.table.grant_read_data(self.get_function)

        # Add cdk-nag suppressions
        self._add_nag_suppressions()

    def _create_table(self) -> dynamodb.Table:
        """Create the DynamoDB table."""
        return dynamodb.Table(
            self,
            "Table",
            table_name=f"{self.table_name}-{self.stage}",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.stage == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

    def _create_layer(self) -> PythonLayerVersion:
        """Create Lambda layer with shared dependencies."""
        return PythonLayerVersion(
            self,
            "CommonLayer",
            entry=constants.LAYER_BUILD_FOLDER,
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_13],
            compatible_architectures=[lambda_.Architecture.X86_64],
            removal_policy=RemovalPolicy.DESTROY,
            description="Common layer with aws-lambda-powertools and shared dependencies",
        )

    def _create_lambda_role(self) -> iam.Role:
        """Create IAM role for Lambda functions."""
        role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(f"service-role/{constants.LAMBDA_BASIC_EXECUTION_ROLE}")
            ],
        )

        # Add X-Ray tracing permissions
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],
            )
        )

        return role

    def _create_lambda_function(
        self,
        function_id: str,
        handler: str,
        description: str,
    ) -> lambda_.Function:
        """Create a Lambda function with common configuration."""

        # Create log group with retention
        log_group = logs.LogGroup(
            self,
            f"{function_id}LogGroup",
            retention=logs.RetentionDays.ONE_WEEK if self.stage == "dev" else logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        return lambda_.Function(
            self,
            function_id,
            function_name=f"{self.table_name}-{function_id.lower()}-{self.stage}",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler=handler,
            code=lambda_.Code.from_asset(constants.SERVICE_BUILD_FOLDER),
            timeout=Duration.seconds(constants.LAMBDA_TIMEOUT),
            memory_size=constants.LAMBDA_MEMORY_SIZE,
            layers=[self.layer],
            role=self.lambda_role,
            log_group=log_group,
            environment={
                constants.TABLE_NAME_ENV_VAR: self.table.table_name,
                constants.POWERTOOLS_SERVICE_NAME: constants.SERVICE_NAME,
                constants.POWERTOOLS_LOG_LEVEL: "DEBUG" if self.stage == "dev" else "INFO",
                "STAGE": self.stage,
            },
            tracing=lambda_.Tracing.ACTIVE,
            logging_format=lambda_.LoggingFormat.JSON,
            description=description,
        )

    def _add_nag_suppressions(self) -> None:
        """Add cdk-nag suppressions for expected security findings."""
        NagSuppressions.add_resource_suppressions(
            self.lambda_role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using AWS managed policy for Lambda basic execution role.",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "X-Ray tracing requires wildcard permissions.",
                },
            ],
            apply_to_children=True,
        )

        for func in [self.create_function, self.get_function]:
            NagSuppressions.add_resource_suppressions(
                func,
                suppressions=[
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "Using Python 3.13 which is the latest supported runtime.",
                    },
                ],
            )

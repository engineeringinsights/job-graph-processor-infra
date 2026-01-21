"""
Performance testing stack.

Job Graph Processor Architecture:
- Incoming Queue: receives jobs to process
- Lambda Processor: processes jobs, reads/writes job details to S3
- S3 Bucket: stores job details and results
- Outgoing Queue: receives completed job notifications

An external process feeds the incoming queue based on job dependencies
and reads from the outgoing queue to track completion.
"""

from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_events
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from aws_cdk.aws_lambda_python_alpha import PythonLayerVersion
from cdk_nag import NagSuppressions
from constructs import Construct

from cdk import constants


class Scenario1Stack(Stack):
    """
    Scenario 1: Lambda + S3 job processor infrastructure.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        stage: str,
        test_run_id: str | None = None,
        lambda_memory_size: int = constants.PERF_LAMBDA_MEMORY_SIZE,
        lambda_timeout: int = constants.PERF_LAMBDA_TIMEOUT,
        batch_size: int = constants.SQS_BATCH_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.stage = stage
        self.test_run_id = test_run_id or "default"
        self.resource_prefix = f"scenario-1-{stage}"

        # Apply cost allocation tags
        Tags.of(self).add("Purpose", "PerformanceTesting")
        Tags.of(self).add("Environment", stage)
        Tags.of(self).add(constants.TAG_TEST_RUN, self.test_run_id)

        # Create resources
        self.bucket = self._create_bucket()
        self.table = self._create_table()
        self.dlq = self._create_dlq()
        self.incoming_queue = self._create_incoming_queue()
        self.outgoing_queue = self._create_outgoing_queue()
        self.layer = self._create_layer()
        self.lambda_role = self._create_lambda_role()
        self.processor_function = self._create_processor_lambda(lambda_memory_size, lambda_timeout, batch_size)

        # Outputs
        self._create_outputs()

        # cdk-nag suppressions
        self._add_nag_suppressions()

    def _create_bucket(self) -> s3.Bucket:
        """Create S3 bucket for test data."""
        return s3.Bucket(
            self,
            "DataBucket",
            bucket_name=f"{self.resource_prefix}-data-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireTestData",
                    expiration=Duration.days(constants.S3_EXPIRATION_DAYS),
                    enabled=True,
                ),
            ],
        )

    def _create_table(self) -> dynamodb.Table:
        """Create DynamoDB table for job metadata."""
        return dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"{self.resource_prefix}-jobs",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
            time_to_live_attribute="ttl",
        )

    def _create_dlq(self) -> sqs.Queue:
        """Create dead-letter queue for failed jobs."""
        return sqs.Queue(
            self,
            "DeadLetterQueue",
            queue_name=f"{self.resource_prefix}-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
        )

    def _create_incoming_queue(self) -> sqs.Queue:
        """Create incoming queue for jobs to be processed."""
        return sqs.Queue(
            self,
            "IncomingQueue",
            queue_name=f"{self.resource_prefix}-incoming",
            visibility_timeout=Duration.seconds(constants.SQS_VISIBILITY_TIMEOUT),
            retention_period=Duration.days(7),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq,
            ),
        )

    def _create_outgoing_queue(self) -> sqs.Queue:
        """Create outgoing queue for completed job notifications."""
        return sqs.Queue(
            self,
            "OutgoingQueue",
            queue_name=f"{self.resource_prefix}-outgoing",
            retention_period=Duration.days(7),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True,
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
            description="Common layer with aws-lambda-powertools",
        )

    def _create_lambda_role(self) -> iam.Role:
        """Create IAM role for Lambda function."""
        role = iam.Role(
            self,
            "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(f"service-role/{constants.LAMBDA_BASIC_EXECUTION_ROLE}")
            ],
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                resources=["*"],
            )
        )

        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": constants.METRICS_NAMESPACE}},
            )
        )

        return role

    def _create_processor_lambda(
        self,
        memory_size: int,
        timeout: int,
        batch_size: int,
    ) -> lambda_.Function:
        """Create Lambda function to process SQS messages."""
        log_group = logs.LogGroup(
            self,
            "ProcessorLogGroup",
            log_group_name=f"/aws/lambda/{self.resource_prefix}-processor",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        processor = lambda_.Function(
            self,
            "ProcessorFunction",
            function_name=f"{self.resource_prefix}-processor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.X86_64,
            handler="service.handlers.processor.handler",
            code=lambda_.Code.from_asset(constants.SERVICE_BUILD_FOLDER),
            memory_size=memory_size,
            timeout=Duration.seconds(timeout),
            layers=[self.layer],
            role=self.lambda_role,
            log_group=log_group,
            environment={
                "BUCKET_NAME": self.bucket.bucket_name,
                "TABLE_NAME": self.table.table_name,
                "OUTGOING_QUEUE_URL": self.outgoing_queue.queue_url,
                "TEST_RUN_ID": self.test_run_id,
                "METRICS_NAMESPACE": constants.METRICS_NAMESPACE,
                "POWERTOOLS_SERVICE_NAME": "perf-testing",
                "POWERTOOLS_METRICS_NAMESPACE": constants.METRICS_NAMESPACE,
                "LOG_LEVEL": "INFO",
            },
            tracing=lambda_.Tracing.ACTIVE,
            logging_format=lambda_.LoggingFormat.JSON,
            description="Processes jobs from incoming queue, writes to S3, sends completion to outgoing queue",
        )

        # Grant permissions
        self.bucket.grant_read_write(processor)
        self.table.grant_read_write_data(processor)
        self.incoming_queue.grant_consume_messages(processor)
        self.outgoing_queue.grant_send_messages(processor)

        # Add event source from incoming queue
        processor.add_event_source(
            lambda_events.SqsEventSource(
                self.incoming_queue,
                batch_size=batch_size,
                max_batching_window=Duration.seconds(constants.SQS_MAX_BATCHING_WINDOW),
                report_batch_item_failures=True,
            )
        )

        return processor

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "IncomingQueueUrl",
            value=self.incoming_queue.queue_url,
            description="Incoming queue URL - send jobs here",
        )
        CfnOutput(self, "IncomingQueueArn", value=self.incoming_queue.queue_arn, description="Incoming queue ARN")
        CfnOutput(
            self,
            "OutgoingQueueUrl",
            value=self.outgoing_queue.queue_url,
            description="Outgoing queue URL - completed jobs appear here",
        )
        CfnOutput(self, "OutgoingQueueArn", value=self.outgoing_queue.queue_arn, description="Outgoing queue ARN")
        CfnOutput(self, "BucketName", value=self.bucket.bucket_name, description="S3 bucket for job details")
        CfnOutput(self, "TableName", value=self.table.table_name, description="DynamoDB table for job metadata")
        CfnOutput(self, "TableArn", value=self.table.table_arn, description="DynamoDB table ARN")
        CfnOutput(self, "ProcessorFunctionName", value=self.processor_function.function_name)
        CfnOutput(self, "TestRunId", value=self.test_run_id, description="Current test run ID for cost tracking")

    def _add_nag_suppressions(self) -> None:
        """Add cdk-nag suppressions."""
        NagSuppressions.add_resource_suppressions(
            self.lambda_role,
            [
                {"id": "AwsSolutions-IAM4", "reason": "Using AWS managed policy for Lambda basic execution"},
                {"id": "AwsSolutions-IAM5", "reason": "X-Ray and CloudWatch require wildcard permissions"},
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            self.bucket,
            [{"id": "AwsSolutions-S1", "reason": "Access logging not required for perf testing"}],
        )

        NagSuppressions.add_resource_suppressions(
            self.dlq,
            [{"id": "AwsSolutions-SQS3", "reason": "This IS the DLQ"}],
        )

        NagSuppressions.add_resource_suppressions(
            self.outgoing_queue,
            [{"id": "AwsSolutions-SQS3", "reason": "Outgoing queue is for notifications only, no DLQ needed"}],
        )

        NagSuppressions.add_resource_suppressions(
            self.processor_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13 which is the latest supported runtime"}],
        )

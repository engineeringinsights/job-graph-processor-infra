"""
Scenario 2: ECS Fargate + S3 job processor infrastructure.

Architecture:
- Incoming Queue: receives jobs to process
- ECS Fargate Service: polls queue, processes jobs
- S3 Bucket: stores job details and results
- Outgoing Queue: receives completed job notifications

The ECS service scales to 0 when not in use and tasks auto-exit after 5 minutes of idle.
"""

from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from cdk_nag import NagSuppressions
from constructs import Construct

from cdk import constants


class Scenario2Stack(Stack):
    """
    Scenario 2: ECS Fargate + S3 job processor infrastructure.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        stage: str,
        vpc: ec2.IVpc,
        test_run_id: str | None = None,
        cpu: int = constants.ECS_CPU,
        memory: int = constants.ECS_MEMORY,
        desired_count: int = 0,  # Start with 0, manually scale
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.stage = stage
        self.test_run_id = test_run_id or "default"
        self.resource_prefix = f"scenario-2-{stage}"
        self.vpc = vpc

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
        self.cluster = self._create_cluster()
        self.task_role = self._create_task_role()
        self.execution_role = self._create_execution_role()
        self.task_definition = self._create_task_definition(cpu, memory)
        self.service = self._create_service(desired_count)

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

    def _create_cluster(self) -> ecs.Cluster:
        """Create ECS cluster."""
        return ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"{self.resource_prefix}-cluster",
            vpc=self.vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

    def _create_task_role(self) -> iam.Role:
        """Create IAM role for ECS task (application permissions)."""
        role = iam.Role(
            self,
            "TaskRole",
            role_name=f"{self.resource_prefix}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # S3 permissions
        self.bucket.grant_read_write(role)

        # DynamoDB permissions
        self.table.grant_read_write_data(role)

        # SQS permissions
        self.incoming_queue.grant_consume_messages(role)
        self.outgoing_queue.grant_send_messages(role)

        # CloudWatch metrics
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": constants.METRICS_NAMESPACE}},
            )
        )

        # X-Ray tracing
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                resources=["*"],
            )
        )

        return role

    def _create_execution_role(self) -> iam.Role:
        """Create IAM role for ECS task execution (pull image, logs)."""
        role = iam.Role(
            self,
            "ExecutionRole",
            role_name=f"{self.resource_prefix}-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ],
        )
        return role

    def _create_task_definition(self, cpu: int, memory: int) -> ecs.FargateTaskDefinition:
        """Create Fargate task definition with container."""
        task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"{self.resource_prefix}-processor",
            cpu=cpu,
            memory_limit_mib=memory,
            task_role=self.task_role,
            execution_role=self.execution_role,
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.X86_64,
            ),
        )

        # Build and use Docker image from local Dockerfile
        image = ecs.ContainerImage.from_asset(
            ".",
            file="docker/Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

        # Create log group
        log_group = logs.LogGroup(
            self,
            "ProcessorLogGroup",
            log_group_name=f"/ecs/{self.resource_prefix}-processor",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Add container
        task_def.add_container(
            "ProcessorContainer",
            container_name="processor",
            image=image,
            essential=True,
            environment={
                "BUCKET_NAME": self.bucket.bucket_name,
                "TABLE_NAME": self.table.table_name,
                "INCOMING_QUEUE_URL": self.incoming_queue.queue_url,
                "OUTGOING_QUEUE_URL": self.outgoing_queue.queue_url,
                "TEST_RUN_ID": self.test_run_id,
                "METRICS_NAMESPACE": constants.METRICS_NAMESPACE,
                "BATCH_SIZE": str(constants.SQS_BATCH_SIZE),
                "LOG_LEVEL": "INFO",
                "AWS_DEFAULT_REGION": self.region,
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="processor",
                log_group=log_group,
            ),
            # Health check - container is healthy if process is running
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "pgrep -f 'python' || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        return task_def

    def _create_service(self, desired_count: int) -> ecs.FargateService:
        """Create ECS Fargate service."""
        # Security group allowing outbound only
        security_group = ec2.SecurityGroup(
            self,
            "ServiceSecurityGroup",
            vpc=self.vpc,
            description="Security group for ECS Fargate tasks",
            allow_all_outbound=True,
        )

        service = ecs.FargateService(
            self,
            "Service",
            service_name=f"{self.resource_prefix}-service",
            cluster=self.cluster,
            task_definition=self.task_definition,
            desired_count=desired_count,
            assign_public_ip=True,  # Required for public subnet without NAT
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[security_group],
            enable_execute_command=True,  # Allows ECS Exec for debugging
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                rollback=True,
            ),
        )

        return service

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "IncomingQueueUrl",
            value=self.incoming_queue.queue_url,
            description="Incoming queue URL - send jobs here",
        )
        CfnOutput(
            self,
            "IncomingQueueArn",
            value=self.incoming_queue.queue_arn,
            description="Incoming queue ARN",
        )
        CfnOutput(
            self,
            "OutgoingQueueUrl",
            value=self.outgoing_queue.queue_url,
            description="Outgoing queue URL - completed jobs appear here",
        )
        CfnOutput(
            self,
            "OutgoingQueueArn",
            value=self.outgoing_queue.queue_arn,
            description="Outgoing queue ARN",
        )
        CfnOutput(
            self,
            "BucketName",
            value=self.bucket.bucket_name,
            description="S3 bucket for job details",
        )
        CfnOutput(
            self,
            "TableName",
            value=self.table.table_name,
            description="DynamoDB table for job metadata",
        )
        CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster.cluster_arn,
            description="ECS cluster ARN",
        )
        CfnOutput(
            self,
            "ServiceArn",
            value=self.service.service_arn,
            description="ECS service ARN",
        )
        CfnOutput(
            self,
            "ServiceName",
            value=self.service.service_name,
            description="ECS service name (for scaling commands)",
        )
        CfnOutput(
            self,
            "ClusterName",
            value=self.cluster.cluster_name,
            description="ECS cluster name (for scaling commands)",
        )

    def _add_nag_suppressions(self) -> None:
        """Add cdk-nag suppressions for known issues."""
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-S1",
                    "reason": "S3 access logging not required for performance testing",
                },
                {
                    "id": "AwsSolutions-SQS3",
                    "reason": "DLQ is intentionally the DLQ itself",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies are acceptable for ECS task execution",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions for X-Ray and CloudWatch metrics are standard",
                },
                {
                    "id": "AwsSolutions-ECS4",
                    "reason": "Container insights enabled via container_insights_v2",
                },
                {
                    "id": "AwsSolutions-VPC7",
                    "reason": "VPC flow logs are enabled in the shared VPC stack",
                },
                {
                    "id": "AwsSolutions-EC23",
                    "reason": "Security group allows outbound only, no inbound",
                },
                {
                    "id": "AwsSolutions-ECS2",
                    "reason": (
                        "Environment variables contain non-sensitive configuration (bucket names,"
                        " queue URLs, timeouts), not secrets"
                    ),
                },
            ],
        )

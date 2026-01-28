"""
Shared VPC stack for performance testing.

Creates a VPC with public subnets only (no NAT Gateway) to minimize costs.
ECS tasks with public IPs can access AWS services directly.
"""

from typing import Any

from aws_cdk import CfnOutput, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from cdk_nag import NagSuppressions
from constructs import Construct


class SharedVpcStack(Stack):
    """
    Shared VPC for performance testing scenarios.

    Uses public subnets only to avoid NAT Gateway costs.
    ECS Fargate tasks will be assigned public IPs.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        stage: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.stage = stage
        self.resource_prefix = f"perf-shared-{stage}"

        # Apply tags
        Tags.of(self).add("Purpose", "PerformanceTesting")
        Tags.of(self).add("Environment", stage)
        Tags.of(self).add("Component", "SharedVpc")

        # Create VPC with public subnets only
        self.vpc = self._create_vpc()

        # Suppress CDK Nag rules for performance testing
        self._add_nag_suppressions()

        # Create outputs
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public subnets only (no NAT Gateway)."""
        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"{self.resource_prefix}-vpc",
            max_azs=2,
            nat_gateways=0,  # No NAT Gateway - use public subnets
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
            # Enable DNS support for AWS service endpoints
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        return vpc

    def _add_nag_suppressions(self) -> None:
        """Suppress CDK Nag rules not applicable for performance testing."""
        NagSuppressions.add_resource_suppressions(
            self.vpc,
            [
                {
                    "id": "AwsSolutions-VPC7",
                    "reason": "VPC Flow Logs not needed for performance testing infrastructure",
                },
            ],
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""
        CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            description="Shared VPC ID",
            export_name=f"{self.resource_prefix}-vpc-id",
        )
        CfnOutput(
            self,
            "PublicSubnetIds",
            value=",".join([subnet.subnet_id for subnet in self.vpc.public_subnets]),
            description="Public subnet IDs",
            export_name=f"{self.resource_prefix}-public-subnet-ids",
        )

from typing import Any

from aws_cdk import CfnOutput, Stack
from constructs import Construct

from cdk.lambda_dynamodb_construct import LambdaDynamoDBConstruct


class AppStack(Stack):
    """
    Main application stack that creates the Lambda + DynamoDB resources.
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

        # Create the Lambda + DynamoDB construct
        self.lambda_dynamodb = LambdaDynamoDBConstruct(
            self,
            "LambdaDynamoDB",
            stage=stage,
            table_name=table_name,
        )

        # Expose resources for cross-stack references if needed
        self.table = self.lambda_dynamodb.table
        self.create_function = self.lambda_dynamodb.create_function
        self.get_function = self.lambda_dynamodb.get_function

        # Outputs
        CfnOutput(
            self,
            "TableName",
            value=self.table.table_name,
            description="DynamoDB table name",
        )

        CfnOutput(
            self,
            "CreateFunctionArn",
            value=self.create_function.function_arn,
            description="Create item Lambda function ARN",
        )

        CfnOutput(
            self,
            "GetFunctionArn",
            value=self.get_function.function_arn,
            description="Get item Lambda function ARN",
        )

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput
)
from constructs import Construct

class FlaskLambdaStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Create DynamoDB table
        main_table = dynamodb.Table(self, "MainTable",
            table_name="main",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True, 
        )

        # cerate secondary index for sorting by created_at
        main_table.add_global_secondary_index(
            index_name="CreatedAtIndex",
            partition_key=dynamodb.Attribute(
            name="pk",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )

        # Create IAM role for Lambda function Execution
        lambda_role = iam.Role(self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Grant DynamoDB permissions to the Lambda role
        main_table.grant_read_write_data(lambda_role)

        # Lambda function for Flask application
        flask_lambda = _lambda.Function(self, "FlaskLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="lambda_handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TABLE_NAME": main_table.table_name,
                "REGION": self.region
            },
            log_retention=logs.RetentionDays.ONE_DAY,
        )

        # Create api gateway for the Flask application
        api = apigw.LambdaRestApi(self, "FlaskApi",
            handler=flask_lambda,
            proxy=True,
            description="Flask Lambda API with DynamoDB",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            ),
            # Enable CORS for the API
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]
            )
        )

        ## Outputs
        CfnOutput(self, "ApiUrl",
            value=api.url,
            description="API Gateway URL"
        )

        CfnOutput(self, "DynamoDBTableName",
            value=main_table.table_name,
            description="DynamoDB Table Name"
        )

        CfnOutput(self, "LambdaFunctionName",
            value=flask_lambda.function_name,
            description="Lambda Function Name"
        )
#!/usr/bin/env python3
import os
from aws_cdk import App, Stack, Environment
from main_stack import FlaskLambdaStack
from cicd_stack import OidcRoleStack


app = App()
FlaskLambdaStack(app, "FlaskLambdaStack",
  env=Environment(
    region="ap-northeast-1",
    account=os.getenv('CDK_DEFAULT_ACCOUNT', '773257008471')  # Default account if not set
  )
)

OidcRoleStack(app, "OidcRoleStack",
  repo="jiang-48692/serverless",
  env=Environment(
    region="ap-northeast-1",
    account=os.getenv('CDK_DEFAULT_ACCOUNT', '773257008471')  # Default account if not set
  )

    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
)

app.synth()

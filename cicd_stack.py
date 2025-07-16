from aws_cdk import (
    Stack,
    aws_iam as iam,
)
from constructs import Construct


class OidcRoleStack(Stack):
    """
    GitHub Actions から OIDC で AssumeRole するための
    OpenID Connect Provider と IAM Role を作成。
    """

    def __init__(self, scope: Construct, construct_id: str,
                 *, repo: str, role_name: str = "github-oidc-cdk-deploy",
                 **kwargs) -> None:
        """
        Parameters
        ----------
        repo : str
            "ORG/REPO" 形式。例: "my-org/my-cdk-app"
        role_name : str, optional
            作成する IAM Role 名。デフォルト "github-oidc-cdk-deploy"
        """
        super().__init__(scope, construct_id, **kwargs)

        # 1) GitHub OIDC Provider (一度だけ作れば再利用可)
        provider = iam.OpenIdConnectProvider(
            self, "GitHubProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"]
        )

        # 2) GitHub Actions から Assume できる IAM Role
        iam.Role(
            self, "GitHubDeployRole",
            role_name=role_name,
            assumed_by=iam.FederatedPrincipal(
                provider.open_id_connect_provider_arn,
                conditions={
                    # 必須: GitHub が発行するトークンの `sub` と `aud`
                    "StringEquals": {
                        "token.actions.githubusercontent.com:sub": f"repo:{repo}:ref:refs/heads/main",
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    }
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            # ★ 本番では最小権限に絞ってください
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
            ],
        )

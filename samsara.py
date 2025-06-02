import json
import os
from typing import Dict, Any, Optional, Protocol, List
import requests


class SSMClientProtocol(Protocol):
    """Protocol defining the SSM client interface we need."""

    def get_parameter(self, Name: str, WithDecryption: bool) -> Dict[str, Any]:
        """Get parameter from SSM."""
        ...


class Secrets:
    """
    Handles loading secrets from either local environment or AWS Parameter Store.
    """

    def __init__(self, client: Optional[SSMClientProtocol]) -> None:
        """
        Initialize the Secrets handler.

        Args:
            client: SSM client for accessing AWS Parameter Store, or None for local development
        """
        self.__client = client

    def load(self) -> Dict[str, Any]:
        """
        Load secrets from the appropriate source based on environment.

        When running locally, secrets are loaded from the
        'SamsaraFunctionLocalSecretsJson' environment variable.

        Returns:
            Dict containing the parsed secrets
        """
        if self.__client is None:
            return json.loads(os.environ.get("SamsaraFunctionLocalSecretsJson", "{}"))

        res = self.__client.get_parameter(
            Name=os.environ["SamsaraFunctionSecretsPath"], WithDecryption=True
        )

        value = res["Parameter"]["Value"]
        if value == "null":
            return {}

        return json.loads(value)


class Function:
    """
    Handles environment detection and secrets management.
    """

    def __init__(
        self, is_local: bool = os.environ.get("AWS_EXECUTION_ENV", "") == ""
    ) -> None:
        """
        Initialize the function with appropriate configuration based on environment.

        Args:
            is_local: Flag indicating if running in local development environment

        Note:
            The is_local parameter doesn't need to be set explicitly as it defaults to
            checking if AWS_EXECUTION_ENV is empty. This environment variable is automatically
            set by AWS Lambda when running in the cloud, but will be empty during local
            development, making the detection automatic in most cases.
        """
        if is_local:
            self.__secrets = Secrets(None)
        else:
            import boto3  # type: ignore -- boto3 is always available in the execution enviroment and not required in development.

            sts = boto3.client("sts")
            res = sts.assume_role(
                RoleArn=os.environ["SamsaraFunctionExecRoleArn"],
                RoleSessionName=os.environ["SamsaraFunctionName"],
            )

            credentials = {
                "aws_access_key_id": res["Credentials"]["AccessKeyId"],
                "aws_secret_access_key": res["Credentials"]["SecretAccessKey"],
                "aws_session_token": res["Credentials"]["SessionToken"],
            }

            self.__secrets = Secrets(boto3.client("ssm", **credentials))

    def secrets(self) -> Secrets:
        """
        Get the secrets handler.

        Returns:
            The configured Secrets instance
        """
        return self.__secrets


class SamsaraClient:
    """
    Client for interacting with the Samsara API.
    """

    BASE_URL = "https://api.samsara.com"

    def __init__(self, api_key: str) -> None:
        """
        Initialize the Samsara API client.

        Args:
            api_key: Your Samsara API key
        """
        self.api_key = api_key

    def get_headers(self) -> Dict[str, str]:
        """
        Get headers for API requests.

        Returns:
            Dictionary containing authorization and content type headers
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }


    def list_issues(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            response = requests.get(
                f"{self.BASE_URL}/issues/stream",
                headers=self.get_headers(),
                params=params
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching form issues: {e}")
            return []


    def update_issue(self, issue_id: str, payload: Dict[str, Any]) -> bool:
        payload["id"] = issue_id

        try:
            response = requests.patch(
                f"{self.BASE_URL}/issues",
                headers=self.get_headers(),
                json=payload
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error updating issue status: {e}")
            return False
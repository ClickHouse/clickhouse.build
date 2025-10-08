import os
from pathlib import Path

from strands.handlers.callback_handler import PrintingCallbackHandler


def get_callback_handler():
    """
    Returns the appropriate callback handler based on environment.
    In dev: returns default strands callback handler
    In prod: returns None
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "prod":
        return None
    else:
        return PrintingCallbackHandler()


def check_aws_credentials():
    """
    Check if AWS credentials are available and properly configured.

    Returns:
        tuple: (bool, str) - (credentials_available, error_message)
    """
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError

        # Try to create a session and get credentials
        session = boto3.Session()
        credentials = session.get_credentials()

        if credentials is None:
            return (
                False,
                "AWS credentials not found. Please configure your AWS credentials using one of the following methods:\n"
                "1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
                "2. Configure AWS CLI: aws configure\n"
                "3. Use IAM roles if running on EC2\n"
                "4. Create ~/.aws/credentials file",
            )

        # Test that credentials work by trying to get caller identity
        sts = boto3.client("sts")
        sts.get_caller_identity()

        return True, ""

    except (NoCredentialsError, PartialCredentialsError):
        return (
            False,
            "AWS credentials not found or incomplete. Please configure your AWS credentials using one of the following methods:\n"
            "1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n"
            "2. Configure AWS CLI: aws configure\n"
            "3. Use IAM roles if running on EC2\n"
            "4. Create ~/.aws/credentials file",
        )
    except Exception as e:
        return False, f"Error checking AWS credentials: {str(e)}"

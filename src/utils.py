import json
import os
from typing import Any

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError


class PrintingCallbackHandler:
    """Handler for streaming text output and tool invocations to stdout."""

    def __init__(self) -> None:
        """Initialize handler."""
        self.tool_count = 0
        self.previous_tool_use = None
        self.tool_inputs = {}  # Track accumulated tool inputs by toolUseId
        self.displayed_tools = set()  # Track which tools we've already displayed

    def __call__(self, **kwargs: Any) -> None:
        """Stream text output and tool invocations to stdout.

        Args:
            **kwargs: Callback event data including:
                - reasoningText (Optional[str]): Reasoning text to print if provided.
                - data (str): Text content to stream.
                - complete (bool): Whether this is the final chunk of a response.
                - current_tool_use (dict): Information about the current tool being used.
                - agent: The agent object executing the tool.
        """
        reasoningText = kwargs.get("reasoningText", False)
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use", {})
        agent = kwargs.get("agent")

        if reasoningText:
            print(reasoningText, end="")

        if data:
            print(data, end="" if not complete else "\n")

        if current_tool_use and current_tool_use.get("name"):
            tool_use_id = current_tool_use.get("toolUseId")
            tool_name = current_tool_use.get("name", "Unknown tool")
            tool_input = current_tool_use.get("input", "")

            if tool_use_id:
                self.tool_inputs[tool_use_id] = tool_input

                # Try to parse as JSON to see if it's complete
                parsed_input = None
                if isinstance(tool_input, str) and tool_input:
                    try:
                        parsed_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        # Not complete JSON yet, skip for now
                        pass
                elif isinstance(tool_input, dict):
                    parsed_input = tool_input

                if parsed_input and tool_use_id not in self.displayed_tools:
                    self.displayed_tools.add(tool_use_id)
                    self.tool_count += 1

                    # Get agent name
                    agent_name = "unknown"
                    if agent:
                        # Try to get the agent's name or class name
                        agent_name = (
                            getattr(agent, "name", None) or agent.__class__.__name__
                        )

                    input_parts = []
                    for key, value in parsed_input.items():
                        if value is not None and value != "" and value is not False:
                            # Truncate long values
                            str_value = str(value)
                            if len(str_value) > 50:
                                str_value = str_value[:47] + "..."
                            input_parts.append(f"{key}={str_value}")

                    if input_parts:
                        input_str = ", ".join(input_parts)
                        print(
                            f"\n\n🌕 [{agent_name}] Tool({self.tool_count}): {tool_name}({input_str})\n"
                        )
                    else:
                        print(
                            f"\n\n🌕 [{agent_name}] Tool({self.tool_count}): {tool_name}()\n"
                        )

        if complete and data:
            print("\n")


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

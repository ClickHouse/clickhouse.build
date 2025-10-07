import logging

from strands import Agent, tool
from strands.models import BedrockModel

from ..utils import check_aws_credentials, get_callback_handler

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a code migration assistant. Your job is to help migrate application code.

For now, you should respond with: "Hello World! Code migrator is ready."
"""

model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"


@tool
def agent_code_migrator(repo_path: str) -> str:
    """
    Run the code migrator agent to help migrate application code.

    Args:
        repo_path: Path to the repository

    Returns:
        Migration guidance (currently just a hello world message)
    """
    logger.info(f"Code migrator agent starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    bedrock_model = BedrockModel(model_id=model_id)

    try:
        agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[],
            callback_handler=get_callback_handler(),
        )

        logger.info("=== CODE MIGRATOR AGENT STARTED ===")

        result = agent("Please introduce yourself and confirm you're ready.")

        logger.info("=== CODE MIGRATOR AGENT COMPLETED ===")

        return str(result)

    except Exception as e:
        logger.error(f"Exception in code_migrator: {type(e).__name__}: {e}")
        return f"Error running code migrator: {str(e)}"

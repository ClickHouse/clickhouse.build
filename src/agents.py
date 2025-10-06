import logging
import os

from strands import Agent, tool
from strands.models import BedrockModel
from .utils import get_callback_handler, check_aws_credentials
from .local_tools import glob, grep, read

logger = logging.getLogger(__name__)

PROMPT_CODE_PLANNER = """
You are an AI agent specialized in analyzing TypeScript/JavaScript repositories.
You have no other purpose but to find analytical queries.

<response_style>
Be concise and direct. Provide structured results without explanatory prose.
Output only the requested information in the specified format.
</response_style>

<instruction>
Search the codebase and identify ALL PostgreSQL analytical queries used for data analysis,
reporting, or business intelligence purposes.

EXCLUDE the following:
- CRUD operations: INSERT, UPDATE, DELETE
- Simple SELECT statements fetching single records by ID
- Schema definitions: CREATE, ALTER, DROP statements
- Transaction management: BEGIN, COMMIT, ROLLBACK
- Basic lookups without aggregation or complex logic
</instruction>
"""

model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"

@tool
def code_planner(repo_path: str) -> str:
    logger.info(f"code_planner starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    bedrock_model = BedrockModel(model_id=model_id)

    try:
        env = {
            "FASTMCP_LOG_LEVEL": "ERROR",
            "AWS_PROFILE": os.getenv("AWS_PROFILE", "default"),
            "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        }

        code_reader_agent = Agent(
            model=bedrock_model,
            system_prompt=PROMPT_CODE_PLANNER,
            tools=[glob, grep, read],
            callback_handler=get_callback_handler()
        )

        result = str(code_reader_agent(repo_path))
        logger.info(f"=== CODE READER COMPLETED ===")
        logger.info(f"Repository: {repo_path}")
        logger.info(f"Result length: {len(result)} characters")
        logger.info(f"Result preview: {result[:500]}{'...' if len(result) > 500 else ''}")
        return result

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
        return f"Error processing your query: {str(e)}"

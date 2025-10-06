import logging
import os
import time

from strands import Agent, tool
from strands.models import BedrockModel
from .utils import get_callback_handler, check_aws_credentials
from .local_tools import glob, grep, read

logger = logging.getLogger(__name__)

PROMPT_CODE_PLANNER = """
You are a fast, efficient code analyzer. Find PostgreSQL analytical queries ONLY.
CRITICAL: The user will provide a repository path. You MUST use that exact path in your tool calls.

STRATEGY:
1. Call grep with these parameters:
   - pattern="SELECT.*FROM"
   - path=<the repo path provided by user>
   - case_insensitive=True
   - output_mode="content"
   - show_line_numbers=True

   Do NOT use file_pattern since we want to search all text files.

2. Analyze the grep results directly - DO NOT read full files
3. Report findings immediately

INCLUDE:
- Queries with: GROUP BY, COUNT, SUM, AVG, aggregations, DATE_TRUNC, LIMIT, ORDER BY
- Analytics, reporting, or business intelligence queries

EXCLUDE:
- INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, BEGIN, COMMIT, ROLLBACK
- Simple SELECT by ID without aggregation

OUTPUT FORMAT:
List each query with:
- File path and line numbers
- SQL query (abbreviated if long)
- Brief purpose

Try to use ONE grep call. Be fast.
"""

model_id="anthropic.claude-3-5-haiku-20241022-v1:0"

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
            callback_handler=get_callback_handler(),
        )

        # Start timer
        start_time = time.time()
        logger.info(f"=== CODE PLANNER STARTED ===")

        result = str(code_reader_agent(repo_path))

        # End timer
        end_time = time.time()
        elapsed_time = end_time - start_time

        logger.info(f"=== CODE PLANNER COMPLETED ===")
        logger.info(f"Repository: {repo_path}")
        logger.info(f"⏱️  Total execution time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        print(f"\n⏱️  Total execution time: {elapsed_time:.2f} seconds\n")

        return result

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
        return f"Error processing your query: {str(e)}"

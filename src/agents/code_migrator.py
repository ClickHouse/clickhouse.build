import json
import logging
import time
from datetime import datetime
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import file_write

from ..agents.qa_code_migrator import qa_approve
from ..prompts.code_migrator import get_system_prompt
from ..tools.common import bash_run, call_human, glob, grep, read
from ..utils import check_aws_credentials, get_callback_handler

logger = logging.getLogger(__name__)

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

    bedrock_model = BedrockModel(
        model_id=model_id,
        max_tokens=16_000,
        temperature=1,
        additional_request_fields={
            "anthropic_beta": ["interleaved-thinking-2025-05-14"],
            "reasoning_config": {"type": "enabled", "budget_tokens": 10_000},
        },
    )

    try:
        start_time = time.time()

        agent = Agent(
            name="code_migrator",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[grep, glob, read, bash_run, qa_approve, file_write, call_human],
            callback_handler=get_callback_handler(),
        )

        logger.info("=== CODE MIGRATOR AGENT STARTED ===")

        result = agent(
            f"Install the @clickhouse/client package in repository: {repo_path}"
        )

        logger.info("=== CODE MIGRATOR AGENT COMPLETED ===")

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Prepare result
        result_str = str(result)

        # Write to timestamped file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        migrator_dir = Path(repo_path) / ".chbuild" / "migrator" / "code"
        migrator_dir.mkdir(parents=True, exist_ok=True)

        plan_file = Path(repo_path) / ".chbuild" / "planner" / f"plan_{timestamp}.json"

        # Try to parse result as JSON, otherwise wrap it
        try:
            result_json = json.loads(result_str)
        except json.JSONDecodeError:
            result_json = {"result": result_str}

        # Add metadata
        result_json["_metadata"] = {
            "timestamp": timestamp,
            "elapsed_seconds": round(elapsed_time, 2),
            "status": "completed",
        }

        plan_file.write_text(json.dumps(result_json, indent=2))
        logger.info(f"Code migration plan saved to: {plan_file}")

        return result_str

    except Exception as e:
        logger.error(f"Exception in code_migrator: {type(e).__name__}: {e}")

        # Write error to timestamped file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        migrator_dir = Path(repo_path) / ".chbuild" / "migrator" / "code"
        migrator_dir.mkdir(parents=True, exist_ok=True)

        error_file = migrator_dir / f"plan_{timestamp}.json"
        error_data = {
            "error": str(e),
            "_metadata": {"timestamp": timestamp, "status": "error"},
        }
        error_file.write_text(json.dumps(error_data, indent=2))

        return f"Error running code migrator: {str(e)}"

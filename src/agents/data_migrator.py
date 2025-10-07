import json
import logging
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from .planner import agent_planner
from ..tools.data_migrator import data_migrator
from ..utils import check_aws_credentials

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a data extraction specialist. Your ONLY job is to:

1. Extract database name, schema names, and table names from the plan data
2. Document any assumptions you made for missing information
3. Call the data_migrator tool with the extracted information
4. Return a JSON object with two keys: "assumptions" (list of strings) and "config" (the tool output)

When calling data_migrator tool:
- database_name: the database name (use "postgres" if inferred - ADD THIS TO ASSUMPTIONS)
- schema_tables: dict mapping schema names to lists of tables (use "public" if inferred - ADD THIS TO ASSUMPTIONS)
- replication_mode: use the requested mode
- destination_database: same as database_name

CRITICAL: Your response must be valid JSON in this exact format:
{
  "assumptions": ["assumption 1", "assumption 2"],
  "config": <the exact JSON from data_migrator tool>
}

You will likely have to make assumptions about database and schema names as well as ordering keys.
If no assumptions were made, use an empty list: "assumptions": []
"""

model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"


def get_latest_plan(repo_path: str) -> dict:
    """
    Get the most recent plan file from the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        dict: The parsed plan JSON

    Raises:
        FileNotFoundError: If no plan files exist
    """
    plans_dir = Path(repo_path) / ".chbuild" / "plans"

    if not plans_dir.exists():
        raise FileNotFoundError(
            f"Plans directory not found at {plans_dir}. "
            "No plans have been generated yet."
        )

    # Find all plan files and sort by name (which sorts by timestamp)
    plan_files = sorted(plans_dir.glob("plan_*.json"), reverse=True)

    if not plan_files:
        raise FileNotFoundError(
            f"No plan files found in {plans_dir}. "
            "No plans have been generated yet."
        )

    latest_plan = plan_files[0]
    logger.info(f"Reading latest plan: {latest_plan.name}")

    with open(latest_plan, "r") as f:
        return json.load(f)


def run_data_migrator_agent(repo_path: str, replication_mode: str = "cdc") -> str:
    """
    Run the data migrator agent to analyze the plan and generate ClickPipe config.

    Args:
        repo_path: Path to the repository
        replication_mode: Replication mode override (cdc, snapshot, cdc_only)

    Returns:
        Result from the data migrator tool (ClickPipe configuration)
    """
    logger.info(f"Data migrator agent starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    try:
        # Try to get the latest plan, run planner if none exists
        try:
            plan_data = get_latest_plan(repo_path)
        except FileNotFoundError:
            logger.info("No existing plan found, running planner agent first...")
            agent_planner(repo_path)
            # Now get the plan that was just created
            plan_data = get_latest_plan(repo_path)

        logger.info(f"Loaded plan with {plan_data.get('total_tables', 0)} tables and {plan_data.get('total_queries', 0)} queries")

        bedrock_model = BedrockModel(model_id=model_id)

        agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[data_migrator],
            callback_handler=None,
        )

        plan_json = json.dumps(plan_data, indent=2)
        prompt = f"""Extract database, schemas, and tables from this plan data. Document any assumptions.

Replication mode: {replication_mode}

Plan Data:
{plan_json}

Return JSON with "assumptions" list and "config" object as specified in system prompt."""

        logger.info("=== DATA MIGRATOR AGENT STARTED ===")
        result = agent(prompt)
        logger.info("=== DATA MIGRATOR AGENT COMPLETED ===")

        return str(result)

    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Exception in data_migrator_agent: {type(e).__name__}: {e}")
        return f"Error analyzing plan: {str(e)}"

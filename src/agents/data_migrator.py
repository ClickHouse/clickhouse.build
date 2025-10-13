import json
import logging
import time
from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from ..prompts.data_migrator import get_system_prompt
from ..tools.data_migrator import data_migrator
from ..tui import (print_code, print_error, print_header, print_info,
                   print_summary_panel)
from ..utils import check_aws_credentials, get_callback_handler
from .planner import agent_planner

logger = logging.getLogger(__name__)

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
    planner_dir = Path(repo_path) / ".chbuild" / "planner"

    if not planner_dir.exists():
        raise FileNotFoundError(
            f"Planner directory not found at {planner_dir}. "
            "No plans have been generated yet."
        )

    # Find all plan files and sort by name (which sorts by timestamp)
    plan_files = sorted(planner_dir.glob("plan_*.json"), reverse=True)

    if not plan_files:
        raise FileNotFoundError(
            f"No plan files found in {planner_dir}. "
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
        print_error(error_message)
        return f"Error: {error_message}"

    try:
        print_header("Data Migrator Agent", f"Repository: {repo_path}")

        # Try to get the latest plan, run planner if none exists
        try:
            print_info("Loading plan data...", label="Step 1")
            plan_data = get_latest_plan(repo_path)
        except FileNotFoundError:
            logger.info("No existing plan found, running planner agent first...")
            print_info("No existing plan found, running planner first", label="Notice")
            agent_planner(repo_path)
            # Now get the plan that was just created
            plan_data = get_latest_plan(repo_path)

        logger.info(
            f"Loaded plan with {plan_data.get('total_tables', 0)} tables and {plan_data.get('total_queries', 0)} queries"
        )

        # Display plan summary
        plan_summary = {
            "Total Tables": plan_data.get("total_tables", 0),
            "Total Queries": plan_data.get("total_queries", 0),
            "Replication Mode": replication_mode.upper(),
        }
        print_summary_panel(plan_summary, title="Plan Summary")

        print_info("Analyzing plan and generating configuration...", label="Step 2")

        bedrock_model = BedrockModel(model_id=model_id)

        agent = Agent(
            name="data_migrator",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[data_migrator],
            callback_handler=get_callback_handler(),
        )

        plan_json = json.dumps(plan_data, indent=2)
        prompt = f"""Extract database, schemas, and tables from this plan data. Document any assumptions.

Replication mode: {replication_mode}

Plan Data:
{plan_json}

Return JSON with "assumptions" list and "config" object as specified in system prompt."""

        start_time = time.time()
        result = agent(prompt)
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Display results
        result_str = str(result)

        try:
            result_data = json.loads(result_str)

            # Display execution time
            exec_summary = {
                "Execution Time": f"{elapsed_time:.2f}s ({elapsed_time/60:.2f}m)",
                "Status": "Success",
            }
            print_summary_panel(exec_summary, title="Execution Summary")

            # Display assumptions if any
            if "assumptions" in result_data and result_data["assumptions"]:
                print_info(f"Made {len(result_data['assumptions'])} assumptions", label="Notice")
                for assumption in result_data["assumptions"]:
                    print_info(f"• {assumption}")
                print()

            # Display config
            if "config" in result_data:
                config_data = result_data["config"]
                if isinstance(config_data, str):
                    config_data = json.loads(config_data)

                # Display info text if present
                if "info" in config_data:
                    print_info(config_data["info"])
                    print()

                # Display curl command as bash markdown
                if "command" in config_data:
                    print_code(config_data["command"], language="bash", title="ClickPipe Configuration Command")
        except json.JSONDecodeError:
            # If result is not JSON, just display it as is
            print_info("Result generated successfully", label="Step 3")

        return result_str

    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        print_error(str(e))
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Exception in data_migrator_agent: {type(e).__name__}: {e}")
        print_error(str(e))
        return f"Error analyzing plan: {str(e)}"

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from langfuse import observe
from strands import Agent
from strands.models import BedrockModel

from ..logging_config import get_current_log_file
from ..models_config import DEFAULT_MODEL, get_model_id
from ..prompts.data_migrator import get_system_prompt
from ..tools.common import set_project_root
from ..tools.data_migrator import create_clickpipe
from ..tui import print_code, print_error, print_header, print_info, print_summary_panel
from ..utils import check_aws_credentials, get_callback_handler
from ..utils.langfuse import get_langfuse_client
from .scanner import agent_scanner

logger = logging.getLogger(__name__)


def get_latest_scan(repo_path: str) -> tuple[dict, Path]:
    """
    Get the most recent scan file from the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        tuple[dict, Path]: The parsed scan JSON and the path to the scan file

    Raises:
        FileNotFoundError: If no scan files exist
    """
    scanner_dir = Path(repo_path) / ".chbuild" / "scanner"

    if not scanner_dir.exists():
        raise FileNotFoundError(
            f"Scanner directory not found at {scanner_dir}. "
            "No scans have been generated yet."
        )

    # Find all scan files and sort by name (which sorts by timestamp)
    scan_files = sorted(scanner_dir.glob("scan_*.json"), reverse=True)

    if not scan_files:
        raise FileNotFoundError(
            f"No scan files found in {scanner_dir}. "
            "No scans have been generated yet."
        )

    latest_scan = scan_files[0]
    logger.info(f"Reading latest scan: {latest_scan.name}")

    with open(latest_scan, "r") as f:
        return json.load(f), latest_scan


@observe(name="agent_data_migrator")
def run_data_migrator_agent(
    repo_path: str, replication_mode: str = "cdc", model: str = DEFAULT_MODEL
) -> str:
    """
    Run the data migrator agent to analyze the scan and generate ClickPipe config.

    Args:
        repo_path: Path to the repository
        replication_mode: Replication mode (cdc, snapshot, or cdc_only). Default is "cdc".
            - cdc: Change Data Capture with initial snapshot + real-time sync
            - snapshot: One-time snapshot replication only
            - cdc_only: CDC without initial snapshot
        model: AI model to use for analysis. Default is DEFAULT_MODEL.

    Returns:
        Result from the data migrator tool (ClickPipe configuration)
    """
    logger.info(f"Data migrator agent starting analysis of repository: {repo_path}")
    set_project_root(repo_path)

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print_error(error_message)
        return f"Error: {error_message}"

    try:
        print_header("Data Migrator Agent", f"Repository: {repo_path}")

        # Try to get the latest scan, run scanner if none exists
        try:
            print_info("Loading scan data...", label="Step 1")
            scan_data, scan_file_path = get_latest_scan(repo_path)
        except FileNotFoundError:
            logger.info("No existing scan found, running scanner agent first...")
            print_info("No existing scan found, running scanner first", label="Notice")
            agent_scanner(repo_path)
            # Now get the scan that was just created
            scan_data, scan_file_path = get_latest_scan(repo_path)

        logger.info(
            f"Loaded scan with {scan_data.get('total_tables', 0)} tables and {scan_data.get('total_queries', 0)} queries"
        )

        # Display scan summary
        scan_summary = {
            "Total Tables": scan_data.get("total_tables", 0),
            "Total Queries": scan_data.get("total_queries", 0),
            "Replication Mode": replication_mode.upper(),
        }
        print_summary_panel(scan_summary, title="Scan Summary")

        print_info("Analyzing scan and generating configuration...", label="Step 2")

        model_id = get_model_id(model)
        bedrock_model = BedrockModel(model_id=model_id)

        agent = Agent(
            name="data_migrator",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[create_clickpipe],
            callback_handler=get_callback_handler(),
        )

        scan_json = json.dumps(scan_data, indent=2)
        prompt = f"""Extract database, schemas, and tables from this scan data. Document any assumptions.

Replication mode: {replication_mode}

Scan Data:
{scan_json}

Return JSON with "assumptions" list and "config" object as specified in system prompt."""

        start_time = time.time()
        result = agent(prompt)
        end_time = time.time()
        elapsed_time = end_time - start_time

        result_str = str(result).strip()
        if result_str.startswith("```json"):
            result_str = result_str[7:]
        elif result_str.startswith("```"):
            result_str = result_str[3:]
        if result_str.endswith("```"):
            result_str = result_str[:-3]
        result_str = result_str.strip()

        try:
            result_data = json.loads(result_str)
            exec_summary = {
                "Execution Time": f"{elapsed_time:.2f}s ({elapsed_time/60:.2f}m)",
                "Status": "Success",
            }
            print("\n\n")
            print_summary_panel(exec_summary, title="Execution Summary")

            # Display assumptions if any
            if "assumptions" in result_data and result_data["assumptions"]:
                print_info(
                    f"Made {len(result_data['assumptions'])} assumptions",
                    label="Notice",
                )
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
                    print_code(
                        config_data["command"],
                        language="bash",
                        title="ClickPipe Configuration Command",
                    )
        except json.JSONDecodeError:
            # If result is not JSON, just display it as is
            print_info("Result generated successfully", label="Step 3")

        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_migrator_dir = Path(repo_path) / ".chbuild" / "data_migrator"
        data_migrator_dir.mkdir(parents=True, exist_ok=True)

        result_file = data_migrator_dir / f"result_{timestamp}.json"
        result_file.write_text(result_str)

        print_info(str(scan_file_path), label="Input file")
        print_info(str(result_file), label="Results saved to")

        log_file = get_current_log_file()
        if log_file:
            print_info(log_file, label="Logs saved to")

        # Flush Langfuse data
        langfuse_client = get_langfuse_client()
        if langfuse_client:
            langfuse_client.flush()

        return result_str

    except FileNotFoundError as e:
        logger.error(f"File not found: {str(e)}")
        print_error(str(e))

        langfuse_client = get_langfuse_client()
        if langfuse_client:
            langfuse_client.flush()

        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Exception in data_migrator_agent: {type(e).__name__}: {e}")
        print_error(str(e))

        langfuse_client = get_langfuse_client()
        if langfuse_client:
            langfuse_client.flush()

        return f"Error analyzing scan: {str(e)}"

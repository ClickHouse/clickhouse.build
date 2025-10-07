import json
import logging
import time
from datetime import datetime
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import file_write

from ..tools.common import bash_run, glob, read
from ..tools.qa_code_migrator import qa_approve
from ..utils import check_aws_credentials, get_callback_handler

logger = logging.getLogger(__name__)


def get_system_prompt(agents_md_content: str = "") -> str:
    """Build the system prompt with optional AGENTS.md content injected."""
    additional_instructions = ""
    if agents_md_content:
        additional_instructions = f"""
<additional_agent_instructions source="AGENTS.md">
{agents_md_content}
</additional_agent_instructions>

"""

    return f"""
You are a code migration assistant helping developers add ClickHouse to their application.

Your job is to install the ClickHouse client library and understand the application's data structure. Follow these steps:
{additional_instructions}

1. **Read the latest plan**
   - Use glob to find plan files in .chbuild/planner/plan_*.json
   - If NO plan files exist, immediately return this JSON and STOP:
     {
       "error": "No plan found. Please run the planner first to analyze your queries.",
       "plan_found": false
     }
   - If plan files exist, read the most recent plan file (sorted by filename)
   - Understand what tables and queries exist in the application

2. **Determine the package manager**
   - Check for lock files: package-lock.json (npm), yarn.lock (yarn), pnpm-lock.yaml (pnpm), bun.lockb (bun)
   - Use glob to find these files in the repository
   - Determine which package manager the project uses

3. **Install @clickhouse/client package**
   - Use the appropriate install command for the detected package manager:
     - npm: `npm install @clickhouse/client`
     - yarn: `yarn add @clickhouse/client`
     - pnpm: `pnpm add @clickhouse/client`
     - bun: `bun add @clickhouse/client`
   - Run the command using bash_run tool

4. **Confirm installation**
   - Read package.json to verify @clickhouse/client is in dependencies

5. **Design strategy pattern for query routing**
   - Re-read the planner file to understand all query locations
   - Use read tool to inspect each query site (file and line numbers from the plan)
   - Design a strategy pattern that:
     a) Maintains backwards compatibility with existing PostgreSQL queries
     b) Allows toggling between PostgreSQL and ClickHouse via environment variable
     c) Environment variable `USE_CLICKHOUSE=true/false` can be:
        - In a .env file (loaded by dotenv or similar)
        - OR a system environment variable
     d) Uses proper TypeScript types - NEVER use `any` or `unknown` types
        - Even if existing code uses any/unknown, your generated code must use proper types
        - All functions, parameters, and return values must be strongly typed

6. **Implement code changes**
   - For EACH file you want to create or modify:
     a) Generate the code content
     b) Call qa_approve tool with: file_path, code_content, and purpose
     c) The qa_approve tool returns: {"approved": boolean, "reason": string}
     d) If approved=true: proceed with file_write
     e) If approved=false: revise the code based on the reason and try qa_approve again
     f) Do NOT use file_write without qa_approve approval
   - Create necessary files (e.g., query router, ClickHouse client wrapper, type definitions)
   - Update each query site identified in the plan to use the new strategy pattern
   - Ensure all code maintains backwards compatibility
   - Ensure strict TypeScript typing throughout (no any/unknown)
   - Return a JSON object with:
     {
       "plan_found": true,
       "tables": [...list from plan...],
       "package_manager": "...",
       "installed": true/false,
       "version": "...",
       "strategy": {
         "pattern": "description of the strategy pattern approach",
         "query_sites": [...list of {file, location, query_type} objects...],
         "total_query_sites": number,
         "environment_variable": "USE_CLICKHOUSE",
         "environment_sources": [".env file", "system environment"],
         "backwards_compatible": true,
         "strict_typing": true
       },
       "implementation": {
         "files_created": [...list of new files...],
         "files_modified": [...list of modified files...],
         "total_changes": number,
         "status": "completed"
       }
     }

IMPORTANT:
- Use the exact repo path provided for all tool calls
- NEVER use any or unknown types in generated code
- Use file_write tool to write/update files
- Return your final result as valid JSON
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

    # Read AGENTS.md if it exists
    agents_md_content = ""
    agents_md_path = Path(repo_path) / "AGENTS.md"
    if agents_md_path.exists():
        try:
            agents_md_content = agents_md_path.read_text()
            logger.info("Found AGENTS.md in repository")
        except Exception as e:
            logger.warning(f"Failed to read AGENTS.md: {e}")

    try:
        start_time = time.time()

        agent = Agent(
            model=bedrock_model,
            system_prompt=get_system_prompt(agents_md_content),
            tools=[glob, read, bash_run, qa_approve, file_write],
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

        plan_file = migrator_dir / f"plan_{timestamp}.json"

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

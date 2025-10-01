"""
Data Migrator Agent

Reads CODE_DISCOVERY.md and determines how to configure the data_migrator tool
for PostgreSQL to ClickHouse data migration via ClickPipes.
"""

import re
from pathlib import Path
from strands import Agent
from strands.models import BedrockModel
from .tools import data_migrator
from .utils import check_aws_credentials

SYSTEM_PROMPT = """
You are a data extraction specialist. Your ONLY job is to:

1. Extract database name, schema names, and table names from the ## Data section
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

You will likely have to make assumptions about database and schema names as well as ording keys.
If no assumptions were made, use an empty list: "assumptions": []
"""


def read_code_discovery(repo_path: str) -> tuple[str, dict]:
    """
    Read the CODE_DISCOVERY.md file from the repository.

    Args:
        repo_path: Path to the repository

    Returns:
        Tuple of (file_content, metadata_dict)

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    discovery_path = Path(repo_path) / ".chbuild" / "CODE_DISCOVERY.md"

    if not discovery_path.exists():
        raise FileNotFoundError(
            f"CODE_DISCOVERY.md not found at {discovery_path}. "
            "Please run code discovery first to generate this file."
        )

    with open(discovery_path, 'r') as f:
        content = f.read()

    # Parse metadata from frontmatter
    metadata = {}
    frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        for line in frontmatter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

    return content, metadata


def run_data_migrator_agent(repo_path: str, replication_mode: str = "cdc") -> str:
    """
    Run the data migrator agent to analyze the code discovery and generate ClickPipe config.

    Args:
        repo_path: Path to the repository containing the code discovery
        replication_mode: Replication mode override (cdc, snapshot, cdc_only)

    Returns:
        Result from the data migrator tool (ClickPipe configuration)
    """
    # Check AWS credentials
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    try:
        # Read the code discovery
        content, metadata = read_code_discovery(repo_path)

        # Get epoch from metadata
        epoch = metadata.get('epoch', 'unknown')

        # Create the agent
        bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

        agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[data_migrator],
            callback_handler=None
        )

        prompt = f"""Extract database, schemas, and tables from the ## Data section. Document any assumptions.

Replication mode: {replication_mode}

{content}

Return JSON with "assumptions" list and "config" object as specified in system prompt."""

        # Run the agent
        result = agent(prompt)

        return str(result)

    except FileNotFoundError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error analyzing code discovery: {str(e)}"

from enum import Enum
import json
import os

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands_tools import shell, file_write, editor
from .prompts import CODE_ANALYSIS_PROMPT, CODE_WRITER_PROMPT, CODE_CONVERTER_PROMPT

@tool
def code_reader(repo_path: str) -> str:
    """
    Code reader specialist that can search through a repository and find relevant content.

    Args:
        repo_path: The repository path of the repository to analyze

    Returns:
        Reading findings
    """
    bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

    try:
        env = {
            "FASTMCP_LOG_LEVEL": "DEBUG",
            "AWS_REGION": "us-west-2",
            "AWS_PROFILE": os.getenv("AWS_PROFILE", "default"),
            "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        }

        git_repo_mcp_server = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=["awslabs.git-repo-research-mcp-server@latest"],
                    env=env,
                )
            )
        )

        with git_repo_mcp_server:
            tools = git_repo_mcp_server.list_tools_sync()
            code_reader_agent = Agent(
                model=bedrock_model,
                system_prompt=CODE_ANALYSIS_PROMPT,
                tools=tools,
                callback_handler=None
            )

            result = str(code_reader_agent(repo_path))
            return result

    except Exception as e:
        print(f"Exception in write_new_content: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return f"Error processing your query: {str(e)}"

@tool
def code_converter(data: str) -> str:
    """
    Converts PostgreSQL analytics queries to ClickHouse analytics queries using specialized knowledge.

    Args:
        data: The PostgreSQL queries data including file paths, code content, and descriptions

    Returns:
        JSON-formatted converted queries with detailed conversion notes and warnings
    """
    bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

    try:
        # Validate input
        if not data or not data.strip():
            return json.dumps({"error": "No query data provided for conversion"})

        code_converter_agent = Agent(
            model=bedrock_model,
            system_prompt=CODE_CONVERTER_PROMPT,
        )

        result = code_converter_agent(data)

        # Ensure we return valid JSON
        try:
            # Try to parse the result as JSON to validate it
            json.loads(str(result))
            return str(result)
        except json.JSONDecodeError:
            # If the result is not valid JSON, wrap it in a structured format
            return json.dumps({
                "conversion_result": str(result),
                "note": "Raw conversion output - may need manual JSON parsing"
            })

    except Exception as e:
        error_response = {
            "error": f"Error during query conversion: {str(e)}",
            "error_type": type(e).__name__,
            "input_data_length": len(data) if data else 0
        }
        return json.dumps(error_response)

@tool
def code_writer(repo_path: str, converted_code: str) -> str:
    """
    Writes new code in the repository given the provided converted_code queries

    Args:
        repo_path: The path of the repository to write the code to
        converted_code: the converted queries

    Returns:
        The converted code diff
    """
    try:
        code_writer_agent = Agent(
            system_prompt=CODE_WRITER_PROMPT,
            tools=[shell, file_write, editor],
            callback_handler=None
        )

        result = code_writer_agent(
            f"In the repository located in {repo_path}, replace the postgres queries with the following clickhouse queries: {converted_code}"
        )
        return str(result)

    except Exception as e:
        return f"Error processing your query: {str(e)}"

class ReplicationMode(Enum):
    CDC = "cdc"
    SNAPSHOT = "snapshot"
    CDC_ONLY = "cdc_only"

@tool
def data_migrator(
    database_name: str,
    table_names: list[str],
    replication_mode: ReplicationMode = ReplicationMode.CDC,
    destination_database: str = "default"
) -> str:
    """
    Generates ClickPipe configuration for migrating data from Postgres to ClickHouse.

    Args:
        database_name: The name of the database to migrate
        table_names: A list of table names to migrate
        replication_mode: The replication mode to use. Defaults to CDC
        destination_database: The ClickHouse destination database. Defaults to 'default'

    Returns:
        JSON configuration for setting up a ClickPipe data migration
    """
    try:
        table_mappings = [
            {
                "sourceSchemaName": "public",
                "sourceTable": table_name,
                "targetTable": table_name
            }
            for table_name in table_names
        ]

        config = {
            "name": f"🚀 {database_name.title()} Migration",
            "source": {
                "postgres": {
                    "host": "localhost",
                    "port": 5432,
                    "database": database_name,
                    "credentials": {
                        "username": "postgres",
                        "password": "password"
                    },
                    "settings": {
                        "replicationMode": replication_mode.value
                    },
                    "tableMappings": table_mappings
                }
            },
            "destination": {
                "database": destination_database
            }
        }

        return json.dumps(config, indent=2)

    except Exception as e:
        return f"Error creating ClickPipe configuration: {str(e)}"

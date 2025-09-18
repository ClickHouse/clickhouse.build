from enum import Enum
import json
import os
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands_tools import shell, file_write, editor
from .prompts import CODE_ANALYSIS_PROMPT, CODE_WRITER_PROMPT, CODE_CONVERTER_PROMPT
from .utils import get_callback_handler, get_mcp_log_level


class ConvertedQuery(BaseModel):
    """Structured output model for a single converted query."""
    original_file_path: str = Field(description="Path to the file containing the original query")
    line_context: str = Field(description="Brief description of where the query appears in the file")
    original_query: str = Field(description="The original PostgreSQL query")
    converted_query: str = Field(description="The converted ClickHouse query")
    conversion_notes: List[str] = Field(description="List of key changes made and performance considerations")
    compatibility_warnings: List[str] = Field(description="Any functionality that might behave differently or require manual verification")


class QueryConversionResult(BaseModel):
    """Structured output model for the complete conversion result."""
    converted_queries: List[ConvertedQuery] = Field(description="List of all converted queries")
    summary: str = Field(description="Brief summary of the conversion process")
    total_queries_converted: int = Field(description="Total number of queries that were converted")
    overall_notes: List[str] = Field(description="General notes about the conversion process", default_factory=list)

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
            "FASTMCP_LOG_LEVEL": get_mcp_log_level(),
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
                callback_handler=get_callback_handler()
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
            error_result = QueryConversionResult(
                converted_queries=[],
                summary="No query data provided for conversion",
                total_queries_converted=0,
                overall_notes=["Error: No input data provided"]
            )
            return error_result.model_dump_json(indent=2)

        code_converter_agent = Agent(
            model=bedrock_model,
            system_prompt=CODE_CONVERTER_PROMPT,
            callback_handler=get_callback_handler()
        )

        # Use structured_output method to get structured response
        result = code_converter_agent.structured_output(QueryConversionResult, data)
        
        return result.model_dump_json(indent=2)

    except ValidationError as e:
        print(f"Validation Error: {e}")
        
        # Try to get the raw response from the agent for fallback processing
        try:
            # Make a regular call to get the raw response
            raw_result = code_converter_agent(data)
            raw_data = str(raw_result)
        except Exception:
            raw_data = "Could not retrieve raw response"
        
        # Create a structured error response that includes the raw data for workflow continuation
        validation_error_result = QueryConversionResult(
            converted_queries=[],
            summary="Validation error: The model output did not match the expected schema, but raw data is included",
            total_queries_converted=0,
            overall_notes=[
                "The language model's response could not be validated against the expected schema",
                f"Validation errors: {str(e)}",
                "Raw response data is included below for manual processing or workflow continuation",
                f"Raw response: {raw_data}",
                "This might indicate the model needs clearer instructions or the schema needs adjustment"
            ]
        )
        return validation_error_result.model_dump_json(indent=2)
        
    except Exception as e:
        print(f"Error: {e}")
        error_result = QueryConversionResult(
            converted_queries=[],
            summary=f"Error during query conversion: {str(e)}",
            total_queries_converted=0,
            overall_notes=[
                f"Error type: {type(e).__name__}",
                f"Input data length: {len(data) if data else 0}"
            ]
        )
        return error_result.model_dump_json(indent=2)

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
            callback_handler=get_callback_handler()
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

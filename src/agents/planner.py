import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List

from langfuse import get_client, observe
from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

from ..prompts.planner import get_system_prompt
from ..tools.common import glob, grep, read
from ..tui import (print_code, print_error, print_header, print_info,
                   print_list, print_summary_panel, print_table)
from ..utils import check_aws_credentials, get_callback_handler

logger = logging.getLogger(__name__)


def get_langfuse_client():
    """Get or create the Langfuse client instance."""
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    if langfuse_enabled:
        return get_client()
    return None


def conditional_observe(name: str):
    """Conditionally apply the @observe decorator based on LANGFUSE_ENABLED."""
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    if langfuse_enabled:
        return observe(name=name)
    else:
        # Return a no-op decorator when langfuse is disabled
        def decorator(func):
            return func
        return decorator


model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"


class AnalyticalQuery(BaseModel):
    """Represents a single analytical SQL query found in the codebase"""

    description: str = Field(description="Brief description of what the query does")
    code: str = Field(description="The SQL query code or ORM query code")
    location: str = Field(
        description="File path with line numbers (e.g., /app/api/route.ts:L60-65)"
    )


class QueryAnalysisResult(BaseModel):
    """Result of analyzing a codebase for analytical queries"""

    tables: List[str] = Field(description="List of database tables used in the queries")
    total_tables: int = Field(description="The number of database tables found")
    total_queries: int = Field(description="The number of analytical queries found")
    queries: List[AnalyticalQuery] = Field(
        description="List of analytical queries found"
    )


@tool
@conditional_observe(name="agent_planner")
def agent_planner(repo_path: str) -> str:
    logger.info(f"planner starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print_error(error_message)
        error_result = {
            "error": error_message,
            "tables": [],
            "total_tables": 0,
            "total_queries": 0,
            "queries": [],
        }
        return json.dumps(error_result, indent=2)

    bedrock_model = BedrockModel(model_id=model_id)

    try:
        print_header("Code Planner Agent", f"Repository: {repo_path}")

        analysis_agent = Agent(
            name="planner",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[glob, grep, read],
            callback_handler=get_callback_handler(),
        )

        start_time = time.time()

        # Run analysis
        analysis_result = str(analysis_agent(repo_path))
        logger.info(f"Analysis result from agent: {analysis_result[:500]}...")

        # Extract structured data
        extraction_agent = Agent(
            model=bedrock_model,
            system_prompt="Extract the analytical queries into structured format. Only include queries that were found in the codebase with real file locations.",
        )

        result = extraction_agent.structured_output(
            QueryAnalysisResult,
            f"Extract all analytical queries from this analysis:\n\n{analysis_result}",
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Display results
        if isinstance(result, QueryAnalysisResult):
            # Log metrics for Langfuse
            logger.info(
                f"Analysis complete: {result.total_queries} queries, "
                f"{result.total_tables} tables, {elapsed_time:.2f}s"
            )

            # Display summary
            summary_data = {
                "Total Queries": result.total_queries,
                "Total Tables": result.total_tables,
                "Execution Time": f"{elapsed_time:.2f}s ({elapsed_time/60:.2f}m)",
            }
            print_summary_panel(summary_data, title="Analysis Summary")

            # Display tables found
            if result.tables:
                print_list(result.tables, title="Tables Found:")

            # Display queries table
            if result.queries:
                queries_data = []
                for idx, query in enumerate(result.queries, 1):
                    code_preview = (
                        query.code[:100] + "..."
                        if len(query.code) > 100
                        else query.code
                    )
                    queries_data.append(
                        {
                            "#": str(idx),
                            "description": query.description,
                            "location": query.location,
                            "code": code_preview,
                        }
                    )

                columns = {
                    "#": {"header": "#", "style": "dim", "width": 4},
                    "description": {"header": "Description", "style": "white"},
                    "location": {"header": "Location", "style": "cyan"},
                    "code": {"header": "Code Preview", "style": "yellow"},
                }
                print_table(
                    queries_data,
                    columns,
                    title="Analytical Queries Found",
                    show_lines=True,
                )

            result_json = result.model_dump_json(indent=2)

            # Display the full JSON result
            print_code(result_json, language="json", title="Full JSON Result")
        else:
            result_json = json.dumps(
                {
                    "error": "Unexpected result type",
                    "tables": [],
                    "total_tables": 0,
                    "total_queries": 0,
                    "queries": [],
                },
                indent=2,
            )
            print_error("Unexpected result type")

        # Save plan file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        planner_dir = Path(repo_path) / ".chbuild" / "planner"
        planner_dir.mkdir(parents=True, exist_ok=True)

        plan_file = planner_dir / f"plan_{timestamp}.json"
        plan_file.write_text(result_json)

        print_info(str(plan_file), label="Plan saved to")

        # Flush Langfuse data
        langfuse_client = get_langfuse_client()
        if langfuse_client:
            langfuse_client.flush()

        return result_json

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
        print_error(str(e))

        error_result = {
            "error": str(e),
            "tables": [],
            "total_tables": 0,
            "total_queries": 0,
            "queries": [],
        }

        # Flush Langfuse data
        langfuse_client = get_langfuse_client()
        if langfuse_client:
            langfuse_client.flush()

        return json.dumps(error_result, indent=2)

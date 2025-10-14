import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

from ..logging_config import get_current_log_file
from ..prompts.scanner import get_system_prompt
from ..tools.common import glob, grep, read
from ..tui import (print_code, print_error, print_header, print_info,
                   print_list, print_summary_panel, print_table)
from ..utils import check_aws_credentials, get_callback_handler
from ..utils.langfuse import conditional_observe, get_langfuse_client

logger = logging.getLogger(__name__)


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
@conditional_observe(name="agent_scanner")
def agent_scanner(repo_path: str) -> str:
    logger.info(f"scanner starting analysis of repository: {repo_path}")

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
        print_header("Code Scanner Agent", f"Repository: {repo_path}")

        analysis_agent = Agent(
            name="scanner",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[glob, grep, read],
            callback_handler=get_callback_handler(),
        )

        start_time = time.time()

        analysis_result = str(analysis_agent(repo_path))
        logger.info(f"Analysis result from agent: {analysis_result[:500]}...")

        extraction_agent = Agent(
            model=bedrock_model,
            system_prompt="Extract the analytical queries into structured format. Only include queries that were found in the codebase with real file locations. You do not have to print it",
        )

        result = extraction_agent.structured_output(
            QueryAnalysisResult,
            f"Extract all analytical queries from this analysis:\n\n{analysis_result}",
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        if isinstance(result, QueryAnalysisResult):
            logger.info(
                f"Analysis complete: {result.total_queries} queries, "
                f"{result.total_tables} tables, {elapsed_time:.2f}s"
            )

            summary_data = {
                "Total Queries": result.total_queries,
                "Total Tables": result.total_tables,
                "Execution Time": f"{elapsed_time:.2f}s ({elapsed_time/60:.2f}m)",
            }
            print_summary_panel(summary_data, title="Analysis Summary")

            if result.tables:
                print_list(result.tables, title="Tables Found:")

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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scanner_dir = Path(repo_path) / ".chbuild" / "scanner"
        scanner_dir.mkdir(parents=True, exist_ok=True)

        scan_file = scanner_dir / f"scan_{timestamp}.json"
        scan_file.write_text(result_json)

        print_info(str(scan_file), label="Scan saved to")

        log_file = get_current_log_file()
        if log_file:
            print_info(log_file, label="Logs saved to")

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

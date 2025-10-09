import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

from ..prompts.planner import get_system_prompt
from ..tools.common import glob, grep, read
from ..utils import check_aws_credentials, get_callback_handler

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
def agent_planner(repo_path: str) -> str:
    logger.info(f"planner starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    bedrock_model = BedrockModel(model_id=model_id)

    try:
        analysis_agent = Agent(
            name="planner",
            model=bedrock_model,
            system_prompt=get_system_prompt(repo_path),
            tools=[glob, grep, read],
            callback_handler=get_callback_handler(),
        )

        start_time = time.time()
        logger.info(f"=== CODE PLANNER STARTED ===")

        analysis_result = str(analysis_agent(repo_path))

        logger.info(f"Analysis result from agent: {analysis_result[:500]}...")

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

        logger.info(f"=== CODE PLANNER COMPLETED ===")
        logger.info(f"Repository: {repo_path}")
        logger.info(
            f"⏱️  Total execution time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)"
        )
        print(f"\n⏱️  Total execution time: {elapsed_time:.2f} seconds\n")

        # Prepare result JSON
        if isinstance(result, QueryAnalysisResult):
            result_json = result.model_dump_json(indent=2)
        else:
            result_json = json.dumps(
                {"error": "Unexpected result type", "result": str(result)}
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        planner_dir = Path(repo_path) / ".chbuild" / "planner"
        planner_dir.mkdir(parents=True, exist_ok=True)

        plan_file = planner_dir / f"plan_{timestamp}.json"
        plan_file.write_text(result_json)
        logger.info(f"Plan saved to: {plan_file}")

        return result_json

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
        return f"Error processing your query: {str(e)}"

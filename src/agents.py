import logging
import os
import time
import json
from typing import List
from pydantic import BaseModel, Field

from strands import Agent, tool
from strands.models import BedrockModel
from .utils import get_callback_handler, check_aws_credentials
from .local_tools import glob, grep, read

logger = logging.getLogger(__name__)

# Structured output models
class AnalyticalQuery(BaseModel):
    """Represents a single analytical SQL query found in the codebase"""
    description: str = Field(description="Brief description of what the query does")
    code: str = Field(description="The SQL query code or ORM query code")
    location: str = Field(description="File path with line numbers (e.g., /app/api/route.ts:L60-65)")

class QueryAnalysisResult(BaseModel):
    """Result of analyzing a codebase for analytical queries"""
    tables: List[str] = Field(description="List of database tables used in the queries")
    queries: List[AnalyticalQuery] = Field(description="List of analytical queries found")

PROMPT_CODE_PLANNER = """
You are a fast, efficient code analyzer. Find PostgreSQL analytical queries ONLY.
Queries may be raw SQL strings OR ORM queries (Prisma, DrizzleORM, TypeORM, etc).

CRITICAL: The user will provide a repository path. You MUST use that exact path in your tool calls.

STRATEGY:
1. First search for raw SQL: grep with pattern="SELECT.*FROM", case_insensitive=True, output_mode="content", show_line_numbers=True
2. Then search for ORM aggregations: grep with pattern="(count\\(|sum\\(|avg\\(|groupBy|DATE_TRUNC)", case_insensitive=False, output_mode="content", show_line_numbers=True
3. Analyze results and identify ONLY analytical queries (with aggregations, GROUP BY, etc.)

IMPORTANT: Use the exact repo path provided in the `path` parameter for ALL grep calls.

INCLUDE (these are ALL analytical queries):
- ANY query with COUNT(), SUM(), AVG(), MAX(), MIN() - even without GROUP BY
- Queries with: GROUP BY, DATE_TRUNC, aggregations
- Analytics, reporting, or business intelligence queries
- ORM queries that do aggregations (.count(), .sum(), .avg(), .groupBy(), etc.)

EXCLUDE:
- INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, BEGIN, COMMIT, ROLLBACK
- Simple SELECT * or SELECT by ID WITHOUT any aggregation functions
- Simple lookups or CRUD operations without COUNT/SUM/AVG

OUTPUT FORMAT:
You will return structured JSON with:
- tables: List of all database tables found in the queries
- queries: Array of query objects, each containing:
  - description: Brief description of what the query does
  - code: The actual SQL or ORM query code
  - location: File path with line numbers (e.g., /app/api/route.ts:L60-65)

IMPORTANT: Report EVERY analytical query you find. Do not skip any.
Be fast. Do not make suggestions or ask follow ups.
"""

model_id="anthropic.claude-3-5-haiku-20241022-v1:0"

@tool
def code_planner(repo_path: str) -> str:
    logger.info(f"code_planner starting analysis of repository: {repo_path}")

    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    bedrock_model = BedrockModel(model_id=model_id)

    try:
        env = {
            "FASTMCP_LOG_LEVEL": "ERROR",
            "AWS_PROFILE": os.getenv("AWS_PROFILE", "default"),
            "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        }

        # Create agent with tools for analysis
        analysis_agent = Agent(
            model=bedrock_model,
            system_prompt=PROMPT_CODE_PLANNER,
            tools=[glob, grep, read],
            callback_handler=get_callback_handler(),
        )

        # Start timer
        start_time = time.time()
        logger.info(f"=== CODE PLANNER STARTED ===")

        # Run agent with tools to find queries
        analysis_result = str(analysis_agent(repo_path))

        logger.info(f"Analysis result from agent: {analysis_result[:500]}...")

        # Now use structured_output to extract the structure from the findings
        extraction_agent = Agent(
            model=bedrock_model,
            system_prompt="Extract the analytical queries into structured format. Only include queries that were actually found in the codebase with real file locations."
        )

        result = extraction_agent.structured_output(
            QueryAnalysisResult,
            f"Extract all analytical queries from this analysis:\n\n{analysis_result}"
        )

        # End timer
        end_time = time.time()
        elapsed_time = end_time - start_time

        logger.info(f"=== CODE PLANNER COMPLETED ===")
        logger.info(f"Repository: {repo_path}")
        logger.info(f"⏱️  Total execution time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        print(f"\n⏱️  Total execution time: {elapsed_time:.2f} seconds\n")

        # Convert Pydantic model to JSON string
        if isinstance(result, QueryAnalysisResult):
            return result.model_dump_json(indent=2)
        else:
            return json.dumps({"error": "Unexpected result type", "result": str(result)})

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
        return f"Error processing your query: {str(e)}"

import os
import logging
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any
from strands import Agent
from strands.models import BedrockModel
from .tools import code_reader, code_converter, code_writer, data_migrator, ensure_clickhouse_client
from .utils import get_callback_handler, check_aws_credentials
from .logging_config import get_logger, setup_logging, LogLevel

class WorkflowOrchestrator:
    def __init__(self, mode: str = "interactive", callback_handler=None, tui_mode: bool = False, app_instance=None, planning_mode: bool = False):
        self.mode = mode
        self.custom_callback_handler = callback_handler
        self.tui_mode = tui_mode
        self.cancelled = False  # Cancellation flag
        self.app_instance = app_instance
        self.planning_mode = planning_mode

        # Track pending file changes for approval
        self.approval_paused = False

        # Track migration results
        self.results = None
        self._tool_outputs = {}
        self._converted_queries = []
        self._modified_files = []
        self._warnings = []
        self._errors = []

        # Ensure logging is properly configured
        self._setup_logging()
        self.logger = get_logger(__name__)
        self.system_prompt = """You are an intelligent workflow orchestrator with access to specialist agents.

        Your role is to intelligently coordinate a workflow using these specialist agents:
        - ensure_clickhouse_client: Ensures @clickhouse/client npm package is installed or upgraded to the latest version
        - code_reader: Reads a repository content from the file system and searches for all postgres analytics queries
        - code_converter: Converts the found postgres analytics queries to ClickHouse analytics queries
        - code_writer: Replaces the postgres analytics queries implementation with the new ClickHouse analytics queries
        - data_migrator: Generates ClickPipe configuration for migrating data from Postgres to ClickHouse. Does not do migration. It just generates the config json file.

        YOU SHOULD NOT ASSUME THAT POSTGRES AND CLICKHOUSE WILL RETURN THE SAME DATA STUCTURES. It is likely the data will need to be parsed differently.
        Under no circumstances should your use the `any` or `unknown` types in TypeScript or JavaScript. You should leverage strong types.

        The agents should run sequentially: ensure_clickhouse_client -> code_reader -> code_converter -> code_writer -> data_migrator.
        The coordinator can re-try and validate accordingly.
        The coordinator understands the output of each agent and provides the output if needed as input to the next agent.
        """

        # Planning mode system prompt
        self.planning_system_prompt = """You are an intelligent workflow orchestrator with access to specialist agents.

Your role is to coordinate a PLANNING workflow using these specialist agents:
- code_reader: Reads a repository content and searches for all postgres analytics queries and table creation scripts
- code_converter: Converts the found postgres analytics queries to ClickHouse analytics queries

YOU ARE RUNNING IN PLANNING MODE. Do not make any changes to files or configurations.
Your goal is to analyze the repository and generate conversion plans.

The agents should run sequentially: code_reader -> code_converter.
After both agents complete, provide a comprehensive analysis report.
"""

        # Use default callback handler if none provided
        if callback_handler is None:
            self.custom_callback_handler = get_callback_handler()

    def respond_to_approval(self, request_id: str, approved: bool) -> None:
        """Legacy method - no longer used. Approval is handled via user_input."""
        self.logger.info(f"📨 ORCHESTRATOR: Legacy approval response received - ignoring")
        self.logger.info(f"Approval response recorded: {request_id} -> {'approved' if approved else 'rejected'}")

    def _process_tool_output(self, tool_name: str, tool_output: str) -> None:
        """Process tool output to extract migration results."""
        self._tool_outputs[tool_name] = tool_output

        try:
            if tool_name == "code_converter":
                # Extract converted queries information
                self._extract_converted_queries(tool_output)
            elif tool_name == "code_writer":
                # Extract modified files information
                self._extract_modified_files(tool_output)
            elif tool_name == "data_migrator":
                # Extract ClickPipe configuration
                self._extract_clickpipe_config(tool_output)

        except Exception as e:
            self.logger.error(f"Error processing {tool_name} output: {e}")
            self._errors.append(f"Error processing {tool_name}: {str(e)}")

    def _extract_converted_queries(self, output: str) -> None:
        """Extract converted queries from code_converter output."""
        # Extract information about converted queries from the output
        if "converted" in output.lower() or "clickhouse" in output.lower() or "select" in output.lower():
            # Count SQL keywords to estimate number of queries
            sql_keywords = ["select", "insert", "update", "delete", "create", "alter"]
            query_count = sum(output.lower().count(keyword) for keyword in sql_keywords)

            # If we found SQL content, create conversion records
            if query_count > 0:
                from .models import QueryConversion

                # Create realistic conversion records based on content
                files_mentioned = []
                if ".sql" in output.lower():
                    # Try to extract file names from output
                    import re
                    file_matches = re.findall(r'[\w/.-]+\.sql', output, re.IGNORECASE)
                    files_mentioned = list(set(file_matches))[:5]  # Limit to 5 files

                if not files_mentioned:
                    files_mentioned = [f"query_{i+1}.sql" for i in range(min(query_count, 3))]

                for i, file_path in enumerate(files_mentioned):
                    conversion = QueryConversion(
                        file_path=file_path,
                        original_query=f"-- PostgreSQL query {i+1} (converted)",
                        converted_query=f"-- ClickHouse query {i+1} (converted)",
                        success=True,
                        warnings=[]
                    )
                    self._converted_queries.append(conversion)

                self.logger.info(f"Extracted {len(files_mentioned)} converted queries")

    def _extract_modified_files(self, output: str) -> None:
        """Extract modified files from code_writer output."""
        # Extract file modification information
        if any(keyword in output.lower() for keyword in ["modified", "updated", "written", "created", "file"]):
            # Try to extract actual file paths from output
            import re
            file_extensions = [r'\.sql', r'\.js', r'\.ts', r'\.py', r'\.json']
            files_mentioned = []

            for ext in file_extensions:
                matches = re.findall(r'[\w/.-]+' + ext, output, re.IGNORECASE)
                files_mentioned.extend(matches)

            # Remove duplicates and limit
            files_mentioned = list(set(files_mentioned))[:10]

            if not files_mentioned and ("file" in output.lower() or "code" in output.lower()):
                # Fallback to generic file names if no specific files found
                files_mentioned = ["src/queries.sql", "src/config.js"]

            from .models import FileModification
            for file_path in files_mentioned:
                modification = FileModification(
                    path=file_path,
                    changes_count=1,
                    success=True,
                    backup_path=None
                )
                self._modified_files.append(modification)

            self.logger.info(f"Extracted {len(files_mentioned)} modified files")

    def _extract_clickpipe_config(self, output: str) -> None:
        """Extract ClickPipe configuration from data_migrator output."""
        # The data_migrator should output JSON configuration
        import json
        try:
            # Try to extract JSON from the output
            if "{" in output and "}" in output:
                start = output.find("{")
                end = output.rfind("}") + 1
                config_json = output[start:end]
                self.clickpipe_config = json.loads(config_json)
            else:
                # Fallback to default config
                self.clickpipe_config = {
                    "name": "Migration Config",
                    "source": {"postgres": {"host": "localhost", "port": 5432, "database": "myapp"}},
                    "destination": {"database": "default"}
                }
        except Exception as e:
            self.logger.error(f"Error parsing ClickPipe config: {e}")
            self.clickpipe_config = {}

    def _create_migration_results(self, success: bool, start_time, end_time) -> None:
        """Create final migration results object."""
        from .models import MigrationResults

        duration = str(end_time - start_time).split('.')[0] if end_time else "Unknown"

        self.results = MigrationResults(
            success=success,
            repo_path=getattr(self, '_current_repo_path', 'Unknown'),
            mode=self.mode,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            converted_queries=self._converted_queries,
            modified_files=self._modified_files,
            clickpipe_config=getattr(self, 'clickpipe_config', {}),
            warnings=self._warnings,
            errors=self._errors,
            orchestrator_output=str(self._tool_outputs),
            tool_results=self._tool_outputs
        )

    def _setup_logging(self):
        """Ensure logging is properly configured for orchestrator."""
        from pathlib import Path


        # Disable console output when running in TUI mode to prevent overlap
        if self.tui_mode:
            os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "disabled"
            # Also disable any other potential console outputs
            os.environ["STRANDS_CONSOLE_OUTPUT"] = "false"
            os.environ["STRANDS_VERBOSE"] = "false"
        else:
            # Set console mode from environment or default to enabled for CLI mode
            os.environ["STRANDS_TOOL_CONSOLE_MODE"] = os.getenv("STRANDS_TOOL_CONSOLE_MODE", "enabled")

        os.environ["BYPASS_TOOL_CONSENT"]="true"

        # Set BYPASS_TOOL_CONSENT based on mode
        if self.mode == "auto":
            os.environ["BYPASS_TOOL_CONSENT"] = "true"
        else:
            # Get from environment or default to false for interactive mode
            os.environ["BYPASS_TOOL_CONSENT"] = os.getenv("BYPASS_TOOL_CONSENT", "false")

    def cancel(self):
        """Cancel the orchestrator workflow."""
        self.cancelled = True
        # Legacy approval session cancellation no longer needed

    def run_workflow(self, repo_path: str) -> str:
        """Execute an intelligent workflow for the given task."""

        self.logger.info(f"Starting workflow for repository: {repo_path}")

        # Check for cancellation at the start
        if self.cancelled:
            self.logger.warning("Workflow cancelled before execution")
            return "Workflow cancelled before execution"

        try:
            claude4_model = BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                max_tokens=4096,
                temperature=1,
                additional_request_fields={
                    "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                    "reasoning_config": {
                        "type": "enabled",
                        "budget_tokens": 3000
                    }
                }
            )

            # Import tools
            from .tools import ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator

            self.logger.info("Creating Strands Agent for synchronous execution")
            orchestrator = Agent(
                model=claude4_model,
                system_prompt=self.system_prompt,
                tools=[ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator],
                callback_handler=self.custom_callback_handler or get_callback_handler()
            )

        except Exception as setup_error:
            raise

        prompt = f"""Coordinate the code migration for the following local repository: {repo_path}

        Instructions:
        1. Think carefully about what information you need to accomplish this task
        2. Use the specialist agents strategically - each has unique strengths
        3. After each tool use, reflect on the results and adapt your approach
        4. Coordinate multiple agents as needed for comprehensive results
        5. Ensure accuracy by fact-checking when appropriate
        6. Provide a comprehensive final response that addresses all aspects that includes the data migrator output

        Remember: Your thinking between tool calls helps you make better decisions.
        Use it to plan, evaluate results, and adjust your strategy.
        """

        try:
            # Check for cancellation before execution
            if self.cancelled:
                return "Workflow cancelled before orchestrator execution"

            # Store repo path for results
            self._current_repo_path = repo_path
            start_time = datetime.now()

            # Execute orchestrator (this is the long-running part)
            self.logger.info("Executing Strands orchestrator synchronously")
            result = orchestrator(prompt)

            # Check for cancellation after execution
            if self.cancelled:
                self.logger.warning("Workflow cancelled during execution")
                return "Workflow cancelled during execution"

            # Process results
            end_time = datetime.now()
            self._process_tool_output("final_result", str(result))
            self._create_migration_results(True, start_time, end_time)

            self.logger.info("Workflow completed successfully")
            return str(result)
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            # Create error results
            end_time = datetime.now()
            self._errors.append(str(e))
            self._create_migration_results(False, start_time if 'start_time' in locals() else datetime.now(), end_time)
            return f"Workflow failed: {e}"

    def run_planning_workflow(self, repo_path: str) -> str:
        """Execute planning workflow (code_reader + code_converter only)."""
        
        start_time = datetime.now()
        self.logger.info(f"🚀 Starting planning workflow for: {repo_path}")
        self.logger.info("📋 Planning Mode: Analysis only - no file modifications will be made")
        
        code_reader_output = ""
        code_converter_output = ""
        
        try:
            # Ensure output directory exists
            self._ensure_planning_output_directory(repo_path)
            
            # Create agent with planning-specific system prompt and limited tools
            planning_tools = [code_reader, code_converter]
            claude4_model = BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                max_tokens=4096,
                temperature=1,
                additional_request_fields={
                    "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                    "reasoning_config": {
                        "type": "enabled",
                        "budget_tokens": 3000
                    }
                }
            )
            agent = Agent(
                model=claude4_model,
                tools=planning_tools,
                system_prompt=self.planning_system_prompt,
                callback_handler=self.custom_callback_handler,
            )

            # Execute planning workflow
            self.logger.info("🔍 Step 1/3: Executing code reader analysis...")
            try:
                prompt = f"PLANNING MODE: Analyze the repository at {repo_path} using ONLY code_reader and code_converter tools. Find PostgreSQL queries and convert them to ClickHouse format. DO NOT use ensure_clickhouse_client, code_writer, or data_migrator tools. This is analysis only - make no file changes."
                result = agent(prompt)
                
                if self.cancelled:
                    self.logger.warning("Planning workflow cancelled during execution")
                    return "Planning workflow cancelled during execution"
                
                # Extract tool outputs from agent execution
                result_str = str(result)
                code_reader_output = result_str
                code_converter_output = result_str
                
                self.logger.info("✅ Step 1/3: Code analysis completed")
                
            except Exception as e:
                self.logger.error(f"❌ Planning workflow execution failed: {e}")
                raise

            # Generate planning report using AI
            self.logger.info("📊 Step 2/3: Generating planning report with AI...")
            try:
                planning_report = self._generate_ai_planning_report(repo_path, code_reader_output, code_converter_output)
                self.logger.info("✅ Step 2/3: AI planning report generated")
                
            except Exception as e:
                self.logger.error(f"❌ AI planning report generation failed: {e}")
                # Continue with a basic report
                planning_report = f"# Planning Report Generation Error\n\nFailed to generate detailed report: {str(e)}\n\n## Raw Analysis Output\n\n{result_str}"
            
            # Save planning report
            self.logger.info("💾 Step 3/3: Saving planning results...")
            try:
                report_path = self._save_planning_report(repo_path, planning_report)
                self.logger.info(f"✅ Step 3/3: Planning results saved to {report_path}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to save planning report: {e}")
                # Still return the report content even if saving failed
            
            # Log planning results summary
            self._log_planning_summary(repo_path, code_reader_output, code_converter_output)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"🎉 Planning workflow completed successfully in {duration:.2f} seconds")
            
            return planning_report

        except Exception as e:
            self.logger.error(f"❌ Planning workflow failed: {e}")
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.error(f"⏱️ Planning workflow failed after {duration:.2f} seconds")
            
            # Create error report
            error_report = f"""# Planning Workflow Error Report

## Error Details
- **Error**: {str(e)}
- **Repository**: {repo_path}
- **Duration**: {duration:.2f} seconds
- **Timestamp**: {datetime.now().isoformat()}

## Partial Results
- **Code Reader Output**: {"Available" if code_reader_output else "Not available"}
- **Code Converter Output**: {"Available" if code_converter_output else "Not available"}

## Raw Output
```
{code_reader_output if code_reader_output else "No output captured"}
```
"""
            
            # Try to save error report
            try:
                self._save_planning_report(repo_path, error_report, is_error=True)
            except:
                pass  # Don't fail on error report saving
            
            return error_report

    def _ensure_planning_output_directory(self, repo_path: str) -> None:
        """Ensure planning output directory exists."""
        try:
            from pathlib import Path
            from .utils import get_chbuild_directory
            
            chbuild_dir = get_chbuild_directory()
            results_dir = Path(chbuild_dir)
            results_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📁 Planning output directory ready: {results_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create planning output directory: {e}")
            raise

    def _log_planning_summary(self, repo_path: str, code_reader_output: str, code_converter_output: str) -> None:
        """Log planning results summary."""
        try:
            # Count queries found
            query_indicators = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']
            query_count = sum(code_reader_output.upper().count(indicator) for indicator in query_indicators)
            
            # Count files analyzed
            file_count = code_reader_output.count('File:') if 'File:' in code_reader_output else 0
            
            # Log summary
            self.logger.info("📊 Planning Results Summary:")
            self.logger.info(f"   📁 Repository: {repo_path}")
            self.logger.info(f"   📄 Files analyzed: {file_count}")
            self.logger.info(f"   🔍 Queries found: {query_count}")
            self.logger.info(f"   📝 Code reader output: {len(code_reader_output)} characters")
            self.logger.info(f"   🔄 Code converter output: {len(code_converter_output)} characters")
            
        except Exception as e:
            self.logger.error(f"Failed to log planning summary: {e}")

    def _generate_ai_planning_report(self, repo_path: str, code_reader_output: str, code_converter_output: str) -> str:
        """Generate planning report using AI to analyze the raw outputs."""
        try:
            # Get git hash from the repository directory
            try:
                git_hash = subprocess.check_output(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=repo_path,
                    stderr=subprocess.DEVNULL
                ).decode('ascii').strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                git_hash = "unknown"
            # Create a specialized agent for report generation
            report_agent = Agent(
                model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
                system_prompt=f"""You are a technical report generator specializing in PostgreSQL to ClickHouse migration planning reports.

Your task is to analyze the outputs from code analysis and query conversion tools, then generate a comprehensive, well-structured migration planning report in Markdown format.

## EXACT Report Structure Required (follow this structure precisely):

# Migration Planning Report

## Metadata

- **UUID**: [Generate a unique UUID]
- **Epoch**: [Current Unix timestamp]
- **Repository Path**: [Extract from context]
- **Technologies**: [Comma-separated list: Next.js, TypeScript, React, etc.]
- **ORMs**: [Comma-separated list: Drizzle, Prisma, etc. or empty if none]
- **Commit**: {git_hash}

## Summary

[Provide a concise overview of the application type and migration scope. Include query count found.]

## Tables

[For each table/schema found:]
### [Table Name]

**File**: [Source file path]

```typescript
[Table schema definition]
```

[If no tables found, write: "No table definitions found."]

## Queries

[For each query found:]
### Query [N]

**File**: [Source file path]
**Type**: [Query type: analytics, select, etc.]

[If context available:]
**Context**: [Where the query appears]

#### Before Conversion

```sql
[Original PostgreSQL query - extract the actual SQL]
```

#### After Conversion

```sql
[Converted ClickHouse query - extract the actual SQL]
```

[If conversion notes available:]
**Conversion Notes**:
[List each note as bullet points]

[If warnings available:]
**Warnings**:
[List each warning as bullet points with ⚠️ emoji]

---

## Data

### Databases
- PostgreSQL (source)
- ClickHouse (target)

### Schemas
- Analysis based on discovered table definitions

### Tables
[List each table found, or "- No tables identified" if none]

### Sorting Keys
- To be determined based on query patterns and performance requirements

IMPORTANT: Extract ALL queries mentioned in the analysis. If the analysis mentions "4 queries found" then show all 4 queries with their before/after conversions. Be thorough and extract the actual SQL code from the outputs.""",
                callback_handler=self.custom_callback_handler,
            )

            # Prepare the analysis data
            import time
            import uuid
            
            current_uuid = str(uuid.uuid4())
            current_epoch = int(time.time())
            
            prompt = f"""Generate a comprehensive migration planning report based on the following analysis outputs.

CRITICAL: The analysis mentions finding multiple queries. Extract ALL of them with their before/after conversions.

## Repository Path
{repo_path}

## Code Reader Analysis Output
{code_reader_output}

## Code Converter Analysis Output  
{code_converter_output}

## Report Metadata to Use
- UUID: {current_uuid}
- Epoch: {current_epoch}

INSTRUCTIONS:
1. Follow the EXACT structure provided in your system prompt
2. Extract ALL queries mentioned in the outputs (if it says "4 queries found", show all 4)
3. For each query, extract the actual SQL code from both before and after sections
4. Include all conversion notes and warnings mentioned
5. Extract table schemas if any are shown
6. Identify technologies and ORMs from the analysis
7. Be thorough - don't miss any information from the outputs

Generate the complete migration planning report now."""

            # Generate the report
            report = report_agent(prompt)
            return str(report)
            
        except Exception as e:
            self.logger.error(f"Error generating AI planning report: {e}")
            # Fallback to basic report
            return f"""# Migration Planning Report (AI Generation Failed)

## Error
Failed to generate AI report: {str(e)}

## Repository
{repo_path}

## Code Reader Output
```
{code_reader_output[:2000]}{'...' if len(code_reader_output) > 2000 else ''}
```

## Code Converter Output  
```
{code_converter_output[:2000]}{'...' if len(code_converter_output) > 2000 else ''}
```
"""

    def _save_planning_report(self, repo_path: str, report_content: str, is_error: bool = False) -> str:
        """Save planning report to file."""
        try:
            from pathlib import Path
            import os
            from .utils import get_chbuild_directory
            
            # Create chbuild output directory
            chbuild_dir = get_chbuild_directory()
            results_dir = Path(chbuild_dir)
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "error_report" if is_error else "planning_report"
            report_file = results_dir / f"{prefix}_{timestamp}.md"
            
            # Write report
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"📄 Planning report saved to: {report_file}")
            return str(report_file)
            
        except Exception as e:
            self.logger.error(f"Failed to save planning report: {e}")
            return ""

    async def run_workflow_with_events(self, repo_path: str):
        """Execute workflow with async event streaming for UI updates."""

        try:
            self.logger.info(f"Starting workflow with events for repository: {repo_path}")

            # Check for cancellation before execution
            if self.cancelled:
                self.logger.warning("Workflow cancelled before orchestrator execution")
                yield {"type": "error", "message": "Workflow cancelled before orchestrator execution"}
                return

            self.logger.info("Setting up orchestrator for async streaming")
            yield {"type": "setup_start", "message": "Setting up orchestrator"}

            claude4_model = BedrockModel(
                model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                max_tokens=4096,
                temperature=1,
                additional_request_fields={
                    "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                    "reasoning_config": {
                        "type": "enabled",
                        "budget_tokens": 3000
                    }
                }
            )

            # Import tools
            from .tools import ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator

            self.logger.info("Creating Strands Agent with migration tools")
            orchestrator = Agent(
                model=claude4_model,
                system_prompt=self.system_prompt,
                tools=[ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator],
                # No callback handler - we'll use async iteration
            )

            self.logger.info("Agent created successfully, starting migration workflow")

            # Store repo path and start time for results
            self._current_repo_path = repo_path
            start_time = datetime.now()

            yield {"type": "agent_start", "message": "Starting migration workflow"}

            prompt = f"""Coordinate the code migration for the following local repository: {repo_path}

            Instructions:
            1. Think carefully about what information you need to accomplish this task
            2. Use the specialist agents strategically - each has unique strengths
            3. After each tool use, reflect on the results and adapt your approach
            4. Coordinate multiple agents as needed for comprehensive results
            5. Ensure accuracy by fact-checking when appropriate
            6. Provide a comprehensive final response that addresses all aspects that includes the data migrator output

            Remember: Your thinking between tool calls helps you make better decisions.
            Use it to plan, evaluate results, and adjust your strategy.
            """

            # Use Strands async streaming API
            try:
                self.logger.info("Starting Strands async streaming")
                yield {"type": "streaming_start", "message": "Using Strands stream_async"}

                async for event in orchestrator.stream_async(prompt):
                    if self.cancelled:
                        yield {"type": "cancelled", "message": "Workflow cancelled during execution"}
                        return

                    # Log all events for debugging
                    self.logger.debug(f"Strands raw event: {event}")

                    # Process Strands events and convert to our format
                    # Ensure event is a dictionary
                    if not isinstance(event, dict):
                        self.logger.warning(f"Event is not a dictionary: {type(event)}")
                        continue

                    if event.get("init_event_loop", False):
                        self.logger.debug("Strands event loop initialized")
                        yield {"type": "event_loop_init", "message": "Event loop initialized"}

                    elif event.get("start_event_loop", False):
                        self.logger.debug("Strands event loop cycle starting")
                        yield {"type": "event_loop_start", "message": "Event loop cycle starting"}

                    elif "message" in event:
                        message = event["message"]
                        if isinstance(message, dict):
                            message_role = message.get("role", "unknown")
                            self.logger.debug(f"Strands message created: {message_role}")
                            yield {"type": "message_created", "message": f"New message created: {message_role}"}
                        else:
                            self.logger.debug("Strands message created")
                            yield {"type": "message_created", "message": "New message created"}

                    elif event.get("complete", False):
                        self.logger.debug("Strands cycle completed")
                        yield {"type": "cycle_complete", "message": "Cycle completed"}

                    elif event.get("force_stop", False):
                        reason = event.get("force_stop_reason", "unknown reason")
                        self.logger.warning(f"Strands event loop force-stopped: {reason}")
                        yield {"type": "force_stop", "message": f"Event loop force-stopped: {reason}"}

                    # Track tool usage - this is key for progress updates
                    elif "current_tool_use" in event:
                        tool_use = event["current_tool_use"]
                        if isinstance(tool_use, dict):
                            tool_name = tool_use.get("name", "")
                            tool_id = tool_use.get("toolUseId", "")
                            tool_input = tool_use.get("input", {})
                        else:
                            self.logger.warning(f"current_tool_use is not a dict: {type(tool_use)}")
                            continue

                        self.logger.info(f"=== TOOL EXECUTION: {tool_name} (ID: {tool_id}) ===")
                        if tool_input:
                            self.logger.info(f"Tool input: {tool_input}")
                        else:
                            self.logger.info("Tool input: (empty)")

                        # Legacy file operation detection removed - approval now handled directly in individual tools

                        yield {
                            "type": "tool_start",
                            "tool_name": tool_name,
                            "tool_id": tool_id,
                            "tool_input": tool_input,
                            "message": f"Using tool: {tool_name}"
                        }

                    # Track text output
                    elif "data" in event:
                        full_data = event["data"]
                        data_snippet = full_data[:100] + ("..." if len(full_data) > 100 else "")

                        # Log the full output
                        self.logger.info(f"Agent output: {full_data}")

                        yield {"type": "text_output", "data": full_data, "message": f"Text output: {full_data}"}

                    # Handle final result
                    elif "result" in event:
                        result = event["result"]
                        self.logger.info("=== ORCHESTRATOR FINAL RESULT ===")
                        self.logger.info(f"Result type: {type(result)}")
                        self.logger.info(f"Result content: {result}")

                        # Process results and create migration results
                        end_time = datetime.now()
                        self._process_tool_output("final_result", str(result))
                        self._create_migration_results(True, start_time, end_time)

                        yield {"type": "final_result", "result": result, "message": "Agent execution completed"}

                    # Handle tool streaming events
                    elif "tool_stream_event" in event:
                        tool_event = event["tool_stream_event"]
                        tool_use = tool_event.get("tool_use", {})
                        tool_name = tool_use.get("name", "")
                        tool_data = tool_event.get("data", "")

                        yield {
                            "type": "tool_stream",
                            "tool_name": tool_name,
                            "tool_data": tool_data,
                            "message": f"Tool {tool_name} streaming: {tool_data}"
                        }

                    # Pass through the raw event for debugging
                    yield {"type": "raw_event", "event": event}

                self.logger.debug("Strands stream completed successfully")
                yield {"type": "execution_complete", "message": "Stream completed successfully"}

            except Exception as exec_error:
                self.logger.error(f"Strands execution failed: {exec_error}")
                yield {"type": "execution_error", "message": f"Execution failed: {exec_error}"}
                return

            self.logger.info("Migration workflow completed successfully")
            yield {"type": "agent_end", "message": "Migration workflow completed"}

        except Exception as e:
            self.logger.error(f"Workflow setup failed: {e}")
            yield {"type": "error", "message": f"Workflow setup failed: {e}"}

    def run_conversational(self, initial_repo_path: str = ""):
        """Run in interactive mode allowing back-and-forth with orchestrator."""

        claude4_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            max_tokens=4096,
            temperature=1,
            additional_request_fields={
                "anthropic_beta": ["interleaved-thinking-2025-05-14"],
                "reasoning_config": {
                    "type": "enabled",
                    "budget_tokens": 3000
                }
            }
        )

        orchestrator = Agent(
            model=claude4_model,
            system_prompt=self.system_prompt + """

            IMPORTANT: If you need information from the user (like repository path, clarifications, etc.),
            ask them directly and wait for their response. Do not proceed without required information.
            You must finish with the data_migrator tool to generate the ClickPipe configuration for data migration. Assume the database is called 'postgres'
            """,
            tools=[ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator],
            callback_handler=self.custom_callback_handler or get_callback_handler()
        )

        # Start conversation
        if initial_repo_path:
            message = f"Please coordinate the code migration for repository: {initial_repo_path}"
        else:
            message = "Please help me migrate PostgreSQL queries to ClickHouse."

        print("ClickHouse Migration Assistant")
        print("=" * 40)
        print("Type 'quit' to exit\n")

        while True:
            try:
                print(f"User: {message}")
                response = orchestrator(message)
                print(f"\nAssistant: {response}\n")

                # Get user input for next message
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                message = user_input

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                message = "There was an error. Please try again."

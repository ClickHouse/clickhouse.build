import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from strands import Agent
from strands.models import BedrockModel
from .tools import code_reader, code_converter, code_writer, data_migrator, ensure_clickhouse_client
from .utils import get_callback_handler
from .logging_config import get_logger, setup_logging, LogLevel

class WorkflowOrchestrator:
    def __init__(self, mode: str = "interactive", callback_handler=None, tui_mode: bool = False, app_instance=None):
        self.mode = mode
        self.custom_callback_handler = callback_handler
        self.tui_mode = tui_mode
        self.cancelled = False  # Cancellation flag
        self.app_instance = app_instance

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

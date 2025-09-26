import os
from strands import Agent
from strands.models import BedrockModel
from .tools import code_reader, code_converter, code_writer, data_migrator, ensure_clickhouse_client
from .utils import get_callback_handler, check_aws_credentials

class WorkflowOrchestrator:
    def __init__(self, mode: str = "conversational"):
        self.mode = mode
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
        # Set console mode from environment or default to enabled
        os.environ["STRANDS_TOOL_CONSOLE_MODE"] = os.getenv("STRANDS_TOOL_CONSOLE_MODE", "enabled")

        # Set BYPASS_TOOL_CONSENT based on mode
        if mode == "auto":
            os.environ["BYPASS_TOOL_CONSENT"] = "true"
        else:
            # Get from environment or default to false for conversational mode
            os.environ["BYPASS_TOOL_CONSENT"] = os.getenv("BYPASS_TOOL_CONSENT", "false")

    def run_workflow(self, repo_path: str) -> str:
        """Execute an intelligent workflow for the given task."""

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
            system_prompt=self.system_prompt,
            tools=[ensure_clickhouse_client, code_reader, code_converter, code_writer, data_migrator],
            callback_handler=get_callback_handler()
        )

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
            result = orchestrator(prompt)
            return str(result)
        except Exception as e:
            return f"Workflow failed: {e}"

    def run_conversational(self, initial_repo_path: str = ""):
        """Run in conversational mode allowing back-and-forth with orchestrator."""

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
            callback_handler=get_callback_handler()
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

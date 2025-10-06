from enum import Enum
import json
import logging
import os
import subprocess
import semver
import glob as glob_module
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from strands_tools import shell, http_request, file_write
from .utils import get_callback_handler, CONFIG, check_aws_credentials
from .prompts import CODE_ANALYSIS_PROMPT, CODE_WRITER_PROMPT, CODE_CONVERTER_PROMPT, DOCUMENTATION_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

@tool
def glob(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern in the specified directory.
    Similar to Claude Code's Glob tool for file pattern matching.

    Args:
        pattern: The glob pattern to match (e.g., "**/*.py", "*.js", "src/**/*.ts")
        path: The directory to search in (defaults to current directory)

    Returns:
        JSON string containing list of matching file paths sorted by modification time
    """
    try:
        search_path = Path(path).resolve()

        if not search_path.exists():
            return json.dumps({
                "error": f"Path does not exist: {path}",
                "files": []
            })

        # Use glob to find matching files
        matches = []
        full_pattern = str(search_path / pattern)

        for file_path in glob_module.glob(full_pattern, recursive=True):
            if os.path.isfile(file_path):
                matches.append({
                    "path": file_path,
                    "mtime": os.path.getmtime(file_path)
                })

        # Sort by modification time (most recent first)
        matches.sort(key=lambda x: x["mtime"], reverse=True)

        # Return just the paths
        file_paths = [m["path"] for m in matches]

        return json.dumps({
            "pattern": pattern,
            "search_path": str(search_path),
            "count": len(file_paths),
            "files": file_paths
        }, indent=2)

    except Exception as e:
        logger.error(f"Error in glob: {e}")
        return json.dumps({
            "error": str(e),
            "files": []
        })

def _get_user_approval(file_path: str, content: str, original_content: str = "", change_type: str = "update", detailed_prompt: str = None) -> str:
    """
    Get user approval using TUI InteractiveCLI widget or fallback to user_input.

    Args:
        file_path: Path of the file being changed
        content: New content for the file
        original_content: Original content (for updates)
        change_type: Type of change ("create", "update", "delete")

    Returns:
        User response string ('y' or 'n' or 'all')
    """
    try:
        # Try to use Chat UI approval system first
        try:
            from src.chat_ui.approval_integration import get_chat_approval

            approval_result = get_chat_approval(
                file_path=file_path,
                new_content=content,
                original_content=original_content,
                change_type=change_type,
                detailed_prompt=detailed_prompt
            )

            if approval_result is not None:
                logger.info(f"Using Chat UI for approval of {file_path}: {approval_result}")
                return 'y' if approval_result else 'n'

        except ImportError:
            # Chat UI not available, try TUI widget
            pass

        # Try to use InteractiveCLI widget for TUI mode
        try:
                # Use a simple synchronous approach with threading
                import threading
                import time

                response_container = {'response': None, 'received': False}

                def input_callback(user_input: str):
                    response_container['response'] = user_input.strip().lower()
                    response_container['received'] = True

                # Request input from the CLI widget
                request_id = cli_widget.request_input(prompt, input_callback)

                # Wait for response (with timeout)
                timeout = 60  # 60 seconds timeout
                start_time = time.time()

                while not response_container['received'] and (time.time() - start_time) < timeout:
                    time.sleep(0.1)

                if response_container['received']:
                    response = response_container['response']
                    if response in ['y', 'yes']:
                        logger.info(f"User approved change to {file_path}")
                        return 'y'
                    else:
                        logger.info(f"User rejected change to {file_path}")
                        return 'n'
                else:
                    logger.warning(f"Timeout waiting for user input for {file_path}")
                    return 'n'

        except ImportError:
            # Not in TUI mode, fall through to input()
            pass

        # Fallback to input() for CLI mode or if TUI widget not available
        logger.info(f"Using input() fallback for approval of {file_path}")
        # Use built-in input() instead of strands_tools user_input

        # Create a simple prompt
        prompt = f"""File Change Approval Required

File: {file_path}
Action: {change_type.title()} file
Size: {len(content)} characters

Do you want to proceed with this change?"""

        response = input(f"{prompt}\n\nApprove this change? (y/n): ")
        if response and response.strip().lower() in ['y', 'yes']:
            return 'y'
        else:
            return 'n'

    except Exception as e:
        logger.error(f"Error getting user approval for {file_path}: {e}")
        # Default to rejection on error
        return 'n'

@tool
def file_write_wrapper(path: str, content: str) -> str:
    """
    Write content to a file with user approval.

    Args:
        path: The file path to write to
        content: The content to write to the file

    Returns:
        str: Success message or error details
    """
    try:
        # Get the file operations manager
        agent = Agent(tools=[file_write])

        # Get original content if file exists for diff
        original_content = ""
        file_exists = os.path.exists(path)
        if file_exists:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read original file {path}: {e}")

        # Create a diff preview
        import difflib
        if file_exists and original_content:
            # Show diff for existing file
            diff_lines = list(difflib.unified_diff(
                original_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm=""
            ))
            diff_preview = "".join(diff_lines)  # First 50 lines
        else:
            # New file - show first part of content
            diff_preview = f"New file: {path}\n\n" + content[:1000]
            if len(content) > 1000:
                diff_preview += f"\n... ({len(content) - 1000} more characters)"

        # Display approval prompt and get user input
        approval_prompt = f"""[APPROVAL] File Write Approval Required

File: {path}
Size: {len(content)} characters
Action: {'Update existing file' if file_exists else 'Create new file'}

Changes to be made:
{diff_preview}

Do you want to proceed with this file write? (y/n/all)"""

        logger.info(f"[APPROVAL] APPROVAL REQUIRED: File write to {path}")
        logger.info(f"� APPPROVAL PROMPT:\n{approval_prompt}")

        # Get user approval
        change_type = "create" if not file_exists else "update"
        user_response = _get_user_approval(path, content, original_content, change_type, approval_prompt)
        # Check if user approved
        if user_response and user_response.lower() in ['y', 'yes']:
            # User approved - write the file using Strands file_write tool

            result = agent.tool.file_write(path=path, content=content)
            logger.info(f"✅ File write approved and completed: {path}")
            return f"✅ Successfully wrote to {path} (approved by user)"
        else:
            # User rejected or gave unclear response
            logger.info(f"❌ File write rejected by user: {path}")
            return f"❌ File write to {path} cancelled by user"

    except Exception as e:
        error_msg = f"File write failed for {path}: {e}"
        logger.error(error_msg)
        return error_msg

@tool
def code_reader(repo_path: str) -> str:
    """
    Code reader specialist that can search through a repository and find relevant content.

    Args:
        repo_path: The repository path of the repository to analyze

    Returns:
        Reading findings
    """
    logger.info(f"Code reader starting analysis of repository: {repo_path}")

    # Check AWS credentials before proceeding
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return f"Error: {error_message}"

    bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

    try:
        env = {
            "FASTMCP_LOG_LEVEL": "ERROR",
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
            logger.info(f"=== CODE READER COMPLETED ===")
            logger.info(f"Repository: {repo_path}")
            logger.info(f"Result length: {len(result)} characters")
            logger.info(f"Result preview: {result[:500]}{'...' if len(result) > 500 else ''}")
            return result

    except Exception as e:
        logger.error(f"Exception in code_reader: {type(e).__name__}: {e}")
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
    logger.info("Code converter starting PostgreSQL to ClickHouse conversion")
    # Check AWS credentials before proceeding
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        return json.dumps({"error": error_message})

    bedrock_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

    try:
        # Validate input
        if not data or not data.strip():
            return json.dumps({"error": "No query data provided for conversion"})

        code_converter_agent = Agent(
            model=bedrock_model,
            system_prompt=CODE_CONVERTER_PROMPT,
            callback_handler=get_callback_handler(),
            tools=[get_clickhouse_documentation]
        )

        result = code_converter_agent(data)

        logger.info("=== CODE CONVERTER COMPLETED ===")
        logger.info(f"Input data length: {len(data)} characters")
        logger.info(f"Result length: {len(str(result))} characters")
        logger.info(f"Result preview: {str(result)[:500]}{'...' if len(str(result)) > 500 else ''}")

        # Ensure we return valid JSON
        try:
            # Try to parse the result as JSON to validate it
            json.loads(str(result))
            logger.info("Code converter output is valid JSON")
            return str(result)
        except json.JSONDecodeError:
            # If the result is not valid JSON, wrap it in a structured format
            logger.warning("Code converter output was not valid JSON, wrapping in structured format")
            return json.dumps({
                "conversion_result": str(result),
                "note": "Raw conversion output - may need manual JSON parsing"
            })

    except Exception as e:
        logger.error(f"Error in code_converter: {type(e).__name__}: {e}")
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
    logger.info(f"Code writer starting to write converted code to repository: {repo_path}")

    try:
        # Import required components
        from strands import Agent
        import uuid

        logger.info("=== CODE WRITER STARTING ===")
        logger.info(f"Repository: {repo_path}")
        logger.info(f"Converted code length: {len(converted_code)} characters")

        # Use simple agent with approval-enabled tools
        # The file_write and editor tools now handle approval directly via user_input
        logger.info("Creating code writer agent with approval-enabled tools")

        # Create agent with approval-enabled tools (file_write and editor handle approval via user_input)
        code_writer_agent = Agent(
            system_prompt=CODE_WRITER_PROMPT,
            tools=[shell, file_write_wrapper],
            callback_handler=get_callback_handler()
        )

        prompt = f"In the repository located in {repo_path}, replace the postgres queries with the following clickhouse queries: {converted_code}"
        logger.info(f"Prompt: {prompt[:300]}{'...' if len(prompt) > 300 else ''}")

        # Execute the agent
        result = code_writer_agent(prompt)

        logger.info("=== CODE WRITER COMPLETED ===")
        logger.info(f"Result length: {len(str(result))} characters")
        logger.info(f"Result: {str(result)}")

        return str(result)

    except Exception as e:
        logger.error(f"Error in code_writer: {type(e).__name__}: {e}")

        # Enhanced error handling with context
        error_context = {
            'tool': 'code_writer',
            'repo_path': repo_path,
            'converted_code_length': len(converted_code) if converted_code else 0,
            'error_type': type(e).__name__
        }

        logger.error(f"Code writer error context: {error_context}")

        # Import traceback for detailed error logging
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

        # Check if this is an approval-related error
        if "approval" in str(e).lower() or "cancelled" in str(e).lower():
            return f"Code writer execution cancelled: {str(e)}"

        return f"Error processing your query: {str(e)}"

class ReplicationMode(Enum):
    CDC = "cdc"
    SNAPSHOT = "snapshot"
    CDC_ONLY = "cdc_only"

@tool
def data_migrator(
    database_name: str,
    schema_tables: dict[str, list[str]],
    replication_mode: ReplicationMode = ReplicationMode.CDC,
    destination_database: str = "default"
) -> str:
    """
    Generates ClickPipe configuration for migrating data from Postgres to ClickHouse.

    Args:
        database_name: The name of the database to migrate
        schema_tables: A dictionary mapping schema names to lists of table names
        replication_mode: The replication mode to use. Defaults to CDC
        destination_database: The ClickHouse destination database. Defaults to 'default'

    Returns:
        JSON configuration for setting up a ClickPipe data migration
    """
    logger.info(f"Data migrator starting for database: {database_name}, tables: {schema_tables}")
    try:
        table_mappings = []
        for schema_name, table_names in schema_tables.items():
            for table_name in table_names:
                table_mappings.append({
                    "sourceSchemaName": schema_name,
                    "sourceTable": table_name,
                    "targetTable": table_name
                })

        config = {
            "name": f"{database_name.title()} Migration",
            "source": {
                "postgres": {
                    "host": "${POSTGRES_HOST}",
                    "port": "${POSTGRES_PORT}",
                    "database": database_name,
                    "credentials": {
                        "username": "${POSTGRES_USER}",
                        "password": "${POSTGRES_PASSWORD}"
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

        info_text = """You can create ClickHouse Cloud credentials by following this guide: https://clickhouse.com/docs/cloud/manage/openapi
If you have alternative networking requirements you can refer to this guide: https://clickhouse.com/docs/integrations/clickpipes/aws-privatelink

> ⚠️  This code may have inaccuracies due to it being generated by an LLM. Always check."""

        # Format the JSON config with proper indentation for readability
        config_json = json.dumps(config, indent=2)

        curl_command = (
            "export ORGANIZATION_ID=<REPLACE_ME>\n"
            "export SERVICE_ID=<REPLACE_ME>\n"
            "export POSTGRES_HOST=<REPLACE_ME>\n"
            "export POSTGRES_PORT=<REPLACE_ME>\n"
            "export POSTGRES_USER=<REPLACE_ME>\n"
            "export POSTGRES_PASSWORD=<REPLACE_ME>\n"
            "\n"
            "curl -X POST https://api.clickhouse.cloud/v1/organizations/$ORGANIZATION_ID/services/$SERVICE_ID/clickpipes/ \\\n"
            "  --header 'Authorization: Basic (...)' \\\n"
            "  --header 'Content-Type: application/json' \\\n"
            f"  --data '{config_json}'"
        )

        return json.dumps({
            "info": info_text,
            "command": curl_command
        })

        logger.info(f"Final result: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in data_migrator: {type(e).__name__}: {e}")
        return f"Error creating ClickPipe configuration: {str(e)}"

@tool
def ensure_clickhouse_client(repo_path: str) -> str:
    """
    Ensures that @clickhouse/client package is installed or upgraded to the latest minor version
    in the given repository. Checks for package.json, searches npm for the package, and either
    installs it or upgrades to the latest compatible version.

    Args:
        repo_path: The path to the repository to check and update

    Returns:
        JSON string containing the operation result, current version, and any actions taken
    """
    logger.info(f"Ensure ClickHouse client starting for repository: {repo_path}")
    try:
        result = {
            "success": False,
            "action": None,
            "current_version": None,
            "latest_version": None,
            "message": ""
        }

        # Check if package.json exists
        package_json_path = os.path.join(repo_path, "package.json")
        if not os.path.exists(package_json_path):
            result["message"] = "No package.json found in repository"
            return json.dumps(result)

        # Read package.json
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)

        # Check if @clickhouse/client is already installed
        dependencies = package_data.get("dependencies", {})
        dev_dependencies = package_data.get("devDependencies", {})
        current_version = dependencies.get("@clickhouse/client") or dev_dependencies.get("@clickhouse/client")

        # Get latest version from npm
        try:
            npm_info = subprocess.run(
                ["npm", "view", "@clickhouse/client", "version", "--json"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=30
            )

            if npm_info.returncode != 0:
                result["message"] = f"Failed to fetch package info from npm: {npm_info.stderr}"
                return json.dumps(result)

            latest_version = json.loads(npm_info.stdout.strip())
            result["latest_version"] = latest_version

        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
            result["message"] = f"Error fetching package version: {str(e)}"
            return json.dumps(result)

        if current_version is None:
            # Package not installed, install it
            try:
                # Ensure all output is captured and doesn't leak to console
                install_cmd = subprocess.run(
                    ["npm", "install", f"@clickhouse/client@^{latest_version}"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path,
                    timeout=120,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                if install_cmd.returncode == 0:
                    result["success"] = True
                    result["action"] = "installed"
                    result["current_version"] = f"^{latest_version}"
                    result["message"] = f"Successfully installed @clickhouse/client@^{latest_version}"
                else:
                    result["message"] = f"Failed to install package: {install_cmd.stderr}"

            except subprocess.TimeoutExpired:
                result["message"] = "npm install timed out"
            except Exception as e:
                result["message"] = f"Error during installation: {str(e)}"

        else:
            # Package is installed, check if update is needed
            result["current_version"] = current_version

            # Parse current version (remove ^ or ~ if present)
            if current_version.startswith("^") or current_version.startswith("~"):
                current_clean = current_version[1:]
            else:
                current_clean = current_version

            try:
                if semver.compare(latest_version, current_clean) > 0:
                    # Update available
                    try:
                        update_cmd = subprocess.run(
                            ["npm", "install", f"@clickhouse/client@^{latest_version}"],
                            capture_output=True,
                            text=True,
                            cwd=repo_path,
                            timeout=120
                        )

                        if update_cmd.returncode == 0:
                            result["success"] = True
                            result["action"] = "upgraded"
                            result["message"] = f"Successfully upgraded @clickhouse/client from {current_version} to ^{latest_version}"
                        else:
                            result["message"] = f"Failed to upgrade package: {update_cmd.stderr}"

                    except subprocess.TimeoutExpired:
                        result["message"] = "npm install timed out during upgrade"
                    except Exception as e:
                        result["message"] = f"Error during upgrade: {str(e)}"
                else:
                    # Already up to date
                    result["success"] = True
                    result["action"] = "no_action_needed"
                    result["message"] = f"@clickhouse/client is already up to date at version {current_version}"

            except Exception as e:
                result["message"] = f"Error comparing versions: {str(e)}"

        logger.info(f"Ensure ClickHouse client completed for repository: {repo_path}")
        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error in ensure_clickhouse_client: {type(e).__name__}: {e}")
        error_result = {
            "success": False,
            "action": None,
            "current_version": None,
            "latest_version": None,
            "message": f"Unexpected error: {str(e)}"
        }
        return json.dumps(error_result)

def browse_clickhouse_documentation(section: str = "js-client") -> str:
    """
    Fetch ClickHouse documentation pages to get detailed information.

    Args:
        section: Documentation section to fetch

    Returns:
        Content from the documentation page
    """
    try:
        # Get URL from config
        doc_url = CONFIG["clickhouse_urls"]["documentation"].get(section)
        if not doc_url:
            doc_url = f"{CONFIG['clickhouse_urls']['base_docs']}"

        http_agent = Agent(
            model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
            system_prompt=DOCUMENTATION_ANALYSIS_PROMPT.format(section=section),
            tools=[http_request],
            callback_handler=get_callback_handler()
        )

        result = http_agent(f"Fetch {doc_url} and extract comprehensive documentation content for the {section} section from the HTML")
        return str(result)

    except Exception as e:
        return f"Error fetching documentation: {str(e)}"

@tool
def get_clickhouse_documentation(sections: str = "js-client,getting-started") -> str:
    """
    Get ClickHouse documentation information using http requests.

    Args:
        sections: Comma-separated list of documentation sections to fetch.
                 Available sections are defined in config.yaml under clickhouse_urls.documentation

    Returns:
        Formatted documentation information
    """
    try:
        section_list = [s.strip() for s in sections.split(',') if s.strip()]

        results = []
        for section in section_list:
            doc_result = browse_clickhouse_documentation(section)
            results.append(f"=== {section.upper()} DOCUMENTATION ===\n{doc_result}\n")

        return "\n".join(results)

    except Exception as e:
        return f"Error fetching ClickHouse documentation: {str(e)}"









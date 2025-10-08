import glob as glob_module
import json
import logging
import os
import subprocess
from pathlib import Path

from strands import tool

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
    logger.debug(f"glob called with pattern {pattern} and path {path}")
    try:
        search_path = Path(path).resolve()

        if not search_path.exists():
            return json.dumps({"error": f"Path does not exist: {path}", "files": []})

        # Use glob to find matching files
        matches = []
        full_pattern = str(search_path / pattern)

        for file_path in glob_module.glob(full_pattern, recursive=True):
            if os.path.isfile(file_path):
                matches.append(
                    {"path": file_path, "mtime": os.path.getmtime(file_path)}
                )

        # Sort by modification time (most recent first)
        matches.sort(key=lambda x: x["mtime"], reverse=True)

        # Return just the paths
        file_paths = [m["path"] for m in matches]

        return json.dumps(
            {
                "pattern": pattern,
                "search_path": str(search_path),
                "count": len(file_paths),
                "files": file_paths,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error in glob: {e}")
        return json.dumps({"error": str(e), "files": []})


@tool
def read(file_path: str, offset: int = 0, limit: int = None) -> str:
    """
    Read the contents of a file with optional line range.
    Similar to Claude Code's Read tool for file reading.

    Args:
        file_path: The absolute path to the file to read
        offset: Line number to start reading from (0-indexed, defaults to 0)
        limit: Maximum number of lines to read (defaults to all lines)

    Returns:
        JSON string containing file contents with line numbers (cat -n format)
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return json.dumps(
                {"error": f"File does not exist: {file_path}", "content": ""}
            )

        if not path.is_file():
            return json.dumps(
                {"error": f"Path is not a file: {file_path}", "content": ""}
            )

        # Read file
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Apply offset and limit
        if limit:
            selected_lines = lines[offset : offset + limit]
        else:
            selected_lines = lines[offset:]

        # Format with line numbers (cat -n style)
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=offset + 1):
            formatted_lines.append(f"{i:6d}\t{line.rstrip()}")

        content = "\n".join(formatted_lines)

        return json.dumps(
            {
                "file": str(path),
                "total_lines": len(lines),
                "offset": offset,
                "lines_returned": len(selected_lines),
                "content": content,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error in read: {e}")
        return json.dumps({"error": str(e), "content": ""})


@tool
def write(file_path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        file_path: The path to the file to write
        content: The content to write to the file

    Returns:
        JSON string containing write result
    """
    try:
        path = Path(file_path).resolve()

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return json.dumps(
            {
                "file": str(path),
                "bytes_written": len(content.encode("utf-8")),
                "success": True,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error in write: {e}")
        return json.dumps({"error": str(e), "success": False})


@tool
def bash_run(command: str, working_dir: str = ".") -> str:
    """
    Execute a bash command in the specified directory.

    Args:
        command: The bash command to execute
        working_dir: The directory to run the command in (defaults to current directory)

    Returns:
        JSON string containing command output and exit code
    """
    try:
        work_path = Path(working_dir).resolve()

        if not work_path.exists():
            return json.dumps(
                {
                    "error": f"Working directory does not exist: {working_dir}",
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": "",
                }
            )

        logger.info(f"Running command: {command} in {work_path}")

        result = subprocess.run(
            command,
            shell=True,
            cwd=str(work_path),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        return json.dumps(
            {
                "command": command,
                "working_dir": str(work_path),
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        )

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {command}")
        return json.dumps(
            {
                "error": "Command timed out after 5 minutes",
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
            }
        )
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return json.dumps(
            {"error": str(e), "exit_code": -1, "stdout": "", "stderr": ""}
        )


@tool
def call_human(prompt: str) -> str:
    """
    Request input from the user during agent execution.
    Use this tool when you need clarification, guidance, or approval from the user.

    Args:
        prompt: The question or message to present to the user

    Returns:
        The user's response as a string
    """
    print(f"\n{'='*60}")
    print(f"AGENT REQUEST FOR INPUT:")
    print(f"{prompt}")
    print(f"{'='*60}\n")

    user_input = input("Your response: ")
    return user_input

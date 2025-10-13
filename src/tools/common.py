import glob as glob_module
import json
import logging
import os
import subprocess
from pathlib import Path

from strands import tool

logger = logging.getLogger(__name__)

# Directories to exclude from glob and grep searches
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    "dist",
    "build",
}


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
                # Check if file is in an excluded directory
                path_parts = Path(file_path).relative_to(search_path).parts
                if not any(part in EXCLUDED_DIRS for part in path_parts):
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
    Write content to a file with user approval and rich diff display.

    Args:
        file_path: The path to the file to write
        content: The content to write to the file

    Returns:
        JSON string containing write result
    """
    import difflib

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.syntax import Syntax
    from rich.text import Text

    console = Console()

    try:
        path = Path(file_path).resolve()
        file_exists = path.exists()

        # Force a newline to break out of any active callback displays
        import sys

        sys.stdout.write("\n")
        sys.stdout.flush()

        console.print()

        # Display file operation header
        if file_exists:
            console.print(
                Panel(
                    f"[bold yellow]Modify existing file[/bold yellow]\n{file_path}",
                    border_style="yellow",
                    padding=(0, 2),
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold green]Create new file[/bold green]\n{file_path}",
                    border_style="green",
                    padding=(0, 2),
                )
            )

        console.print()

        if file_exists:
            # Show diff for existing file
            with open(path, "r", encoding="utf-8") as f:
                original_content = f.read()

            # Check if content is actually different
            if original_content == content:
                console.print("[dim]No changes detected - content is identical[/dim]")
                console.print()
                # Still ask for approval but make it clear nothing will change
                approved = Confirm.ask(
                    "[bold cyan]File is unchanged. Continue anyway?[/bold cyan]",
                    default=False,
                )
                if not approved:
                    return json.dumps(
                        {
                            "file": str(path),
                            "success": True,
                            "unchanged": True,
                            "message": "No changes needed",
                        },
                        indent=2,
                    )
            else:
                # Generate unified diff
                diff = list(
                    difflib.unified_diff(
                        original_content.splitlines(keepends=False),
                        content.splitlines(keepends=False),
                        fromfile=f"a/{path.name}",
                        tofile=f"b/{path.name}",
                        lineterm="",
                    )
                )

                if diff:
                    # Display diff with syntax highlighting
                    console.print("[bold]Changes:[/bold]")
                    diff_text = "\n".join(diff)
                    syntax = Syntax(
                        diff_text, "diff", theme="monokai", line_numbers=False
                    )
                    console.print(syntax)
                else:
                    # Shouldn't happen but just in case
                    console.print(
                        "[yellow]Content differs but diff generation failed[/yellow]"
                    )
                    console.print(
                        f"[dim]Old size: {len(original_content)} chars, New size: {len(content)} chars[/dim]"
                    )
        else:
            # Show preview of new file content
            console.print("[bold]New file content:[/bold]")

            # Try to detect file type for syntax highlighting
            extension = path.suffix.lstrip(".")
            if not extension:
                extension = "text"

            # Show preview (first 50 lines or full content if shorter)
            lines = content.splitlines()
            preview_lines = lines[:50]
            preview_content = "\n".join(preview_lines)

            if len(lines) > 50:
                preview_content += f"\n... ({len(lines) - 50} more lines)"

            syntax = Syntax(
                preview_content, extension, theme="monokai", line_numbers=True
            )
            console.print(syntax)

        console.print()

        # Ask for approval
        approved = Confirm.ask(
            "[bold cyan]Approve this file operation?[/bold cyan]", default=True
        )

        if not approved:
            console.print("[yellow]✗ File operation cancelled by user[/yellow]")
            return json.dumps(
                {
                    "file": str(path),
                    "success": False,
                    "cancelled": True,
                    "message": "User cancelled the operation",
                },
                indent=2,
            )

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        console.print(f"[green]✓ Successfully wrote to {file_path}[/green]")
        console.print()

        return json.dumps(
            {
                "file": str(path),
                "bytes_written": len(content.encode("utf-8")),
                "success": True,
                "operation": "update" if file_exists else "create",
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error in write: {e}")
        console.print(f"[red]✗ Error: {str(e)}[/red]")
        return json.dumps({"error": str(e), "success": False})


@tool
def bash_run(command: str, working_dir: str = ".") -> str:
    """
    Execute a bash command in the specified directory with user approval.

    Args:
        command: The bash command to execute
        working_dir: The directory to run the command in (defaults to current directory)

    Returns:
        JSON string containing command output and exit code
    """
    import sys

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.syntax import Syntax

    console = Console()

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

        # Force a newline to break out of any active callback displays
        sys.stdout.write("\n")
        sys.stdout.flush()

        console.print()

        # Display command execution request
        console.print(
            Panel(
                f"[bold cyan]Execute bash command[/bold cyan]\n\n"
                f"[bold]Command:[/bold] [yellow]{command}[/yellow]\n"
                f"[bold]Working directory:[/bold] [dim]{work_path}[/dim]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

        console.print()

        # Ask for approval
        approved = Confirm.ask(
            "[bold cyan]Approve this command execution?[/bold cyan]", default=True
        )

        if not approved:
            console.print("[yellow]✗ Command execution cancelled by user[/yellow]")
            console.print()
            return json.dumps(
                {
                    "command": command,
                    "working_dir": str(work_path),
                    "exit_code": -1,
                    "cancelled": True,
                    "stdout": "",
                    "stderr": "",
                    "message": "User cancelled the operation",
                },
                indent=2,
            )

        console.print(f"[dim]Running: {command}[/dim]")
        logger.info(f"Running command: {command} in {work_path}")

        result = subprocess.run(
            command,
            shell=True,
            cwd=str(work_path),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        # Show result
        if result.returncode == 0:
            console.print(f"[green]✓ Command completed successfully[/green]")
        else:
            console.print(
                f"[yellow]⚠ Command exited with code {result.returncode}[/yellow]"
            )

        console.print()

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
        console.print(f"[red]✗ Command timed out after 5 minutes[/red]")
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
        console.print(f"[red]✗ Error: {str(e)}[/red]")
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
    import sys

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()

    # Force a newline to break out of any active callback displays
    sys.stdout.write("\n")
    sys.stdout.flush()

    # Display the prompt in a styled panel
    console.print()
    console.print(
        Panel(
            prompt,
            title="[bold yellow]🤔 Agent Request for Input[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print()

    # Get user input with rich styling
    user_input = Prompt.ask("[bold cyan]Your response[/bold cyan]")

    return user_input


@tool
def load_example(orm_type: str = "orm_none") -> str:
    """
    Load an example from the corpus based on the ORM type.

    Args:
        orm_type: The ORM type to load examples for. Options:
                  - "orm_none" (default): Plain SQL queries without ORM
                  - "orm_drizzleorm": Drizzle ORM examples
                  - "orm_prisma": Prisma ORM examples (future)

    Returns:
        JSON string containing the corpus content and metadata
    """
    try:
        current_dir = Path(__file__).parent.parent
        corpus_dir = current_dir / "corpus"

        corpus_file = corpus_dir / f"{orm_type}.txt"

        if not corpus_file.exists():
            available_files = list(corpus_dir.glob("*.txt"))
            available_orms = [f.stem for f in available_files]

            return json.dumps(
                {
                    "error": f"Corpus file not found for ORM type: {orm_type}",
                    "available_orm_types": available_orms,
                    "content": "",
                },
                indent=2,
            )

        # Read the corpus file
        with open(corpus_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Calculate some metadata
        file_sections = content.count("<file")
        evaluation_sections = content.count("<EVALUATION>")

        return json.dumps(
            {
                "orm_type": orm_type,
                "corpus_file": str(corpus_file),
                "file_size_bytes": corpus_file.stat().st_size,
                "content_length": len(content),
                "file_sections": file_sections,
                "evaluation_sections": evaluation_sections,
                "content": content,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Error loading corpus example: {e}")
        return json.dumps({"error": str(e), "content": ""})


@tool
def grep(
    pattern: str,
    path: str = ".",
    file_pattern: str = None,
    case_insensitive: bool = False,
    show_line_numbers: bool = False,
    context_lines: int = 0,
    output_mode: str = "files",
) -> str:
    """
    Search for a pattern in files within the specified directory.
    Similar to Claude Code's Grep tool for content searching.

    Args:
        pattern: The regex pattern to search for
        path: The directory to search in (defaults to current directory)
        file_pattern: Optional glob pattern to filter files (e.g., "*.py", "*.js")
        case_insensitive: Whether to perform case-insensitive search
        show_line_numbers: Whether to show line numbers in output (requires output_mode="content")
        context_lines: Number of lines to show before and after matches (requires output_mode="content")
        output_mode: "files" (list files with matches), "content" (show matching lines), or "count" (show match counts)

    Returns:
        JSON string containing search results based on output_mode
    """
    try:
        import re

        search_path = Path(path).resolve()

        if not search_path.exists():
            return json.dumps({"error": f"Path does not exist: {path}", "results": []})

        # Compile regex pattern
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return json.dumps({"error": f"Invalid regex pattern: {e}", "results": []})

        # Find files to search
        if file_pattern:
            files_to_search = []
            for file_path in glob_module.glob(
                str(search_path / file_pattern), recursive=True
            ):
                if os.path.isfile(file_path):
                    files_to_search.append(file_path)
        else:
            # Search all files recursively
            files_to_search = []
            for root, dirs, files in os.walk(search_path):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                for file in files:
                    files_to_search.append(os.path.join(root, file))

        # Filter to only code/SQL files
        allowed_extensions = {".ts", ".tsx", ".js", ".jsx", ".sql"}
        files_to_search = [
            f for f in files_to_search if os.path.splitext(f)[1] in allowed_extensions
        ]

        results = []

        for file_path in files_to_search:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                matches = []
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        matches.append(
                            {"line_number": line_num, "content": line.rstrip("\n")}
                        )

                if matches:
                    result_entry = {"file": file_path, "match_count": len(matches)}

                    if output_mode == "content":
                        if context_lines > 0:
                            # Add context lines
                            enhanced_matches = []
                            for match in matches:
                                line_num = match["line_number"]
                                start = max(1, line_num - context_lines)
                                end = min(len(lines), line_num + context_lines)

                                context = []
                                for i in range(start, end + 1):
                                    context.append(
                                        {
                                            "line_number": (
                                                i if show_line_numbers else None
                                            ),
                                            "content": lines[i - 1].rstrip("\n"),
                                            "is_match": i == line_num,
                                        }
                                    )

                                enhanced_matches.append(
                                    {"match_line": line_num, "context": context}
                                )

                            result_entry["matches"] = enhanced_matches
                        else:
                            result_entry["matches"] = matches

                    results.append(result_entry)

            except (UnicodeDecodeError, PermissionError):
                continue

        if output_mode == "files":
            return json.dumps(
                {
                    "pattern": pattern,
                    "search_path": str(search_path),
                    "files_with_matches": [r["file"] for r in results],
                    "count": len(results),
                },
                indent=2,
            )
        elif output_mode == "count":
            return json.dumps(
                {
                    "pattern": pattern,
                    "search_path": str(search_path),
                    "results": [
                        {"file": r["file"], "matches": r["match_count"]}
                        for r in results
                    ],
                    "total_matches": sum(r["match_count"] for r in results),
                },
                indent=2,
            )
        else:  # content
            return json.dumps(
                {
                    "pattern": pattern,
                    "search_path": str(search_path),
                    "results": results,
                    "total_files": len(results),
                    "total_matches": sum(r["match_count"] for r in results),
                },
                indent=2,
            )

    except Exception as e:
        logger.error(f"Error in grep: {e}")
        return json.dumps({"error": str(e), "results": []})

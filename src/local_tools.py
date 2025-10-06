import json
import logging
import os
import glob as glob_module
import re
from pathlib import Path

from strands import tool

logger = logging.getLogger(__name__)

@tool
def glob(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern in the specified directory.
    Respects .gitignore patterns if a .gitignore file exists.
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

        # Read .gitignore patterns if file exists
        gitignore_patterns = set()
        gitignore_path = search_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            gitignore_patterns.add(line)
            except Exception as e:
                logger.warning(f"Could not read .gitignore: {e}")

        # Helper function to check if a path matches gitignore patterns
        def is_ignored(file_path: str) -> bool:
            rel_path = os.path.relpath(file_path, search_path)
            for pattern in gitignore_patterns:
                # Simple pattern matching (handle basic cases)
                if pattern.endswith('/'):
                    # Directory pattern
                    if rel_path.startswith(pattern.rstrip('/')):
                        return True
                elif '**' in pattern:
                    # Recursive pattern
                    simplified = pattern.replace('**/', '')
                    if simplified in rel_path:
                        return True
                elif pattern.startswith('*.'):
                    # Extension pattern
                    if rel_path.endswith(pattern[1:]):
                        return True
                else:
                    # Exact match or directory match
                    if rel_path == pattern or rel_path.startswith(pattern + '/'):
                        return True
            return False

        # Use glob to find matching files
        matches = []
        full_pattern = str(search_path / pattern)

        for file_path in glob_module.glob(full_pattern, recursive=True):
            if os.path.isfile(file_path):
                # Skip if matches gitignore pattern
                if gitignore_patterns and is_ignored(file_path):
                    continue

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

@tool
def grep(pattern: str, path: str = ".", file_pattern: str = None, case_insensitive: bool = False,
         show_line_numbers: bool = False, context_lines: int = 0, output_mode: str = "files") -> str:
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
        search_path = Path(path).resolve()

        if not search_path.exists():
            return json.dumps({
                "error": f"Path does not exist: {path}",
                "results": []
            })

        # Compile regex pattern
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return json.dumps({
                "error": f"Invalid regex pattern: {e}",
                "results": []
            })

        # Find files to search
        if file_pattern:
            files_to_search = []
            for file_path in glob_module.glob(str(search_path / file_pattern), recursive=True):
                if os.path.isfile(file_path):
                    files_to_search.append(file_path)
        else:
            # Search all files recursively
            files_to_search = []
            for root, dirs, files in os.walk(search_path):
                # Skip common directories
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv'}]
                for file in files:
                    files_to_search.append(os.path.join(root, file))

        results = []

        for file_path in files_to_search:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                matches = []
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        matches.append({
                            "line_number": line_num,
                            "content": line.rstrip('\n')
                        })

                if matches:
                    result_entry = {
                        "file": file_path,
                        "match_count": len(matches)
                    }

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
                                    context.append({
                                        "line_number": i if show_line_numbers else None,
                                        "content": lines[i - 1].rstrip('\n'),
                                        "is_match": i == line_num
                                    })

                                enhanced_matches.append({
                                    "match_line": line_num,
                                    "context": context
                                })

                            result_entry["matches"] = enhanced_matches
                        else:
                            result_entry["matches"] = matches

                    results.append(result_entry)

            except (UnicodeDecodeError, PermissionError):
                # Skip files that can't be read
                continue

        # Format output based on mode
        if output_mode == "files":
            return json.dumps({
                "pattern": pattern,
                "search_path": str(search_path),
                "files_with_matches": [r["file"] for r in results],
                "count": len(results)
            }, indent=2)
        elif output_mode == "count":
            return json.dumps({
                "pattern": pattern,
                "search_path": str(search_path),
                "results": [{"file": r["file"], "matches": r["match_count"]} for r in results],
                "total_matches": sum(r["match_count"] for r in results)
            }, indent=2)
        else:  # content
            return json.dumps({
                "pattern": pattern,
                "search_path": str(search_path),
                "results": results,
                "total_files": len(results),
                "total_matches": sum(r["match_count"] for r in results)
            }, indent=2)

    except Exception as e:
        logger.error(f"Error in grep: {e}")
        return json.dumps({
            "error": str(e),
            "results": []
        })

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
            return json.dumps({
                "error": f"File does not exist: {file_path}",
                "content": ""
            })

        if not path.is_file():
            return json.dumps({
                "error": f"Path is not a file: {file_path}",
                "content": ""
            })

        # Read file
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Apply offset and limit
        if limit:
            selected_lines = lines[offset:offset + limit]
        else:
            selected_lines = lines[offset:]

        # Format with line numbers (cat -n style)
        formatted_lines = []
        for i, line in enumerate(selected_lines, start=offset + 1):
            formatted_lines.append(f"{i:6d}\t{line.rstrip()}")

        content = "\n".join(formatted_lines)

        return json.dumps({
            "file": str(path),
            "total_lines": len(lines),
            "offset": offset,
            "lines_returned": len(selected_lines),
            "content": content
        }, indent=2)

    except Exception as e:
        logger.error(f"Error in read: {e}")
        return json.dumps({
            "error": str(e),
            "content": ""
        })

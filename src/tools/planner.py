import glob as glob_module
import json
import logging
import os
import re
from pathlib import Path

from strands import tool

from .common import glob, read

logger = logging.getLogger(__name__)


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
    print(f"pattern: {pattern}, case_insensitive: {case_insensitive}")
    try:
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
                # Skip common directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d
                    not in {
                        ".git",
                        "node_modules",
                        "__pycache__",
                        ".venv",
                        "venv",
                        ".next",
                        "dist",
                        "build",
                    }
                ]
                for file in files:
                    files_to_search.append(os.path.join(root, file))

        # Filter to only code/SQL files
        allowed_extensions = {".ts", ".tsx", ".js", ".jsx", ".sql"}
        files_to_search = [
            f for f in files_to_search if os.path.splitext(f)[1] in allowed_extensions
        ]

        results = []

        print(f"files_to_search: {files_to_search}")
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

"""Display utilities for formatted console output using rich."""

from typing import Any, Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


def print_header(title: str, subtitle: str = "") -> None:
    """Print a formatted header with rule.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]", align="left")
    if subtitle:
        console.print(f"[dim]{subtitle}[/dim]\n")
    else:
        console.print()


def print_summary_panel(data: Dict[str, Any], title: str = "Summary") -> None:
    """Print a summary panel with key-value pairs.

    Args:
        data: Dictionary of key-value pairs to display
        title: Panel title
    """
    summary_text = Text()
    for i, (key, value) in enumerate(data.items()):
        if i > 0:
            summary_text.append("\n")
        summary_text.append(f"{key}: ", style="bold")

        # Style based on value type
        if isinstance(value, (int, float)):
            summary_text.append(str(value), style="bold cyan")
        elif "time" in key.lower() or "duration" in key.lower():
            summary_text.append(str(value), style="bold green")
        else:
            summary_text.append(str(value), style="cyan")

    console.print(
        Panel(summary_text, title=f"[bold]{title}[/bold]", border_style="green")
    )
    console.print()


def print_list(items: List[str], title: str = "", item_style: str = "cyan") -> None:
    """Print a formatted list with optional title.

    Args:
        items: List of items to display
        title: Optional title for the list
        item_style: Rich style for list items
    """
    if title:
        console.print(f"[bold]{title}[/bold]")
    for item in items:
        console.print(f"  • {item}", style=item_style)
    console.print()


def print_table(
    data: List[Dict[str, Any]],
    columns: Dict[str, Dict[str, Any]],
    title: str = "",
    show_lines: bool = True,
) -> None:
    """Print a formatted table.

    Args:
        data: List of dictionaries containing row data
        columns: Dictionary mapping column keys to column config:
                 {"column_key": {"header": "Header", "style": "cyan", "width": 10}}
        title: Optional table title
        show_lines: Whether to show lines between rows
    """
    table = Table(
        title=f"[bold]{title}[/bold]" if title else None, show_lines=show_lines
    )

    # Add columns
    for col_key, col_config in columns.items():
        table.add_column(
            col_config.get("header", col_key),
            style=col_config.get("style", "white"),
            width=col_config.get("width"),
        )

    # Add rows
    for row_data in data:
        row_values = [str(row_data.get(key, "")) for key in columns.keys()]
        table.add_row(*row_values)

    console.print(table)
    console.print()


def print_code(
    code: str,
    language: str = "json",
    title: str = "",
    theme: str = "monokai",
    line_numbers: bool = False,
) -> None:
    """Print syntax-highlighted code.

    Args:
        code: Code string to display
        language: Programming language for syntax highlighting
        title: Optional title above the code
        theme: Color theme for syntax highlighting
        line_numbers: Whether to show line numbers
    """
    if title:
        console.rule(f"[bold]{title}[/bold]", style="dim")
        console.print()

    syntax = Syntax(code, language, theme=theme, line_numbers=line_numbers)
    console.print(syntax)
    console.print()


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Error message to display
    """
    console.print(f"[red]Error:[/red] {message}")


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Success message to display
    """
    console.print(f"[green]✓[/green] {message}")


def print_info(message: str, label: str = "") -> None:
    """Print an info message.

    Args:
        message: Info message to display
        label: Optional label prefix
    """
    if label:
        console.print(f"[dim]{label}:[/dim] [blue]{message}[/blue]")
    else:
        console.print(f"[blue]{message}[/blue]")

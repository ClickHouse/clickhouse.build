"""Callback handlers for agent tool execution and output streaming."""

import json
from typing import Any, Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text


class PrintingCallbackHandler:
    """Handler for streaming text output and tool invocations to stdout with rich formatting."""

    def __init__(self) -> None:
        """Initialize handler."""
        self.tool_count = 0
        self.previous_tool_use = None
        self.tool_inputs = {}  # Track accumulated tool inputs by toolUseId
        self.displayed_tools = set()  # Track which tools we've already displayed
        self.console = Console()
        self.current_live: Optional[Live] = None
        self.current_tool_id: Optional[str] = None
        self.current_tool_text: Optional[Text] = None  # Store current tool info
        self.current_tool_number: int = 0

    def _complete_current_tool(self) -> None:
        """Complete the current tool animation and show checkmark."""
        if self.current_live and self.current_tool_text:
            # Create completion display with checkmark
            completed_text = Text()
            completed_text.append("✓ ", style="bold green")
            completed_text.append(self.current_tool_text)

            completed_panel = Panel(
                completed_text, border_style="green", padding=(0, 1), expand=False
            )

            # Update the live display to show completed state
            self.current_live.update(completed_panel)

            # Stop the live display (leaves the completed version visible)
            self.current_live.stop()
            self.console.print()

            self.current_live = None
            self.current_tool_id = None
            self.current_tool_text = None

    def __call__(self, **kwargs: Any) -> None:
        """Stream text output and tool invocations to stdout.

        Args:
            **kwargs: Callback event data including:
                - reasoningText (Optional[str]): Reasoning text to print if provided.
                - data (str): Text content to stream.
                - complete (bool): Whether this is the final chunk of a response.
                - current_tool_use (dict): Information about the current tool being used.
                - agent: The agent object executing the tool.
        """
        reasoningText = kwargs.get("reasoningText", False)
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        current_tool_use = kwargs.get("current_tool_use", {})
        agent = kwargs.get("agent")

        # If we're getting text data and have an active tool, complete it first
        if data and self.current_live:
            self._complete_current_tool()

        if reasoningText:
            print(reasoningText, end="")

        if data:
            print(data, end="" if not complete else "\n")

        if current_tool_use and current_tool_use.get("name"):
            tool_use_id = current_tool_use.get("toolUseId")
            tool_name = current_tool_use.get("name", "Unknown tool")
            tool_input = current_tool_use.get("input", "")

            if tool_use_id:
                self.tool_inputs[tool_use_id] = tool_input

                # Try to parse as JSON to see if it's complete
                parsed_input = None
                if isinstance(tool_input, str) and tool_input:
                    try:
                        parsed_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        # Not complete JSON yet, skip for now
                        pass
                elif isinstance(tool_input, dict):
                    parsed_input = tool_input

                if parsed_input and tool_use_id not in self.displayed_tools:
                    # Complete previous tool if any
                    if self.current_live and self.current_tool_id != tool_use_id:
                        self._complete_current_tool()

                    self.displayed_tools.add(tool_use_id)
                    self.tool_count += 1
                    self.current_tool_id = tool_use_id
                    self.current_tool_number = self.tool_count

                    # Check if this tool handles its own display - if so, we'll auto-complete immediately
                    # Tools that show their own prompts: call_human, write, bash_run
                    handles_own_display = tool_name in [
                        "call_human",
                        "write",
                        "bash_run",
                    ]

                    # Get agent name
                    agent_name = "unknown"
                    if agent:
                        # Try to get the agent's name or class name
                        agent_name = (
                            getattr(agent, "name", None) or agent.__class__.__name__
                        )

                    # Build formatted tool call text
                    tool_text = Text()
                    tool_text.append(f"[{agent_name}]", style="dim cyan")
                    tool_text.append(f" Tool #{self.tool_count}: ", style="dim")
                    tool_text.append(f"{tool_name}", style="bold yellow")

                    # Format parameters
                    param_parts = []
                    for key, value in parsed_input.items():
                        if value is not None and value != "" and value is not False:
                            # Truncate long values
                            str_value = str(value)
                            if len(str_value) > 50:
                                str_value = str_value[:47] + "..."
                            param_parts.append(f"{key}={str_value}")

                    if param_parts:
                        params_text = ", ".join(param_parts)
                        tool_text.append(f"({params_text})", style="white")
                    else:
                        tool_text.append("()", style="white")

                    # Store for completion display
                    self.current_tool_text = tool_text.copy()

                    if handles_own_display:
                        # For tools that handle their own display (call_human, write),
                        # show completed immediately to avoid interference
                        completed_text = Text()
                        completed_text.append("✓ ", style="bold green")
                        completed_text.append(tool_text)

                        completed_panel = Panel(
                            completed_text,
                            border_style="green",
                            padding=(0, 1),
                            expand=False,
                        )

                        self.console.print()
                        self.console.print(completed_panel)

                        # Clear state since we're done
                        self.current_live = None
                        self.current_tool_id = None
                        self.current_tool_text = None
                    else:
                        # Create animated display with spinner for other tools
                        spinner = Spinner("dots", text=tool_text, style="bold blue")
                        panel = Panel(
                            spinner, border_style="blue", padding=(0, 1), expand=False
                        )

                        # Start live display
                        self.console.print()
                        self.current_live = Live(
                            panel, console=self.console, refresh_per_second=10
                        )
                        self.current_live.start()

        if complete:
            # Complete any remaining tool
            if self.current_live:
                self._complete_current_tool()
            if data:
                print("\n")

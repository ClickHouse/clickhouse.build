"""
Main Chat UI Application.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from pathlib import Path

from .screens.chat_screen import ChatScreen
from ..logging_config import setup_logging, LogLevel, get_logger


class ChatApp(App):
    """Interactive Chat UI for ClickHouse Migration Assistant."""

    TITLE = "ClickHouse Migration Assistant - Chat Interface"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("f1", "help", "Help", show=True),
    ]

    CSS = """
    Screen {
        background: $surface;
    }
    """

    def __init__(self, repo_path: str = None, **kwargs):
        super().__init__(**kwargs)
        # Default to current directory if no path provided
        self.repo_path = repo_path or str(Path.cwd())
        self.logger = None

    def on_mount(self) -> None:
        """Initialize the chat application."""
        # Set up logging for chat UI
        setup_logging(
            log_dir=Path.cwd() / "logs",
            log_level=LogLevel.INFO,
            console_output=False,  # Disable console output for TUI
            file_output=True,
        )

        self.logger = get_logger("ChatApp")
        self.logger.info("Chat UI application starting up")

        # Push the main chat screen
        self.push_screen(ChatScreen(repo_path=self.repo_path))

    def action_help(self) -> None:
        """Show help information."""
        self.bell()
        # TODO: Implement help screen

    def action_quit(self) -> None:
        """Quit the application."""
        if self.logger:
            self.logger.info("Chat UI application shutting down")
        self.exit()


def run_chat_ui():
    """Entry point for the chat UI."""
    app = ChatApp()
    app.run()
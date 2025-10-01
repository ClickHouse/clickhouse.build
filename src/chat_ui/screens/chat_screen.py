"""
Main Chat Screen with Steps Panel and Chat Interface.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Input, Button
from textual.screen import Screen
from textual.binding import Binding
from textual.message import Message
from pathlib import Path

from ..widgets.chat_widget import ChatWidget
from ..widgets.steps_widget import StepsWidget
from ..widgets.approval_widget import ApprovalWidget
from ..widgets.logs_widget import LogsWidget, LogHandler
from ..approval_integration import register_chat_screen, unregister_chat_screen
from ...logging_config import get_logger
import logging


class ChatScreen(Screen):
    """Main chat interface screen."""

    BINDINGS = [
        Binding("ctrl+l", "clear_chat", "Clear Chat", show=True),
        Binding("ctrl+g", "toggle_logs", "Toggle Logs", show=True),
        Binding("escape", "focus_input", "Focus Input", show=False),
    ]

    CSS = """
    #main-container {
        height: 100%;
        layout: vertical;
    }

    #steps-panel {
        height: 30%;
        border-bottom: solid $primary;
        background: $surface;
        padding: 1;
    }

    #bottom-section {
        height: 70%;
        layout: horizontal;
    }

    #chat-panel {
        width: 50%;
        background: $surface;
    }

    #logs-panel {
        width: 50%;
        border-left: solid $primary;
        background: $surface;
        padding: 1;
    }

    #logs-panel.logs-hidden {
        display: none;
    }

    #chat-panel.logs-hidden {
        width: 100%;
    }

    #chat-input-container {
        height: 3;
        border-top: solid $primary;
        background: $surface;
        padding: 0 1;
    }

    #chat-input {
        width: 1fr;
    }

    #send-button {
        width: 10;
        margin-left: 1;
    }

    .panel-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .logs-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    .logs-display {
        height: 1fr;
        border: solid $primary;
        background: $surface-darken-1;
        padding: 1;
    }

    .logs-status {
        height: 1;
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }

    /* Responsive layout adjustments */
    #logs-panel {
        min-height: 10;
        max-height: 50%;
    }

    #top-section {
        min-height: 20;
    }
    """

    class MessageSent(Message):
        """Message sent when user sends a chat message."""

        def __init__(self, message: str):
            super().__init__()
            self.message = message

    def __init__(self, repo_path: str = None):
        super().__init__()
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self.logger = get_logger(__name__)
        self.orchestrator = None
        self.migration_running = False
        self.logs_visible = True


    def compose(self) -> ComposeResult:
        """Create the chat screen layout."""
        yield Header()

        with Container(id="main-container"):
            # Top panel: Migration steps
            with Vertical(id="steps-panel"):
                yield Static("🚀 Migration Progress", classes="panel-title")
                yield StepsWidget(id="steps-widget")

            # Bottom section: Chat and Logs side by side
            with Horizontal(id="bottom-section"):
                # Left panel: Chat interface
                with Vertical(id="chat-panel"):
                    yield Static("💬 Chat with Assistant", classes="panel-title")
                    yield ChatWidget(id="chat-widget")

                    # Chat input area
                    with Horizontal(id="chat-input-container"):
                        yield Input(
                            placeholder="Type your message or question...",
                            id="chat-input"
                        )
                        yield Button("Send", id="send-button", variant="primary")

                # Right panel: Logs
                with Vertical(id="logs-panel"):
                    yield LogsWidget(id="logs-widget")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the chat screen."""
        self.logger.info(f"Chat screen initialized for repository: {self.repo_path}")

        # Focus the input field
        self.query_one("#chat-input", Input).focus()
        
        # Set up periodic refresh to handle MCP log interference
        self.set_interval(3.0, self._periodic_refresh)

        # Send initial greeting
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        # Check if repository path is valid
        repo_status = "✅" if self.repo_path.exists() and self.repo_path.is_dir() else "❌"

        chat_widget.add_assistant_message(
            "Hello! I'm your ClickHouse Migration Assistant. "
            "I'll help you convert your PostgreSQL queries to ClickHouse.\n\n"
            f"**Current Repository:** {repo_status} `{self.repo_path}`\n\n"
            "**Before we start:**\n"
            "• Type `repo` to check/change your repository path\n"
            "• Type `repo /path/to/your/project` to set a specific path\n\n"
            "**Then you can:**\n"
            "• **migrate** - Start the full migration process\n"
            "• **help** - Get more information about available commands"
        )

        # Initialize the real orchestrator
        self.setup_orchestrator()

        # Set up log handler
        self.setup_log_handler()

        # Register this screen for approval requests
        register_chat_screen(self)

        # Reset any previous "yes to all" setting
        from ..approval_integration import disable_yes_to_all
        disable_yes_to_all()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user submits input."""
        if event.input.id == "chat-input":
            message = event.value.strip()
            if message:
                self.send_message(message)
                event.input.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-button":
            input_widget = self.query_one("#chat-input", Input)
            message = input_widget.value.strip()
            if message:
                self.send_message(message)
                input_widget.value = ""
                input_widget.focus()

    def send_message(self, message: str) -> None:
        """Send a user message and process it."""
        self.logger.info(f"User message: {message}")

        # Add user message to chat
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        chat_widget.add_user_message(message)

        # Process the message
        self.process_user_message(message)

        # Post message for any listeners
        self.post_message(self.MessageSent(message))

    def on_approval_widget_approval_result(self, event: ApprovalWidget.ApprovalResult) -> None:
        """Handle approval results from approval widgets."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        chat_widget.handle_approval_result(event.approval_id, event.approved)



    def process_user_message(self, message: str) -> None:
        """Process user message and generate response."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        steps_widget = self.query_one("#steps-widget", StepsWidget)

        # First check if this is an approval response
        if chat_widget.process_user_input_for_approval(message):
            return  # Approval was handled

        message_lower = message.lower().strip()

        if message_lower in ['migrate', 'migration', 'start']:
            self.start_migration()
        elif message_lower in ['help', '?']:
            self.show_help()
        elif message_lower in ['clear', 'reset']:
            chat_widget.clear_messages()
            chat_widget.add_assistant_message("Chat cleared! How can I help you?")
        elif message_lower in ['status', 'progress']:
            self.show_status()
        elif message_lower.startswith('repo ') or message_lower.startswith('repository '):
            # Extract path from command like "repo /path/to/repo" or "repository /path/to/repo"
            parts = message.split(' ', 1)
            if len(parts) > 1:
                new_path = parts[1].strip()
                self.change_repository_path(new_path)
            else:
                self.show_current_repository()
        elif message_lower in ['repo', 'repository', 'path']:
            self.show_current_repository()
        elif message_lower in ['pwd', 'current', 'where']:
            self.show_current_repository()
        elif message_lower in ['browse', 'ls', 'list']:
            self.browse_directories()
        else:
            # Generic response for now
            chat_widget.add_assistant_message(
                f"I understand you said: \"{message}\"\n\n"
                "I'm still learning to understand all commands. Try:\n"
                "• **migrate** - to start migration\n"
                "• **repo [path]** - set repository path\n"
                "• **help** - for more options"
            )

    def setup_orchestrator(self) -> None:
        """Set up connection to the orchestrator."""
        try:
            # Lazy import to avoid circular dependency
            from ...orchestrator import WorkflowOrchestrator

            # Initialize the real orchestrator
            self.orchestrator = WorkflowOrchestrator(
                mode="interactive",
                app_instance=self
            )

            self.logger.info("Orchestrator initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to setup orchestrator: {e}")
            chat_widget = self.query_one("#chat-widget", ChatWidget)
            chat_widget.add_system_message(f"Error: Failed to initialize orchestrator - {e}")

    def start_migration(self) -> None:
        """Start full migration process."""
        if self.migration_running:
            chat_widget = self.query_one("#chat-widget", ChatWidget)
            chat_widget.add_assistant_message("Migration is already running. Please wait for it to complete.")
            return

        # Validate repository path first
        if not self.validate_repository_before_migration():
            return

        chat_widget = self.query_one("#chat-widget", ChatWidget)
        steps_widget = self.query_one("#steps-widget", StepsWidget)

        chat_widget.add_assistant_message(
            f"Starting full migration process...\n\n"
            f"**Repository:** `{self.repo_path}`\n\n"
            f"I'll guide you through each step and ask for your approval when needed."
        )

        # Update steps
        steps_widget.set_step_status(0, "running", "Installing ClickHouse client...")

        # Start real migration (fallback to simulation if orchestrator not available)
        if self.orchestrator:
            self.run_worker(self.run_real_migration())

    def show_help(self) -> None:
        """Show help information."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        chat_widget.add_assistant_message(
            "📚 **ClickHouse Migration Assistant Help**\n\n"
            "**Available Commands:**\n"
            "• `migrate` - Start full migration process\n"
            "• `repo [path]` - Set or show repository path\n"
            "• `status` - Show current migration status\n"
            "• `clear` - Clear chat history\n"
            "• `help` - Show this help message\n\n"
            "**Repository Commands:**\n"
            "• `repo` - Show current repository path\n"
            "• `repo /path/to/repo` - Change repository path\n"
            "• `browse` - Browse directories for easy selection\n"
            "• `repo ..` - Go to parent directory\n\n"
            "**During Migration:**\n"
            "• I'll show you file diffs directly in chat\n"
            "• Type `y` or `yes` to approve individual changes\n"
            "• Type `n` or `no` to reject individual changes\n"
            "• Type `all` to approve all remaining changes automatically\n"
            "\n"
            "• You'll see before/after diffs with syntax highlighting\n\n"
            "**Keyboard Shortcuts:**\n"
            "• `Ctrl+L` - Clear chat\n"
            "• `Ctrl+G` - Toggle logs panel (show/hide)\n"
            "• `Ctrl+Shift+↑` - Minimize logs panel\n"
            "• `Ctrl+Shift+↓` - Maximize logs panel\n"
            "• `Ctrl+Q` - Quit application\n\n"
            "**Logs Panel:**\n"
            "• View real-time migration logs at bottom\n"
            "• Toggle visibility with Ctrl+G\n"
            "• Filter by log level (c=clear, f=filter)\n"
            "• Minimize when you need more chat space\n\n"
            "What would you like to do?"
        )

    def show_status(self) -> None:
        """Show current migration status."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        steps_widget = self.query_one("#steps-widget", StepsWidget)

        current_step = steps_widget.get_current_step()
        completed_count = sum(1 for i in range(len(steps_widget.steps))
                             if steps_widget.get_step_status(i) == 'completed')

        # Get approval status
        from ..approval_integration import get_pending_requests_count, is_yes_to_all_enabled
        pending_approvals = get_pending_requests_count()
        chat_pending = len(chat_widget.pending_approvals)
        total_pending = pending_approvals + chat_pending
        yes_to_all = is_yes_to_all_enabled()

        chat_widget.add_assistant_message(
            f"**Migration Status**\n\n"
            f"**Repository:** {self.repo_path.name}\n"
            f"**Progress:** {completed_count}/{len(steps_widget.steps)} steps completed\n"
            f"*Current Step:** {current_step + 1}. {steps_widget.steps[current_step]}\n\n"
            f"**Waiting for approval:** {'Yes' if total_pending > 0 else 'No'}\n"
            f"**Pending approvals:** {total_pending}\n"
            f"**Chat approvals:** {chat_pending}\n"
            f"**Tool approvals:** {pending_approvals}\n"
            f"**Auto-approval mode:** {'🚀 Enabled (yes to all)' if yes_to_all else '⏸️ Disabled (manual)'}\n\n"
            "Type `migrate` to continue or `help` for more options."
        )

    def handle_approval_request(self, request_id: str) -> None:
        """Handle approval request from orchestrator."""
        self.logger.info(f"Handling approval request: {request_id}")
        from ..approval_integration import _approval_requests, _approval_lock

        with _approval_lock:
            request = _approval_requests.get(request_id)
            if not request:
                self.logger.warning(f"Approval request {request_id} not found")
                return

        self.logger.info(f"Found approval request for file: {request['file_path']}")

        chat_widget = self.query_one("#chat-widget", ChatWidget)
        steps_widget = self.query_one("#steps-widget", StepsWidget)

        # Update steps to show waiting for approval
        steps_widget.set_step_status(2, "running", "Waiting for your approval...")

        # Display the approval request in chat
        file_path = request['file_path']
        new_content = request['new_content']
        original_content = request['original_content']
        change_type = request['change_type']
        detailed_prompt = request.get('detailed_prompt', '')

        # Create a simple approval message
        if change_type == "create":
            action_desc = f"I need to **create** a new file: `{file_path}`"
        elif change_type == "delete":
            action_desc = f"I need to **delete** the file: `{file_path}`"
        else:
            action_desc = f"I need to **modify** the file: `{file_path}`"

        # Show the file changes
        if original_content and new_content:
            # Show diff for modifications
            chat_widget.add_assistant_message(
                f"📝 **File Change Approval Required**\n\n"
                f"{action_desc}\n\n"
                f"**Changes:**\n"
                f"```diff\n"
                f"--- {file_path} (before)\n"
                f"+++ {file_path} (after)\n"
                f"{self._create_simple_diff(original_content, new_content)}\n"
                f"```\n\n"
                f"{detailed_prompt}\n\n" if detailed_prompt else ""
                f"**Do you approve this change?** Type `y` or `yes` to approve, `n` or `no` to reject. Type `yes all` to approve all subsequent changes"
            )
        elif new_content:
            # Show new file content
            chat_widget.add_assistant_message(
                f"📝 **File Change Approval Required**\n\n"
                f"{action_desc}\n\n"
                f"**New content:**\n"
                f"```\n{new_content[:500]}{'...' if len(new_content) > 500 else ''}\n```\n\n"
                f"{detailed_prompt}\n\n" if detailed_prompt else ""
                f"**Do you approve this change?** Type `y` or `yes` to approve, `n` or `no` to reject.  Type `yes all` to approve all subsequent changes"
            )
        else:
            # Simple approval request
            chat_widget.add_assistant_message(
                f"📝 **File Change Approval Required**\n\n"
                f"{action_desc}\n\n"
                f"{detailed_prompt}\n\n" if detailed_prompt else ""
                f"**Do you approve this change?** Type `y` or `yes` to approve, `n` or `no` to reject.  Type `yes all` to approve all subsequent changes."
            )

        # Store the request ID for response handling
        chat_widget.set_pending_approval(request_id)

    def _create_simple_diff(self, old_content: str, new_content: str) -> str:
        """Create a simple diff display."""
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')

        # Use a simple line-by-line comparison
        diff_lines = []

        # Show first few lines of context
        for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
            if old_line != new_line:
                diff_lines.append(f"- {old_line}")
                diff_lines.append(f"+ {new_line}")
            else:
                diff_lines.append(f"  {old_line}")

            # Limit output to keep it readable
            if len(diff_lines) > 15:
                diff_lines.append("  ... (truncated)")
                break

        # Handle case where files have different lengths
        if len(old_lines) != len(new_lines):
            if len(old_lines) > len(new_lines):
                for i in range(len(new_lines), min(len(old_lines), len(new_lines) + 5)):
                    diff_lines.append(f"- {old_lines[i]}")
            else:
                for i in range(len(old_lines), min(len(new_lines), len(old_lines) + 5)):
                    diff_lines.append(f"+ {new_lines[i]}")

        return '\n'.join(diff_lines)

    def show_next_file_conversion(self) -> None:
        """Show the next file conversion for approval."""
        if not hasattr(self, 'migration_files') or self.current_file_index >= len(self.migration_files):
            # Migration complete
            chat_widget = self.query_one("#chat-widget", ChatWidget)
            steps_widget = self.query_one("#steps-widget", StepsWidget)

            steps_widget.set_step_status(2, "completed", "All queries converted")
            steps_widget.set_step_status(3, "completed", "Files updated")
            steps_widget.set_step_status(4, "completed", "Migration complete")

            chat_widget.add_assistant_message(
                "🎉 **Migration Complete!**\n\n"
                "All PostgreSQL queries have been successfully converted to ClickHouse syntax!"
            )
            return

        # Show current file conversion
        file_info = self.migration_files[self.current_file_index]
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        chat_widget.add_approval_request(
            file_path=file_info["file_path"],
            old_content=file_info["old_content"],
            new_content=file_info["new_content"],
            description=file_info["description"],
            callback=self.handle_file_approval
        )

    def handle_file_approval(self, approval: 'PendingApproval', approved: bool) -> None:
        """Handle file approval and move to next file."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        if approved:
            chat_widget.add_assistant_message(f"✅ Applied changes to {approval.file_path}")
        else:
            chat_widget.add_assistant_message(f"⏭️ Skipped changes to {approval.file_path}")

        # Move to next file
        self.current_file_index += 1

        # Small delay before showing next file
        self.call_later(1, self.show_next_file_conversion)

    async def run_real_migration(self) -> None:
        """Run real migration process using the orchestrator."""
        if not self.orchestrator:
            self.logger.error("Orchestrator not initialized")
            return

        self.migration_running = True
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        steps_widget = self.query_one("#steps-widget", StepsWidget)

        try:
            self.logger.info(f"Starting real migration for repository: {self.repo_path}")

            # Use the orchestrator's event streaming
            async for event in self.orchestrator.run_workflow_with_events(str(self.repo_path)):
                if not event or not isinstance(event, dict):
                    continue

                event_type = event.get("type", "unknown")
                message = event.get("message", "")

                self.logger.debug(f"Migration event: {event_type} - {message}")

                # Get logs widget for event logging
                logs_widget = self.query_one("#logs-widget", LogsWidget)

                # Add debug info to logs widget for troubleshooting
                logs_widget.add_log_entry("DEBUG", f"Received event: {event_type}", "ChatScreen")

                # Map orchestrator events to UI updates
                if event_type == "setup_start":
                    steps_widget.set_step_status(0, "running", "Setting up ClickHouse client...")
                    chat_widget.add_system_message("Setting up migration environment", "progress")
                    logs_widget.add_log_entry("INFO", "Migration setup started", "Orchestrator")

                elif event_type == "agent_start":
                    steps_widget.set_step_status(0, "completed", "ClickHouse client ready")
                    steps_widget.set_step_status(1, "running", "Analyzing repository")
                    chat_widget.add_system_message("Starting migration workflow", "progress")
                    logs_widget.add_log_entry("INFO", "Migration workflow started", "Orchestrator")

                elif event_type == "streaming_start":
                    chat_widget.add_system_message("Connecting to migration agents", "progress")
                    logs_widget.add_log_entry("DEBUG", "Event streaming initialized", "Orchestrator")

                # Handle actual orchestrator events
                elif event_type == "tool_start":
                    tool_name = event.get("tool_name", "unknown")
                    logs_widget.add_log_entry("INFO", f"Starting tool: {tool_name}", "Orchestrator")

                    if tool_name == "ensure_clickhouse_client":
                        steps_widget.set_step_status(0, "running", "Installing ClickHouse client")
                        chat_widget.add_system_message("Installing ClickHouse client", "progress")
                    elif tool_name == "code_reader":
                        steps_widget.set_step_status(0, "completed", "ClickHouse client ready")
                        steps_widget.set_step_status(1, "running", "Analyzing repository")
                        chat_widget.add_system_message("Scanning repository for PostgreSQL queries", "progress")
                    elif tool_name == "code_converter":
                        steps_widget.set_step_status(1, "completed", "Repository scanned")
                        steps_widget.set_step_status(2, "running", "Converting queries")
                        chat_widget.add_system_message("Converting PostgreSQL queries to ClickHouse", "progress")
                    elif tool_name == "code_writer":
                        steps_widget.set_step_status(2, "completed", "Queries converted")
                        steps_widget.set_step_status(3, "running", "Writing updated files")
                        chat_widget.add_system_message("Writing converted files...", "progress")
                    elif tool_name == "data_migrator":
                        steps_widget.set_step_status(3, "completed", "Files updated")
                        steps_widget.set_step_status(4, "running", "Generating ClickPipe config")
                        chat_widget.add_system_message("Generating migration configuration", "progress")

                elif event_type == "text_output":
                    # Show agent text output in chat
                    data = event.get("data", "")
                    if data and len(data.strip()) > 10:  # Only show substantial output
                        chat_widget.add_assistant_message(f"🤖 **Agent Output:**\n\n{data[:500]}...")
                        logs_widget.add_log_entry("DEBUG", f"Agent output: {len(data)} characters", "Agent")

                elif event_type == "tool_stream":
                    tool_name = event.get("tool_name", "unknown")
                    tool_data = event.get("tool_data", "")
                    logs_widget.add_log_entry("DEBUG", f"Tool {tool_name} streaming: {tool_data[:100]}...", tool_name)

                elif event_type == "final_result":
                    steps_widget.set_step_status(4, "completed", "Migration complete")
                    result = event.get("result", "")
                    chat_widget.add_assistant_message(
                        "**Migration Complete!**\n\n"
                        "All PostgreSQL queries have been successfully converted to ClickHouse syntax. "
                        "Check the logs for detailed information about the changes made."
                    )
                    logs_widget.add_log_entry("INFO", "Migration completed successfully", "Orchestrator")

                elif event_type == "execution_complete":
                    chat_widget.add_system_message("Migration execution completed", "success")
                    logs_widget.add_log_entry("INFO", "Execution completed", "Orchestrator")

                elif event_type == "error":
                    chat_widget.add_system_message(f"Error: {message}", "error")
                    logs_widget.add_log_entry("ERROR", f"Migration error: {message}", "Orchestrator")

                elif event_type == "cancelled":
                    chat_widget.add_system_message("Migration cancelled by user", "warning")
                    logs_widget.add_log_entry("WARNING", "Migration cancelled by user", "Orchestrator")
                    break

        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            chat_widget.add_system_message(f"Migration failed: {e}", "error")
            # Mark current step as failed
            current_step = steps_widget.get_current_step()
            steps_widget.set_step_status(current_step, "failed", f"Error: {str(e)}")
        finally:
            self.migration_running = False

    def action_clear_chat(self) -> None:
        """Clear the chat."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)
        chat_widget.clear_messages()
        chat_widget.add_assistant_message("Chat cleared! How can I help you?")

    def action_focus_input(self) -> None:
        """Focus the input field."""
        self.query_one("#chat-input", Input).focus()
    
    def _periodic_refresh(self) -> None:
        """Periodically refresh the screen to handle MCP log interference."""
        try:
            # Only refresh if not actively typing
            input_widget = self.query_one("#chat-input", Input)
            if not input_widget.has_focus or not input_widget.value:
                self.app.refresh()
        except Exception:
            pass  # Ignore refresh errors

    def on_unmount(self) -> None:
        """Clean up when screen is unmounted."""
        # Unregister from approval system
        unregister_chat_screen()
        self.logger.info("Chat screen unmounted and unregistered")

    def on_message(self, message: Message) -> None:
        """Handle custom messages."""
        # Handle approval request messages
        if hasattr(message, 'request_id'):
            self._handle_approval_request_message(message.request_id)

    def _handle_approval_request_message(self, request_id: str):
        """Handle approval request message from tools."""
        from ..approval_integration import _approval_requests, _approval_lock

        with _approval_lock:
            request = _approval_requests.get(request_id)

        if not request:
            return

        try:
            # Get chat widget
            chat_widget = self.query_one("#chat-widget", ChatWidget)

            # Create description for the change
            file_path = request['file_path']
            change_type = request['change_type']
            new_content = request['new_content']
            original_content = request['original_content']

            if change_type == "create":
                description = f"Creating new file: {file_path}"
            elif change_type == "delete":
                description = f"Deleting file: {file_path}"
            else:
                description = f"Modifying file: {file_path}"

            # Add approval request to chat
            approval_id = chat_widget.add_approval_request(
                file_path=file_path,
                old_content=original_content,
                new_content=new_content,
                description=description,
                callback=lambda approval, approved: self._handle_tool_approval_response(request_id, approved)
            )

            self.logger.info(f"Approval request displayed in chat (request: {request_id}, approval: {approval_id})")

        except Exception as e:
            self.logger.error(f"Error showing approval request in chat: {e}")
            # Mark as rejected on error
            self._handle_tool_approval_response(request_id, False)

    def _handle_tool_approval_response(self, request_id: str, approved: bool):
        """Handle approval response for tool requests."""
        from ..approval_integration import _approval_requests, _approval_lock

        with _approval_lock:
            request = _approval_requests.get(request_id)
            if request:
                request['response'] = approved
                request['completed'] = True
                self.logger.info(f"Tool approval response: {request_id} -> {approved}")

    def action_toggle_logs(self) -> None:
        """Toggle the visibility of the logs panel."""
        self.logs_visible = not self.logs_visible
        logs_panel = self.query_one("#logs-panel")
        chat_panel = self.query_one("#chat-panel")

        if self.logs_visible:
            logs_panel.remove_class("logs-hidden")
            chat_panel.remove_class("logs-hidden")
            logs_panel.display = True
        else:
            logs_panel.add_class("logs-hidden")
            chat_panel.add_class("logs-hidden")
            logs_panel.display = False

    def setup_log_handler(self) -> None:
        """Set up the log handler to capture logs in the UI."""
        try:
            logs_widget = self.query_one("#logs-widget", LogsWidget)

            # Create custom log handler
            log_handler = LogHandler(logs_widget)
            log_handler.setLevel(logging.DEBUG)

            # Format logs nicely
            formatter = logging.Formatter('%(message)s')
            log_handler.setFormatter(formatter)

            # Add handler to root logger to capture all logs
            root_logger = logging.getLogger()
            root_logger.addHandler(log_handler)

            # Also add to specific loggers we care about
            migration_loggers = [
                'ChatScreen',
                'WorkflowOrchestrator',
                'ChatWidget',
                'StepsWidget',
                'strands',
                'code_reader',
                'code_converter',
                'code_writer',
                'data_migrator'
            ]

            for logger_name in migration_loggers:
                logger = logging.getLogger(logger_name)
                logger.addHandler(log_handler)

            # Add a welcome message to logs
            logs_widget.add_log_entry("INFO", "Log monitoring started", "ChatScreen")

            self.logger.info("Log handler setup complete")

        except Exception as e:
            self.logger.error(f"Failed to setup log handler: {e}")

    def show_current_repository(self) -> None:
        """Show the current repository path and allow changing it."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        # Check if current path exists and is valid
        path_exists = self.repo_path.exists()
        is_directory = self.repo_path.is_dir() if path_exists else False

        status_icon = "✅" if path_exists and is_directory else "❌"
        status_text = "Valid directory" if path_exists and is_directory else "Invalid or missing directory"

        chat_widget.add_assistant_message(
            f"**Current Repository Path:**\n\n"
            f"{status_icon} `{self.repo_path.absolute()}`\n"
            f"Status: {status_text}\n\n"
            f"**To change repository:**\n"
            f"• Type: `repo /path/to/your/repository`\n"
            f"• Type: `repository /path/to/your/repository`\n\n"
            f"**Examples:**\n"
            f"• `repo ./my-project`\n"
            f"• `repo /Users/username/projects/my-app`\n"
            f"• `repo ../other-project`\n\n"
            f"The path can be absolute or relative to the current directory."
        )

    def change_repository_path(self, new_path: str) -> None:
        """Change the repository path and validate it."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        try:
            # Handle special case of ".." for parent directory
            if new_path.strip() == "..":
                new_repo_path = self.repo_path.parent.resolve()
            else:
                # Convert to Path object and resolve
                new_repo_path = Path(new_path).expanduser().resolve()

            # Validate the path
            if not new_repo_path.exists():
                chat_widget.add_assistant_message(
                    f"❌ **Path Not Found**\n\n"
                    f"The path `{new_repo_path}` does not exist.\n\n"
                    f"Please check the path and try again. You can use:\n"
                    f"• Absolute paths: `/Users/username/projects/my-app`\n"
                    f"• Relative paths: `./my-project` or `../other-project`\n"
                    f"• Home directory: `~/projects/my-app`"
                )
                return

            if not new_repo_path.is_dir():
                chat_widget.add_assistant_message(
                    f"❌ **Not a Directory**\n\n"
                    f"The path `{new_repo_path}` exists but is not a directory.\n\n"
                    f"Please provide a path to a directory containing your code."
                )
                return

            # Update the repository path
            old_path = self.repo_path
            self.repo_path = new_repo_path

            # Reset orchestrator since repo path changed
            self.orchestrator = None

            # Update the steps widget title
            steps_widget = self.query_one("#steps-widget", StepsWidget)
            steps_widget.reset_all_steps()

            chat_widget.add_assistant_message(
                f"**Repository Path Updated**\n\n"
                f"**Previous:** `{old_path}`\n"
                f"**Current:** `{self.repo_path}`\n\n"
                f"The repository path has been successfully updated. You can now:\n"
                f"• **migrate** - Start migration for the new repository"
            )

            # Log the change
            logs_widget = self.query_one("#logs-widget", LogsWidget)
            logs_widget.add_log_entry("INFO", f"Repository path changed to: {self.repo_path}", "ChatScreen")

            # Re-initialize orchestrator with new path
            self.setup_orchestrator()

        except Exception as e:
            chat_widget.add_assistant_message(
                f"❌ **Error Changing Path**\n\n"
                f"Failed to change repository path: {str(e)}\n\n"
                f"Please check the path format and try again."
            )
            self.logger.error(f"Error changing repository path: {e}")

    def validate_repository_before_migration(self) -> bool:
        """Validate repository path before starting migration."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        if not self.repo_path.exists():
            chat_widget.add_assistant_message(
                f"❌ **Repository Not Found**\n\n"
                f"The repository path `{self.repo_path}` does not exist.\n\n"
                f"Please set a valid repository path using:\n"
                f"• `repo /path/to/your/repository`\n\n"
                f"Or type `repo` to see the current path and change it."
            )
            return False

        if not self.repo_path.is_dir():
            chat_widget.add_assistant_message(
                f"❌ **Invalid Repository**\n\n"
                f"The path `{self.repo_path}` is not a directory.\n\n"
                f"Please set a valid directory path using:\n"
                f"• `repo /path/to/your/repository`"
            )
            return False

        return True

    def browse_directories(self) -> None:
        """Show directories in the current path for easy selection."""
        chat_widget = self.query_one("#chat-widget", ChatWidget)

        try:
            current_dir = self.repo_path if self.repo_path.is_dir() else self.repo_path.parent

            # Get directories in current path
            directories = []
            try:
                for item in current_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        directories.append(item)
            except PermissionError:
                chat_widget.add_assistant_message(
                    f"❌ **Permission Denied**\n\n"
                    f"Cannot access directory: `{current_dir}`\n\n"
                    f"Please try a different path or check permissions."
                )
                return

            # Sort directories
            directories.sort(key=lambda x: x.name.lower())

            # Show current directory and parent
            parent_dir = current_dir.parent

            browse_text = f"📂 **Directory Browser**\n\n"
            browse_text += f"**Current:** `{current_dir}`\n\n"

            if parent_dir != current_dir:
                browse_text += f"📁 `..` (Parent: `{parent_dir.name}`)\n"
                browse_text += f"   → Use: `repo {parent_dir}`\n\n"

            if directories:
                browse_text += "**Subdirectories:**\n"
                for i, directory in enumerate(directories[:10]):  # Limit to 10 directories
                    browse_text += f"📁 `{directory.name}`\n"
                    browse_text += f"   → Use: `repo {directory}`\n"

                if len(directories) > 10:
                    browse_text += f"\n... and {len(directories) - 10} more directories\n"
            else:
                browse_text += "No subdirectories found.\n"

            browse_text += f"\n**Commands:**\n"
            browse_text += f"• `repo <directory-name>` - Change to directory\n"
            browse_text += f"• `repo ..` - Go to parent directory\n"
            browse_text += f"• `browse` - Refresh directory listing\n"

            chat_widget.add_assistant_message(browse_text)

        except Exception as e:
            chat_widget.add_assistant_message(
                f"❌ **Error Browsing Directories**\n\n"
                f"Failed to browse directories: {str(e)}\n\n"
                f"Please try setting the path directly with: `repo /path/to/directory`"
            )
            self.logger.error(f"Error browsing directories: {e}")
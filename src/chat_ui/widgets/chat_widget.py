"""
Interactive Chat Widget for conversing with the migration assistant.
"""

from textual.widgets import RichLog
from textual.reactive import reactive
from textual.containers import Vertical
from rich.text import Text
from rich.panel import Panel
from rich.syntax import Syntax
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from .approval_widget import ApprovalWidget, PendingApproval
import uuid


class ChatWidget(RichLog):
    """Widget for displaying chat conversation with the migration assistant."""
    
    # Reactive attributes
    message_count = reactive(0)
    
    def __init__(self, **kwargs):
        # Enable markup and highlighting for rich formatting
        kwargs.setdefault('markup', True)
        kwargs.setdefault('highlight', True)
        super().__init__(**kwargs)
        
        self.messages: List[Dict[str, Any]] = []
        self.pending_approvals: Dict[str, PendingApproval] = {}
        self.waiting_for_approval = False
        
    def add_user_message(self, message: str) -> None:
        """Add a user message to the chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Store message
        self.messages.append({
            'type': 'user',
            'message': message,
            'timestamp': timestamp
        })
        
        # Display with user styling
        user_text = Text()
        user_text.append(f"[{timestamp}] ", style="dim")
        user_text.append("👤 You: ", style="bold blue")
        user_text.append(message, style="white")
        
        self.write(user_text)
        self.write("")  # Empty line for spacing
        self.scroll_end(animate=True)
        
        self.message_count += 1
    
    def add_assistant_message(self, message: str) -> None:
        """Add an assistant message to the chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Store message
        self.messages.append({
            'type': 'assistant',
            'message': message,
            'timestamp': timestamp
        })
        
        # Display with assistant styling
        assistant_text = Text()
        assistant_text.append(f"[{timestamp}] ", style="dim")
        assistant_text.append("🤖 Assistant: ", style="bold green")
        
        self.write(assistant_text)
        
        # Process message content for rich formatting
        self._write_formatted_message(message)
        self.write("")  # Empty line for spacing
        self.scroll_end(animate=True)
        
        self.message_count += 1
    
    def add_system_message(self, message: str, message_type: str = "info") -> None:
        """Add a system message to the chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Store message
        self.messages.append({
            'type': 'system',
            'message': message,
            'timestamp': timestamp,
            'message_type': message_type
        })
        
        # Choose icon and color based on type
        icons = {
            'info': ('ℹ️', 'cyan'),
            'success': ('✅', 'green'),
            'warning': ('⚠️', 'yellow'),
            'error': ('❌', 'red'),
            'progress': ('[PROGRESS]', 'blue')
        }
        
        icon, color = icons.get(message_type, ('ℹ️', 'cyan'))
        
        # Display with system styling
        system_text = Text()
        system_text.append(f"[{timestamp}] ", style="dim")
        system_text.append(f"{icon} System: ", style=f"bold {color}")
        system_text.append(message, style=color)
        
        self.write(system_text)
        self.write("")  # Empty line for spacing
        self.scroll_end(animate=True)
        
        self.message_count += 1
    
    def _write_formatted_message(self, message: str) -> None:
        """Write a message with rich formatting support."""
        lines = message.split('\n')
        
        for line in lines:
            if line.strip().startswith('```'):
                # Handle code blocks
                if line.strip() == '```':
                    continue
                    
                # Extract language from ```lang
                lang = line.strip()[3:].strip() or 'text'
                continue
            elif line.strip().startswith('**') and line.strip().endswith('**'):
                # Bold headers
                self.write(f"[bold white]{line}[/bold white]")
            elif line.strip().startswith('• '):
                # Bullet points
                self.write(f"[cyan]{line}[/cyan]")
            elif line.strip().startswith('- ') or line.strip().startswith('+ '):
                # Diff lines
                if line.strip().startswith('- '):
                    self.write(f"[red]{line}[/red]")
                else:
                    self.write(f"[green]{line}[/green]")
            elif line.strip().startswith('📄 ') or line.strip().startswith('📁 '):
                # File/folder references
                self.write(f"[bold cyan]{line}[/bold cyan]")
            elif '**' in line:
                # Inline bold formatting
                formatted_line = line.replace('**', '[bold]', 1).replace('**', '[/bold]', 1)
                self.write(formatted_line)
            else:
                # Regular line
                self.write(line)
    
    def add_approval_request(
        self, 
        file_path: str, 
        old_content: str, 
        new_content: str,
        description: str = "",
        callback: Optional[Callable] = None
    ) -> str:
        """Add an approval request to the chat."""
        approval_id = str(uuid.uuid4())
        
        # Create pending approval
        pending_approval = PendingApproval(
            approval_id=approval_id,
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            description=description,
            callback=callback
        )
        
        self.pending_approvals[approval_id] = pending_approval
        self.waiting_for_approval = True
        
        # Display the approval request in the chat
        self._display_approval_request(file_path, old_content, new_content, description, approval_id)
        
        return approval_id
    
    def _display_approval_request(self, file_path: str, old_content: str, new_content: str, description: str, approval_id: str) -> None:
        """Display an approval request in the chat."""
        import difflib
        
        # Header
        self.write(f"[bold yellow]📝 File Change Request: {file_path}[/bold yellow]")
        
        if description:
            self.write(f"[dim]{description}[/dim]")
        
        self.write("")  # Spacing
        
        # Generate and display diff
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        ))
        
        if diff_lines:
            # Show first 20 lines of diff
            shown_lines = 0
            max_lines = 20
            
            for line in diff_lines:
                if shown_lines >= max_lines:
                    self.write(f"[dim]... ({len(diff_lines) - shown_lines} more lines)[/dim]")
                    break
                    
                line = line.rstrip()
                if line.startswith('+++'):
                    self.write(f"[bold green]{line}[/bold green]")
                elif line.startswith('---'):
                    self.write(f"[bold red]{line}[/bold red]")
                elif line.startswith('+'):
                    self.write(f"[green]{line}[/green]")
                elif line.startswith('-'):
                    self.write(f"[red]{line}[/red]")
                elif line.startswith('@@'):
                    self.write(f"[bold cyan]{line}[/bold cyan]")
                else:
                    self.write(f"[white]{line}[/white]")
                
                shown_lines += 1
        
        self.write("")  # Spacing
        self.write("[bold cyan]💬 Type 'y' or 'yes' to approve, 'n' or 'no' to reject[/bold cyan]")
        self.write("")  # Spacing
        self.scroll_end(animate=True)
    
    def handle_approval_result(self, approval_id: str, approved: bool) -> None:
        """Handle the result of an approval."""
        if approval_id in self.pending_approvals:
            pending_approval = self.pending_approvals[approval_id]
            pending_approval.resolve(approved)
            
            # Remove from pending
            del self.pending_approvals[approval_id]
            
            # Check if we're still waiting for approvals
            self.waiting_for_approval = len(self.pending_approvals) > 0
            
            # Add result message
            if approved:
                self.add_system_message(f"✅ Applied changes to {pending_approval.file_path}", "success")
            else:
                self.add_system_message(f"⏭️ Skipped changes to {pending_approval.file_path}", "warning")
    
    def process_user_input_for_approval(self, message: str) -> bool:
        """Process user input to see if it's an approval response."""
        if not self.waiting_for_approval and not hasattr(self, 'orchestrator_approval_id'):
            return False
        
        message_lower = message.lower().strip()
        
        # Check for approval responses
        if message_lower in ['y', 'yes', 'approve', 'ok', 'apply']:
            # Handle orchestrator approval first
            if hasattr(self, 'orchestrator_approval_id'):
                self.handle_orchestrator_approval(self.orchestrator_approval_id, True)
                return True
            # Approve the most recent pending approval
            elif self.pending_approvals:
                approval_id = list(self.pending_approvals.keys())[-1]
                self.handle_approval_result(approval_id, True)
                return True
        elif message_lower in ['ya', 'all', 'yes to all', 'yes all', 'approve all', 'yesall']:
            # Enable "yes to all" mode and approve current request
            from ..approval_integration import enable_yes_to_all
            enable_yes_to_all()
            
            self.add_system_message(
                "🚀 **Yes to All Enabled!**\n\n"
                "All future file changes will be automatically approved.",
                "success"
            )
            
            # Approve current request
            if hasattr(self, 'orchestrator_approval_id'):
                self.handle_orchestrator_approval(self.orchestrator_approval_id, True)
                return True
            elif self.pending_approvals:
                approval_id = list(self.pending_approvals.keys())[-1]
                self.handle_approval_result(approval_id, True)
                return True

        elif message_lower in ['n', 'no', 'reject', 'skip', 'cancel']:
            # Handle orchestrator approval first
            if hasattr(self, 'orchestrator_approval_id'):
                self.handle_orchestrator_approval(self.orchestrator_approval_id, False)
                return True
            # Reject the most recent pending approval
            elif self.pending_approvals:
                approval_id = list(self.pending_approvals.keys())[-1]
                self.handle_approval_result(approval_id, False)
                return True
        
        return False
    
    def set_pending_approval(self, request_id: str) -> None:
        """Set a pending orchestrator approval request."""
        self.orchestrator_approval_id = request_id
        self.waiting_for_approval = True
    
    def handle_orchestrator_approval(self, request_id: str, approved: bool) -> None:
        """Handle orchestrator approval response."""
        from ..approval_integration import _approval_requests, _approval_lock
        
        # Send response back to orchestrator
        with _approval_lock:
            request = _approval_requests.get(request_id)
            if request:
                request['response'] = approved
                request['completed'] = True
        
        # Clear pending approval
        if hasattr(self, 'orchestrator_approval_id'):
            delattr(self, 'orchestrator_approval_id')
        self.waiting_for_approval = False
        
        # Show confirmation message
        if approved:
            self.add_system_message("✅ Change approved! Continuing migration...", "success")
        else:
            self.add_system_message("❌ Change rejected. Skipping this file...", "warning")
        
        # Update steps widget to continue migration
        try:
            from textual import get_current_app
            app = get_current_app()
            if hasattr(app, 'screen') and hasattr(app.screen, 'query_one'):
                steps_widget = app.screen.query_one("#steps-widget")
                if hasattr(steps_widget, 'set_step_status'):
                    steps_widget.set_step_status(2, "running", "Processing your response...")
        except:
            pass  # Ignore if we can't update steps widget
    
    def clear_messages(self) -> None:
        """Clear all messages from the chat."""
        self.clear()
        self.messages = []
        self.message_count = 0
    
    def get_message_history(self) -> List[Dict[str, Any]]:
        """Get the complete message history."""
        return self.messages.copy()
    
    async def simulate_analysis(self) -> None:
        """Simulate analysis process with chat updates."""
        import asyncio
        
        await asyncio.sleep(1)
        self.add_system_message("Scanning TypeScript files...", "progress")
        
        await asyncio.sleep(1)
        self.add_system_message("Found PostgreSQL queries in 2 files", "success")
        
        await asyncio.sleep(0.5)
        self.add_assistant_message(
            "🎯 **Analysis Results:**\n\n"
            "I found **4 PostgreSQL queries** that need conversion:\n\n"
            "📄 **app/api/expenses/route.ts**\n"
            "• 1 COUNT(*) query for expense totals\n\n"
            "📄 **app/api/expenses/stats/route.ts**\n"
            "• 3 analytics queries with aggregations\n\n"
            "Ready to start the migration? Type **migrate** to begin!"
        )
    
    def action_clear_chat(self) -> None:
        """Action to clear chat."""
        self.clear_messages()
        self.add_assistant_message("Chat cleared! How can I help you?")
    
    def action_focus_input(self) -> None:
        """Focus the input field."""
        self.screen.query_one("#chat-input", Input).focus()
"""
Chat Container Widget inspired by the Mother example.
Uses VerticalScroll to dynamically mount message widgets.
"""

from textual.containers import VerticalScroll
from textual.widgets import Markdown, Static
from textual.reactive import reactive
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
import uuid


class UserMessage(Markdown):
    """User message widget."""
    
    def __init__(self, content: str, **kwargs):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_content = f"**👤 You [{timestamp}]:** {content}"
        super().__init__(formatted_content, **kwargs)
        self.add_class("user-message")


class AssistantMessage(Markdown):
    """Assistant message widget."""
    
    def __init__(self, content: str, **kwargs):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_content = f"**🤖 Assistant [{timestamp}]:** {content}"
        super().__init__(formatted_content, **kwargs)
        self.add_class("assistant-message")


class SystemMessage(Markdown):
    """System message widget."""
    
    def __init__(self, content: str, message_type: str = "info", **kwargs):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        icons = {
            'info': '[INFO]',
            'success': '[SUCCESS]',
            'warning': '[WARNING]',
            'error': '[ERROR]',
            'progress': '[PROGRESS]'
        }
        
        icon = icons.get(message_type, 'ℹ️')
        formatted_content = f"**{icon} System [{timestamp}]:** {content}"
        super().__init__(formatted_content, **kwargs)
        self.add_class(f"system-message system-{message_type}")


class ApprovalMessage(Static):
    """Approval message widget with interactive buttons."""
    
    def __init__(
        self, 
        file_path: str, 
        old_content: str, 
        new_content: str,
        description: str = "",
        callback: Optional[Callable] = None,
        **kwargs
    ):
        self.file_path = file_path
        self.old_content = old_content
        self.new_content = new_content
        self.description = description
        self.callback = callback
        self.approval_id = str(uuid.uuid4())
        self.is_resolved = False
        
        # Create the approval content
        content = self._create_approval_content()
        super().__init__(content, **kwargs)
        self.add_class("approval-message")
    
    def _create_approval_content(self) -> str:
        """Create the approval message content."""
        import difflib
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Generate diff
        diff_lines = list(difflib.unified_diff(
            self.old_content.splitlines(keepends=True),
            self.new_content.splitlines(keepends=True),
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm=""
        ))
        
        # Format the content
        content = f"📝 **File Change Request [{timestamp}]:** `{self.file_path}`\n\n"
        
        if self.description:
            content += f"*{self.description}*\n\n"
        
        if diff_lines:
            content += "```diff\n"
            # Show first 20 lines
            for i, line in enumerate(diff_lines[:20]):
                content += line.rstrip() + "\n"
            if len(diff_lines) > 20:
                content += f"... ({len(diff_lines) - 20} more lines)\n"
            content += "```\n\n"
        
        content += "**💬 Type 'y' or 'yes' to approve, 'n' or 'no' to reject**"
        
        return content
    
    def resolve(self, approved: bool) -> None:
        """Resolve the approval."""
        if self.is_resolved:
            return
            
        self.is_resolved = True
        
        # Update the display
        if approved:
            result_text = f"\n\n✅ **APPROVED** - Changes will be applied to `{self.file_path}`"
        else:
            result_text = f"\n\n❌ **REJECTED** - Changes will be skipped for `{self.file_path}`"
        
        current_content = str(self.renderable)
        self.update(current_content + result_text)
        
        # Call callback if provided
        if self.callback:
            self.callback(self, approved)


class ChatContainer(VerticalScroll):
    """Chat container using VerticalScroll for dynamic message mounting."""
    
    # Reactive attributes
    message_count = reactive(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages: List[Dict[str, Any]] = []
        self.pending_approvals: Dict[str, ApprovalMessage] = {}
        self.waiting_for_approval = False
        
    def compose(self):
        """Initial compose with welcome message."""
        yield AssistantMessage(
            "👋 Hello! I'm your ClickHouse Migration Assistant. "
            "I'll help you convert your PostgreSQL queries to ClickHouse.\n\n"
            "What would you like to do?"
        )
    
    async def add_user_message(self, content: str) -> UserMessage:
        """Add a user message to the chat."""
        message = UserMessage(content)
        await self.mount(message)
        self.scroll_end(animate=True)
        
        # Store message
        self.messages.append({
            'type': 'user',
            'content': content,
            'timestamp': datetime.now(),
            'widget': message
        })
        
        self.message_count += 1
        return message
    
    async def add_assistant_message(self, content: str) -> AssistantMessage:
        """Add an assistant message to the chat."""
        message = AssistantMessage(content)
        await self.mount(message)
        self.scroll_end(animate=True)
        
        # Store message
        self.messages.append({
            'type': 'assistant',
            'content': content,
            'timestamp': datetime.now(),
            'widget': message
        })
        
        self.message_count += 1
        return message
    
    async def add_system_message(self, content: str, message_type: str = "info") -> SystemMessage:
        """Add a system message to the chat."""
        message = SystemMessage(content, message_type)
        await self.mount(message)
        self.scroll_end(animate=True)
        
        # Store message
        self.messages.append({
            'type': 'system',
            'content': content,
            'message_type': message_type,
            'timestamp': datetime.now(),
            'widget': message
        })
        
        self.message_count += 1
        return message
    
    async def add_approval_request(
        self, 
        file_path: str, 
        old_content: str, 
        new_content: str,
        description: str = "",
        callback: Optional[Callable] = None
    ) -> str:
        """Add an approval request to the chat."""
        approval_message = ApprovalMessage(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            description=description,
            callback=callback
        )
        
        await self.mount(approval_message)
        self.scroll_end(animate=True)
        
        # Store approval
        self.pending_approvals[approval_message.approval_id] = approval_message
        self.waiting_for_approval = True
        
        # Store message
        self.messages.append({
            'type': 'approval',
            'file_path': file_path,
            'timestamp': datetime.now(),
            'widget': approval_message
        })
        
        self.message_count += 1
        return approval_message.approval_id
    
    def process_user_input_for_approval(self, message: str) -> bool:
        """Process user input to see if it's an approval response."""
        if not self.waiting_for_approval or not self.pending_approvals:
            return False
        
        message_lower = message.lower().strip()
        
        # Check for approval responses
        if message_lower in ['y', 'yes', 'approve', 'ok', 'apply']:
            # Approve the most recent pending approval
            approval_id = list(self.pending_approvals.keys())[-1]
            approval_message = self.pending_approvals[approval_id]
            approval_message.resolve(True)
            del self.pending_approvals[approval_id]
            self.waiting_for_approval = len(self.pending_approvals) > 0
            return True
            
        elif message_lower in ['n', 'no', 'reject', 'skip', 'cancel']:
            # Reject the most recent pending approval
            approval_id = list(self.pending_approvals.keys())[-1]
            approval_message = self.pending_approvals[approval_id]
            approval_message.resolve(False)
            del self.pending_approvals[approval_id]
            self.waiting_for_approval = len(self.pending_approvals) > 0
            return True
        
        return False
    
    def clear_messages(self) -> None:
        """Clear all messages from the chat."""
        # Remove all child widgets
        for child in list(self.children):
            child.remove()
        
        # Clear stored data
        self.messages.clear()
        self.pending_approvals.clear()
        self.waiting_for_approval = False
        self.message_count = 0
        
        # Add welcome message back
        self.mount(AssistantMessage("Chat cleared! How can I help you?"))
    
    def get_message_count(self) -> int:
        """Get the number of messages in the chat."""
        return self.message_count
    
    def has_pending_approvals(self) -> bool:
        """Check if there are pending approvals."""
        return len(self.pending_approvals) > 0
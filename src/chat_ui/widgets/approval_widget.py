"""
Approval Widget for handling file diff approvals in chat.
"""

from textual.widgets import Static, Button
from textual.containers import Horizontal, Vertical
from textual.message import Message
from rich.text import Text
from rich.syntax import Syntax
from rich.panel import Panel
from typing import Optional, Callable


class ApprovalWidget(Vertical):
    """Widget for displaying file diffs and handling approvals."""

    class ApprovalResult(Message):
        """Message sent when user makes an approval decision."""

        def __init__(self, approved: bool, file_path: str, approval_id: str):
            super().__init__()
            self.approved = approved
            self.file_path = file_path
            self.approval_id = approval_id

    def __init__(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        approval_id: str,
        description: str = "",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.file_path = file_path
        self.old_content = old_content
        self.new_content = new_content
        self.approval_id = approval_id
        self.description = description
        self.is_resolved = False

    def compose(self):
        """Create the approval widget layout."""
        # File header
        yield Static(
            f"📝 **File Change Request:** `{self.file_path}`",
            classes="approval-header"
        )

        # Description if provided
        if self.description:
            yield Static(self.description, classes="approval-description")

        # Diff display
        yield Static(
            self._create_diff_display(),
            classes="approval-diff"
        )

        # Action buttons (only if not resolved)
        if not self.is_resolved:
            with Horizontal(classes="approval-buttons"):
                yield Button("✅ Approve", id="approve-btn", variant="success")
                yield Button("❌ Reject", id="reject-btn", variant="error")
                yield Button("📋 Show Full Diff", id="details-btn", variant="primary")

    def _create_diff_display(self) -> Text:
        """Create a formatted diff display."""
        import difflib

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            self.old_content.splitlines(keepends=True),
            self.new_content.splitlines(keepends=True),
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm=""
        ))

        text = Text()

        if not diff_lines:
            text.append("No changes detected", style="dim")
            return text

        # Show first 20 lines of diff
        shown_lines = 0
        max_lines = 20

        for line in diff_lines:
            if shown_lines >= max_lines:
                text.append(f"\n... ({len(diff_lines) - shown_lines} more lines)", style="dim")
                break

            line = line.rstrip()
            if line.startswith('+++'):
                text.append(f"{line}\n", style="bold green")
            elif line.startswith('---'):
                text.append(f"{line}\n", style="bold red")
            elif line.startswith('+'):
                text.append(f"{line}\n", style="green")
            elif line.startswith('-'):
                text.append(f"{line}\n", style="red")
            elif line.startswith('@@'):
                text.append(f"{line}\n", style="bold cyan")
            else:
                text.append(f"{line}\n", style="white")

            shown_lines += 1

        return text

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if self.is_resolved:
            return

        if event.button.id == "approve-btn":
            self._resolve_approval(True)
        elif event.button.id == "reject-btn":
            self._resolve_approval(False)
        elif event.button.id == "details-btn":
            self._show_full_diff()

    def _resolve_approval(self, approved: bool) -> None:
        """Resolve the approval and update the UI."""
        self.is_resolved = True

        # Remove buttons
        buttons_container = self.query_one(".approval-buttons")
        buttons_container.remove()

        # Add result message
        if approved:
            result_text = "✅ **Approved** - Changes will be applied"
            result_style = "bold green"
        else:
            result_text = "❌ **Rejected** - Changes will be skipped"
            result_style = "bold red"

        self.mount(Static(result_text, classes="approval-result"))

        # Post the approval result
        self.post_message(self.ApprovalResult(approved, self.file_path, self.approval_id))

    def _show_full_diff(self) -> None:
        """Show the full diff in a separate view."""
        # TODO: Implement full diff view
        # For now, just update the diff display to show more lines
        diff_widget = self.query_one(".approval-diff")
        full_diff = self._create_full_diff_display()
        diff_widget.update(full_diff)

    def _create_full_diff_display(self) -> Text:
        """Create a full diff display without line limits."""
        import difflib

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            self.old_content.splitlines(keepends=True),
            self.new_content.splitlines(keepends=True),
            fromfile=f"a/{self.file_path}",
            tofile=f"b/{self.file_path}",
            lineterm=""
        ))

        text = Text()

        for line in diff_lines:
            line = line.rstrip()
            if line.startswith('+++'):
                text.append(f"{line}\n", style="bold green")
            elif line.startswith('---'):
                text.append(f"{line}\n", style="bold red")
            elif line.startswith('+'):
                text.append(f"{line}\n", style="green")
            elif line.startswith('-'):
                text.append(f"{line}\n", style="red")
            elif line.startswith('@@'):
                text.append(f"{line}\n", style="bold cyan")
            else:
                text.append(f"{line}\n", style="white")

        return text


class PendingApproval:
    """Represents a pending approval request."""

    def __init__(
        self,
        approval_id: str,
        file_path: str,
        old_content: str,
        new_content: str,
        description: str = "",
        callback: Optional[Callable] = None
    ):
        self.approval_id = approval_id
        self.file_path = file_path
        self.old_content = old_content
        self.new_content = new_content
        self.description = description
        self.callback = callback
        self.is_resolved = False
        self.approved = False

    def resolve(self, approved: bool) -> None:
        """Resolve the approval."""
        self.is_resolved = True
        self.approved = approved

        if self.callback:
            self.callback(self, approved)
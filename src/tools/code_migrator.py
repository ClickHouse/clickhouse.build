import logging
import os

from strands import Agent, tool
from strands_tools import file_write

logger = logging.getLogger(__name__)


"""
Integration module for chat UI approval system.
Allows tools to request approval through the chat interface.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Global registry for active chat screens
_active_chat_screen = None
_approval_requests: Dict[str, Dict[str, Any]] = {}
_approval_lock = threading.Lock()
_yes_to_all_enabled = False


def register_chat_screen(chat_screen):
    """Register the active chat screen for approval requests."""
    global _active_chat_screen
    _active_chat_screen = chat_screen
    logger.info("Chat screen registered for approval requests")


def unregister_chat_screen():
    """Unregister the chat screen."""
    global _active_chat_screen
    _active_chat_screen = None
    logger.info("Chat screen unregistered")


def get_chat_approval(
    file_path: str,
    new_content: str,
    original_content: str = "",
    change_type: str = "update",
    detailed_prompt: str = None,
    timeout: int = 300,  # 5 minutes timeout
) -> Optional[bool]:
    """
    Request approval through the chat UI.

    Args:
        file_path: Path of the file being changed
        new_content: New content for the file
        original_content: Original content (for updates)
        change_type: Type of change ("create", "update", "delete")
        detailed_prompt: Optional detailed prompt
        timeout: Timeout in seconds

    Returns:
        True if approved, False if rejected, None if no chat UI available
    """
    global _active_chat_screen, _approval_requests

    logger.info(f"get_chat_approval called for {file_path}")
    logger.info(f"Active chat screen: {_active_chat_screen is not None}")
    logger.info(f"Yes to all enabled: {_yes_to_all_enabled}")

    # If "yes to all" is enabled, automatically approve
    if _yes_to_all_enabled:
        logger.info(f"Auto-approving {file_path} due to 'yes to all' setting")
        try:
            # Still show the change in chat for transparency
            try:
                chat_widget = _active_chat_screen.query_one("#chat-widget")
                # Get the app instance for thread-safe calls
                app = _active_chat_screen.app
                app.call_from_thread(
                    chat_widget.add_system_message,
                    f"✅ Auto-approved: `{file_path}` (yes to all enabled)",
                    "success",
                )
            except Exception:
                pass  # Don't fail if we can't show the message
        except:
            pass  # Don't fail if we can't show the message
        return True

    if not _active_chat_screen:
        logger.debug("No active chat screen for approval")
        return None

    try:
        # Generate unique request ID
        import uuid

        request_id = str(uuid.uuid4())

        # Create approval request
        with _approval_lock:
            _approval_requests[request_id] = {
                "file_path": file_path,
                "new_content": new_content,
                "original_content": original_content,
                "change_type": change_type,
                "detailed_prompt": detailed_prompt,
                "response": None,
                "completed": False,
                "timestamp": time.time(),
            }

        logger.info(f"Requesting chat approval for {file_path} (ID: {request_id})")

        # Send approval request to chat UI using thread-safe method
        logger.info(f"Displaying approval request in chat for {request_id}")
        try:
            # Get the chat widget and display the approval request
            chat_widget = _active_chat_screen.query_one("#chat-widget")

            # Get the request data from the dictionary
            with _approval_lock:
                request_data = _approval_requests[request_id]

            # Create approval message content
            request_file_path = request_data["file_path"]
            request_new_content = request_data["new_content"]
            request_original_content = request_data["original_content"]
            request_change_type = request_data["change_type"]
            request_detailed_prompt = request_data.get("detailed_prompt", "")

            # Create action description
            if request_change_type == "create":
                action_desc = f"I need to **create** a new file: `{request_file_path}`"
            elif request_change_type == "delete":
                action_desc = f"I need to **delete** the file: `{request_file_path}`"
            else:
                action_desc = f"I need to **modify** the file: `{request_file_path}`"

            # Create the approval message
            if request_original_content and request_new_content:
                # Show diff for modifications
                approval_message = (
                    f"📝 **File Change Approval Required**\n\n"
                    f"{action_desc}\n\n"
                    f"**Changes:**\n"
                    f"```diff\n"
                    f"--- {request_file_path} (before)\n"
                    f"+++ {request_file_path} (after)\n"
                    f"{_create_simple_diff(request_original_content, request_new_content)}\n"
                    f"```\n\n"
                    f"{request_detailed_prompt}\n\n"
                    if request_detailed_prompt
                    else ""
                    f"**Do you approve this change?**\n"
                    f"• `y` or `yes` - Approve this change\n"
                    f"• `n` or `no` - Reject this change\n"
                    f"• `all` - Approve this and all future changes"
                )
            else:
                # Simple approval request
                approval_message = (
                    f"📝 **File Change Approval Required**\n\n"
                    f"{action_desc}\n\n"
                    f"{request_detailed_prompt}\n\n"
                    if request_detailed_prompt
                    else ""
                    f"**Do you approve this change?**\n"
                    f"• `y` or `yes` - Approve this change\n"
                    f"• `n` or `no` - Reject this change\n"
                    f"• `all` - Approve this and all future changes"
                )

            # Use thread-safe method to add the message
            app = _active_chat_screen.app
            app.call_from_thread(chat_widget.add_assistant_message, approval_message)

            # Set the pending approval
            app.call_from_thread(chat_widget.set_pending_approval, request_id)

        except Exception as e:
            logger.error(f"Error displaying approval request: {e}")
            import traceback

            traceback.print_exc()

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            with _approval_lock:
                request = _approval_requests.get(request_id)
                if request and request["completed"]:
                    response = request["response"]
                    # Clean up
                    del _approval_requests[request_id]
                    logger.info(f"Chat approval completed for {file_path}: {response}")
                    return response

            time.sleep(0.1)  # Check every 100ms

        # Timeout
        with _approval_lock:
            if request_id in _approval_requests:
                del _approval_requests[request_id]

        logger.warning(f"Chat approval timeout for {file_path}")
        return False  # Default to reject on timeout

    except Exception as e:
        logger.error(f"Error in chat approval for {file_path}: {e}")
        return None


# Approval request handling is now done in ChatScreen via message system


def cleanup_old_requests(max_age: int = 600):
    """Clean up old approval requests (older than max_age seconds)."""
    global _approval_requests

    current_time = time.time()
    with _approval_lock:
        expired_requests = [
            req_id
            for req_id, req in _approval_requests.items()
            if current_time - req["timestamp"] > max_age
        ]

        for req_id in expired_requests:
            del _approval_requests[req_id]
            logger.warning(f"Cleaned up expired approval request: {req_id}")


def get_pending_requests_count() -> int:
    """Get the number of pending approval requests."""
    with _approval_lock:
        return len(_approval_requests)


def _create_simple_diff(old_content: str, new_content: str) -> str:
    """Create a simple diff display."""
    old_lines = old_content.split("\n")
    new_lines = new_content.split("\n")

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

    return "\n".join(diff_lines)


def enable_yes_to_all():
    """Enable 'yes to all' mode - automatically approve all future requests."""
    global _yes_to_all_enabled
    _yes_to_all_enabled = True
    logger.info("Yes to all mode enabled")


def disable_yes_to_all():
    """Disable 'yes to all' mode - return to normal approval process."""
    global _yes_to_all_enabled
    _yes_to_all_enabled = False
    logger.info("Yes to all mode disabled")


def is_yes_to_all_enabled():
    """Check if 'yes to all' mode is currently enabled."""
    return _yes_to_all_enabled


def get_active_chat_screen():
    """Get the currently active chat screen."""
    return _active_chat_screen


def _get_user_approval(
    file_path: str,
    content: str,
    original_content: str = "",
    change_type: str = "update",
    detailed_prompt: str = None,
) -> str:
    """
    Get user approval using TUI InteractiveCLI widget or fallback to user_input.

    Args:
        file_path: Path of the file being changed
        content: New content for the file
        original_content: Original content (for updates)
        change_type: Type of change ("create", "update", "delete")

    Returns:
        User response string ('y' or 'n' or 'all')
    """
    # Check for auto-approve flag (--yes mode)
    import os
    if os.environ.get("CHBUILD_AUTO_APPROVE") == "true":
        logger.info(f"Auto-approving change to {file_path} (--yes flag enabled)")
        return "y"

    try:
        # Try to use Chat UI approval system first
        try:
            approval_result = get_chat_approval(
                file_path=file_path,
                new_content=content,
                original_content=original_content,
                change_type=change_type,
                detailed_prompt=detailed_prompt,
            )

            if approval_result is not None:
                logger.info(
                    f"Using Chat UI for approval of {file_path}: {approval_result}"
                )
                return "y" if approval_result else "n"

        except ImportError:
            # Chat UI not available, try TUI widget
            pass

        # Try to use InteractiveCLI widget for TUI mode
        try:
            # Use a simple synchronous approach with threading
            import threading
            import time

            response_container = {"response": None, "received": False}

            def input_callback(user_input: str):
                response_container["response"] = user_input.strip().lower()
                response_container["received"] = True

            # Request input from the CLI widget
            # request_id = cli_widget.request_input(prompt, input_callback)

            # Wait for response (with timeout)
            timeout = 60  # 60 seconds timeout
            start_time = time.time()

            while (
                not response_container["received"]
                and (time.time() - start_time) < timeout
            ):
                time.sleep(0.1)

            if response_container["received"]:
                response = response_container["response"]
                if response in ["y", "yes"]:
                    logger.info(f"User approved change to {file_path}")
                    return "y"
                else:
                    logger.info(f"User rejected change to {file_path}")
                    return "n"
            else:
                logger.warning(f"Timeout waiting for user input for {file_path}")
                return "n"

        except ImportError:
            # Not in TUI mode, fall through to input()
            pass

        # Fallback to input() for CLI mode or if TUI widget not available
        logger.info(f"Using input() fallback for approval of {file_path}")
        # Use built-in input() instead of strands_tools user_input

        # Create a simple prompt
        prompt = f"""File Change Approval Required

File: {file_path}
Action: {change_type.title()} file
Size: {len(content)} characters

Do you want to proceed with this change?"""

        response = input(f"{prompt}\n\nApprove this change? (y/n): ")
        if response and response.strip().lower() in ["y", "yes"]:
            return "y"
        else:
            return "n"

    except Exception as e:
        logger.error(f"Error getting user approval for {file_path}: {e}")
        # Default to rejection on error
        return "n"


@tool
def file_write_wrapper(path: str, content: str) -> str:
    """
    Write content to a file with user approval.

    Args:
        path: The file path to write to
        content: The content to write to the file

    Returns:
        str: Success message or error details
    """
    try:
        # Get the file operations manager
        agent = Agent(tools=[file_write])

        # Get original content if file exists for diff
        original_content = ""
        file_exists = os.path.exists(path)
        if file_exists:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    original_content = f.read()
            except Exception as e:
                logger.warning(f"Could not read original file {path}: {e}")

        # Create a diff preview
        import difflib

        if file_exists and original_content:
            # Show diff for existing file
            diff_lines = list(
                difflib.unified_diff(
                    original_content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
            )
            diff_preview = "".join(diff_lines)  # First 50 lines
        else:
            # New file - show first part of content
            diff_preview = f"New file: {path}\n\n" + content[:1000]
            if len(content) > 1000:
                diff_preview += f"\n... ({len(content) - 1000} more characters)"

        # Display approval prompt and get user input
        approval_prompt = f"""[APPROVAL] File Write Approval Required

File: {path}
Size: {len(content)} characters
Action: {'Update existing file' if file_exists else 'Create new file'}

Changes to be made:
{diff_preview}

Do you want to proceed with this file write? (y/n/all)"""

        logger.info(f"[APPROVAL] APPROVAL REQUIRED: File write to {path}")
        logger.info(f"� APPPROVAL PROMPT:\n{approval_prompt}")

        # Get user approval
        change_type = "create" if not file_exists else "update"
        user_response = _get_user_approval(
            path, content, original_content, change_type, approval_prompt
        )
        # Check if user approved
        if user_response and user_response.lower() in ["y", "yes"]:
            # User approved - write the file using Strands file_write tool

            result = agent.tool.file_write(path=path, content=content)
            logger.info(f"✅ File write approved and completed: {path}")
            return f"✅ Successfully wrote to {path} (approved by user)"
        else:
            # User rejected or gave unclear response
            logger.info(f"❌ File write rejected by user: {path}")
            return f"❌ File write to {path} cancelled by user"

    except Exception as e:
        error_msg = f"File write failed for {path}: {e}"
        logger.error(error_msg)
        return error_msg

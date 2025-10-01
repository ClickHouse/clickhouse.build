"""
Integration module for chat UI approval system.
Allows tools to request approval through the chat interface.
"""

import threading
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path

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
    timeout: int = 300  # 5 minutes timeout
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
                    "success"
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
                'file_path': file_path,
                'new_content': new_content,
                'original_content': original_content,
                'change_type': change_type,
                'detailed_prompt': detailed_prompt,
                'response': None,
                'completed': False,
                'timestamp': time.time()
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
            request_file_path = request_data['file_path']
            request_new_content = request_data['new_content']
            request_original_content = request_data['original_content']
            request_change_type = request_data['change_type']
            request_detailed_prompt = request_data.get('detailed_prompt', '')

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
                    f"{request_detailed_prompt}\n\n" if request_detailed_prompt else ""
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
                    f"{request_detailed_prompt}\n\n" if request_detailed_prompt else ""
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
                if request and request['completed']:
                    response = request['response']
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
            req_id for req_id, req in _approval_requests.items()
            if current_time - req['timestamp'] > max_age
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
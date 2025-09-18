import os
from strands.handlers.callback_handler import PrintingCallbackHandler


def get_callback_handler():
    """
    Returns the appropriate callback handler based on environment.
    In dev: returns default strands callback handler
    In prod: returns None
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "prod":
        return None
    else:
        return PrintingCallbackHandler()


def get_mcp_log_level():
    """
    Returns the appropriate MCP log level based on environment.
    In dev: returns DEBUG for detailed logging
    In prod: returns ERROR for minimal logging
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "prod":
        return "ERROR"
    else:
        return "DEBUG"
import os
import yaml
from pathlib import Path
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


def load_config():
    """Load configuration from config.yaml file."""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")


# Export configuration object
CONFIG = load_config()
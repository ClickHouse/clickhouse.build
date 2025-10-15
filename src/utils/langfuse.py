"""Langfuse utilities for observability."""

import os

from langfuse import get_client


def get_langfuse_client():
    """Get or create the Langfuse client instance."""
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    if langfuse_enabled:
        return get_client()
    return None

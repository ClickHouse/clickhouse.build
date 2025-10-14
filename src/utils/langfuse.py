"""Langfuse utilities for observability."""

import os

from langfuse import get_client


def get_langfuse_client():
    """Get or create the Langfuse client instance."""
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    if langfuse_enabled:
        return get_client()
    return None


def conditional_observe(name: str):
    """Conditionally apply the @observe decorator based on LANGFUSE_ENABLED."""
    from langfuse import observe

    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
    if langfuse_enabled:
        return observe(name=name)
    else:
        # Return a no-op decorator when langfuse is disabled
        def decorator(func):
            return func

        return decorator

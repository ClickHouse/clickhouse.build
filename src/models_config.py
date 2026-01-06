# Model name to Bedrock model ID mapping
MODEL_MAPPING = {
    "claude-opus-4-5": "us.anthropic.claude-opus-4-5-20251101-v1:0",
    "claude-sonnet-4-5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-sonnet-4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
}

# Default model
DEFAULT_MODEL = "claude-opus-4-5"

# List of available model names for CLI choices
AVAILABLE_MODELS = list(MODEL_MAPPING.keys())


def _normalize_model_name(name: str) -> str:
    """
    Normalize a model name to the model ID format (e.g., "claude-opus-4-5").
    Converts spaces and underscores to hyphens, removes extra whitespace, and converts to lowercase.

    Args:
        name: The model name to normalize (e.g., "Claude Opus 4.5" or "claude_opus_4_5")

    Returns:
        Normalized model name in format "claude-opus-4-5"
    """
    # Convert to lowercase, replace spaces and underscores with hyphens, remove extra whitespace
    normalized = name.lower().strip()
    normalized = normalized.replace(" ", "-").replace(".", "-")
    return normalized


def get_model_id(model_name: str) -> str:
    """
    Get the Bedrock model ID for a given model name.
    Supports multiple naming formats:
    - --model claude-opus-4-5 (model ID format)
    - --model "Claude Opus 4.5" (user-friendly format)

    Args:
        model_name: The model name in any supported format

    Returns:
        The corresponding Bedrock model ID

    Raises:
        ValueError: If the model name is not found
    """
    # First try exact match
    if model_name in MODEL_MAPPING:
        return MODEL_MAPPING[model_name]

    # Try normalized match (converts to model ID format like "claude-opus-4-5")
    normalized_input = _normalize_model_name(model_name)
    if normalized_input in MODEL_MAPPING:
        return MODEL_MAPPING[normalized_input]

    # If no match found, raise error
    available = ", ".join(AVAILABLE_MODELS)
    raise ValueError(f"Unknown model: {model_name}. Available models: {available}")

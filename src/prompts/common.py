import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_agents_md(repo_path: str) -> str:
    """
    Read AGENTS.md file from the repository if it exists.

    Args:
        repo_path: Path to the repository root

    Returns:
        Content of AGENTS.md file, or empty string if not found
    """
    agents_md_content = ""
    agents_md_path = Path(repo_path) / "AGENTS.md"
    if agents_md_path.exists():
        try:
            agents_md_content = agents_md_path.read_text()
            logger.info("Found AGENTS.md in repository")
        except Exception as e:
            logger.warning(f"Failed to read AGENTS.md: {e}")

    return agents_md_content

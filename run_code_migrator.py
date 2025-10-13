#!/usr/bin/env python3
"""
Code migrator script to run the code_migrator agent on a test project.
This script will help migrate application code.
"""

import logging
import os
import sys
from pathlib import Path

import colorlog
from dotenv import load_dotenv

# Load environment variables before importing modules
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.code_migrator import agent_code_migrator
from src.tui.logo import print_logo
from src.utils import check_aws_credentials

# Configure colorful logging
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
        secondary_log_colors={},
        style="%",
    )
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)


def main():
    print_logo()
    logger.info("Checking AWS credentials")
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print(f"Error: {error_message}")
        sys.exit(1)
    print("✓ AWS credentials found and valid\n")

    # Define the repository path
    repo_path = os.path.join(os.path.dirname(__file__), "test", "pg-expense-direct")

    if not os.path.exists(repo_path):
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)

    print(f"Analyzing repository: {repo_path}")
    print("=" * 60)
    print()

    # Run the code migrator
    try:
        agent_code_migrator(repo_path)
    except Exception as e:
        logger.error(f"Error running code migrator: {e}")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

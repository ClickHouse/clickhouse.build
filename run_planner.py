#!/usr/bin/env python3
"""
Planner script to run the code_planner agent on the test/pg-expense-direct project.
This script will analyze the repository and find all PostgreSQL analytical queries.
"""

import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.planner import agent_planner
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    print("Checking AWS credentials...")
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

    try:
        agent_planner(repo_path)
    except Exception as e:
        logger.error(f"Error running code planner: {e}")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

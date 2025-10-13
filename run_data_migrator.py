#!/usr/bin/env python3
"""
Data migrator script to run the data_migrator agent on a repository.
This script will analyze the plan and generate ClickPipe configuration.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables before importing modules
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.data_migrator import run_data_migrator_agent
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
        # Run data migrator with default replication mode
        run_data_migrator_agent(repo_path, replication_mode="cdc")
    except Exception as e:
        logger.error(f"Error running data migrator: {e}")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path
from src.orchestrator import WorkflowOrchestrator

def main():
    parser = argparse.ArgumentParser(
        description="ClickHouse Build: PostgreSQL to ClickHouse Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                        # Analyze current directory
  python main.py --path /path/to/repo   # Analyze specific path
  python main.py --path ./my-project    # Analyze relative path
  python main.py --mode auto            # Run current directory in auto mode
  python main.py --path ./proj --mode auto  # Specific path in auto mode
        """
    )

    parser.add_argument(
        "--path",
        default=".",
        help="Path to the repository to analyze and migrate (default: current directory)"
    )

    parser.add_argument(
        "--mode",
        choices=["conversational", "auto"],
        default="conversational",
        help="Execution mode: conversational (interactive) or auto (automated)"
    )

    args = parser.parse_args()

    # Validate repository path
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Repository path '{args.path}' does not exist")
        sys.exit(1)

    if not repo_path.is_dir():
        print(f"Error: '{args.path}' is not a directory")
        sys.exit(1)

    print("ClickHouse Build: PostgreSQL to ClickHouse Migration Tool")
    print("=" * 60)
    print(f"Repository: {repo_path}")
    print(f"Mode: {args.mode}")
    print()

    try:
        # Create orchestrator
        orchestrator = WorkflowOrchestrator()

        # Run in the specified mode
        if args.mode == "conversational":
            orchestrator.run_conversational(str(repo_path))
        else:
            # Auto mode - run the full workflow automatically
            print("Starting automated migration workflow...")
            result = orchestrator.run_workflow(str(repo_path))
            print("Migration workflow completed!")
            print(result)

    except KeyboardInterrupt:
        print("\nMigration cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
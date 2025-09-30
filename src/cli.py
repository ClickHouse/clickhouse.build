"""
CLI interface for ClickHouse Build tool.
"""

import argparse
import os
import sys
from pathlib import Path
from .orchestrator import WorkflowOrchestrator
from .logging_config import setup_logging, LogLevel


def run_cli():
    """Run the CLI interface."""
    parser = argparse.ArgumentParser(
        description="ClickHouse Build: PostgreSQL to ClickHouse Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --cli                        # CLI mode, analyze current directory
  python main.py --cli --path /path/to/repo   # CLI mode, analyze specific path
  python main.py --cli --path ./my-project    # CLI mode, analyze relative path
  python main.py --cli --mode auto            # CLI mode, current directory in auto mode
  python main.py --cli --path ./proj --mode auto  # CLI mode, specific path in auto mode
        """
    )

    parser.add_argument(
        "--path",
        default=".",
        help="Path to the repository to analyze and migrate (default: current directory)"
    )

    parser.add_argument(
        "--mode",
        choices=["interactive", "auto"],
        default="interactive",
        help="Execution mode: conversational (interactive) or auto (automated)"
    )

    parser.add_argument(
        "--approval-mode",
        choices=["interactive", "automatic"],
        default="interactive",
        help="File approval mode: interactive (prompt for each change) or automatic (auto-approve all changes)"
    )

    args = parser.parse_args()

    # Validate repository path
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"❌ Error: Repository path '{args.path}' does not exist")
        sys.exit(1)

    if not repo_path.is_dir():
        print(f"❌ Error: '{args.path}' is not a directory")
        sys.exit(1)

    print("🚀 ClickHouse Build: PostgreSQL to ClickHouse Migration Tool")
    print("=" * 60)
    print(f"📁 Repository: {repo_path}")
    print(f"🔧 Mode: {args.mode}")
    print(f"📋 Approval Mode: {args.approval_mode}")
    print()

    # Set up centralized logging for CLI mode
    setup_logging(
        log_level=LogLevel.INFO,
        console_output=True,  # Enable console output for CLI
        file_output=True,
    )

    try:
        # Create orchestrator with mode
        orchestrator = WorkflowOrchestrator(mode=args.mode)

        # Run in the specified mode
        if args.mode == "interactive":
            orchestrator.run_conversational(str(repo_path))
        else:
            # Auto mode - run the full workflow automatically
            print("🚀 Starting automated migration workflow...")
            result = orchestrator.run_workflow(str(repo_path))
            print("🎉 Migration workflow completed!")
            print(result)

    except KeyboardInterrupt:
        print("\n👋 Migration cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
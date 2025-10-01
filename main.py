#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from src.orchestrator import WorkflowOrchestrator
from src.utils import check_aws_credentials

def main():
    """Main entry point - choose between TUI and CLI interfaces."""
    parser = argparse.ArgumentParser(
        description="ClickHouse Build: PostgreSQL to ClickHouse Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Interface Options:
  python main.py              # Launch TUI interface (default)
  python main.py --chat       # Launch interactive chat UI
  python main.py --cli        # Use CLI interface

Examples:
  python main.py --chat       # Interactive chat with approval system
  python main.py --cli --path /path/to/repo --mode auto
  python main.py --cli --mode interactive
        """
    )

    # Interface selection
    interface_group = parser.add_mutually_exclusive_group()
    interface_group.add_argument(
        "--cli",
        action="store_true",
        help="Use CLI interface"
    )

    interface_group.add_argument(
        "--chat",
        action="store_true",
        help="Use interactive chat UI interface"
    )

    # Add planning mode argument
    parser.add_argument(
        "--planning-mode",
        action="store_true",
        help="Run in planning mode (analysis only, no file changes)"
    )

    # Parse known args to handle interface selection first
    args, remaining = parser.parse_known_args()
    
    # Check AWS credentials before proceeding
    print("Checking AWS credentials...")
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print(f"Error: {error_message}")
        sys.exit(1)
    print("✓ AWS credentials found and valid")
    print()

    # Determine interface
    if args.cli:
        # Use CLI interface
        from src.cli import run_cli
        # Re-parse with CLI arguments, preserving planning mode
        cli_args = [sys.argv[0]] + remaining
        if args.planning_mode:
            cli_args.append("--planning-mode")
        sys.argv = cli_args
        run_cli()
    else:
        # Use Chat UI interface (default)
        try:
            from src.chat_ui import ChatApp
            app = ChatApp(planning_mode=args.planning_mode)
            app.run()
        except ImportError as e:
            print(f"Error: Chat UI dependencies not available: {e}")
            print("Try installing with: uv sync")
            print("Or use CLI mode: python main.py --cli")
            sys.exit(1)
        except Exception as e:
            print(f"Chat UI Error: {e}")
            print("Or use CLI mode: python main.py --cli")
            sys.exit(1)

if __name__ == "__main__":
    main()
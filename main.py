#!/usr/bin/env python3

import argparse
import sys


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

    # Parse known args to handle interface selection first
    args, remaining = parser.parse_known_args()

    # Determine interface
    if args.cli:
        # Use CLI interface
        from src.cli import run_cli
        # Re-parse with CLI arguments
        sys.argv = [sys.argv[0]] + remaining
        run_cli()
    else:
        # Use Chat UI interface (default)
        try:
            from src.chat_ui import ChatApp
            app = ChatApp()
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
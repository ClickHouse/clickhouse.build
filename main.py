#!/usr/bin/env python3
"""
ClickHouse Build - PostgreSQL to ClickHouse Migration Tool
Main CLI entry point for running various migration agents.
"""

import logging
import os
import sys
from pathlib import Path

import rich_click as click
from dotenv import load_dotenv

# Load environment and configure path early
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

# Now import local modules (after sys.path modification)
from src.logging_config import get_chbuild_logger  # noqa: E402
from src.tui.logo import print_logo  # noqa: E402
from src.utils import check_aws_credentials  # noqa: E402

# Configure rich_click after imports
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "magenta italic"
click.rich_click.ERRORS_SUGGESTION = ""
click.rich_click.ERRORS_EPILOGUE = ""

click.rich_click.COMMAND_GROUPS = {
    "main.py": [
        {
            "name": "Commands",
            "commands": ["scanner", "code-migrator", "data-migrator", "migrate"],
        },
        {
            "name": "Meta",
            "commands": ["eval"],
        },
    ]
}

_, log_file_path = get_chbuild_logger()
logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.version_option(version="1.0.0-prototype", prog_name="clickhouse-build")
@click.pass_context
def main(ctx):
    """An agentic Postgres -> ClickHouse migration tool."""
    # Only print logo if no subcommand is provided
    if ctx.invoked_subcommand is None:
        print_logo()
        click.echo(ctx.get_help())
        click.echo()  # Add extra newline for spacing
    else:
        # Print logo for subcommands
        print_logo()


@main.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    required=True,
)
@click.option(
    "--skip-credentials-check",
    is_flag=True,
    help="Skip AWS credentials validation",
)
def scanner(repo_path: str, skip_credentials_check: bool):
    """
    Run the scanner agent to analyze a repository and find PostgreSQL analytical queries.

    REPO_PATH: Path to the repository to analyze
    """
    if not skip_credentials_check:
        logger.info("Checking AWS credentials...")
        creds_available, error_message = check_aws_credentials()
        if not creds_available:
            click.secho(f"Error: {error_message}", fg="red", err=True)
            sys.exit(1)
        click.secho("✓ AWS credentials loaded\n", fg="green")

    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(repo_path):
        click.secho(
            f"Error: Repository path does not exist: {repo_path}", fg="red", err=True
        )
        sys.exit(1)

    try:
        from src.agents.scanner import agent_scanner

        agent_scanner(repo_path)
        click.secho("\n✓ Scanner completed successfully", fg="green")
    except Exception as e:
        logger.error(f"Error running scanner: {e}")
        click.secho(f"\nError: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    required=True,
)
@click.option(
    "--skip-credentials-check",
    is_flag=True,
    help="Skip AWS credentials validation",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip all confirmation prompts and approve all changes automatically",
)
def code_migrator(repo_path: str, skip_credentials_check: bool, yes: bool):
    """
    Run the code migrator agent to help migrate application code.

    REPO_PATH: Path to the repository to analyze
    """
    if not skip_credentials_check:
        logger.info("Checking AWS credentials...")
        creds_available, error_message = check_aws_credentials()
        if not creds_available:
            click.secho(f"Error: {error_message}", fg="red", err=True)
            sys.exit(1)
        click.secho("✓ AWS credentials loaded\n", fg="green")

    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(repo_path):
        click.secho(
            f"Error: Repository path does not exist: {repo_path}", fg="red", err=True
        )
        sys.exit(1)

    # Set environment variable for auto-approval if --yes flag is set
    if yes:
        os.environ["CHBUILD_AUTO_APPROVE"] = "true"

    try:
        from src.agents.code_migrator import agent_code_migrator

        agent_code_migrator(repo_path)
        click.secho("\n✓ Code migrator completed successfully", fg="green")
    except Exception as e:
        logger.error(f"Error running code migrator: {e}")
        click.secho(f"\nError: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    required=True,
)
@click.option(
    "--replication-mode",
    type=click.Choice(["cdc", "snapshot", "cdc_only"], case_sensitive=False),
    default="cdc",
    help="Replication mode for data migration",
)
@click.option(
    "--skip-credentials-check",
    is_flag=True,
    help="Skip AWS credentials validation",
)
def data_migrator(repo_path: str, replication_mode: str, skip_credentials_check: bool):
    """
    Run the data migrator agent to analyze the plan and generate ClickPipe configuration.

    REPO_PATH: Path to the repository to analyze
    """
    if not skip_credentials_check:
        logger.info("Checking AWS credentials...")
        creds_available, error_message = check_aws_credentials()
        if not creds_available:
            click.secho(f"Error: {error_message}", fg="red", err=True)
            sys.exit(1)
        click.secho("✓ AWS credentials loaded\n", fg="green")

    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(repo_path):
        click.secho(
            f"Error: Repository path does not exist: {repo_path}", fg="red", err=True
        )
        sys.exit(1)

    try:
        from src.agents.data_migrator import run_data_migrator_agent

        run_data_migrator_agent(repo_path, replication_mode=replication_mode)
        click.secho("\n✓ Data migrator completed successfully", fg="green")
    except Exception as e:
        logger.error(f"Error running data migrator: {e}")
        click.secho(f"\nError: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument(
    "repo_path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    required=True,
)
@click.option(
    "--replication-mode",
    type=click.Choice(["cdc", "snapshot", "cdc_only"], case_sensitive=False),
    default="cdc",
    help="Replication mode for data migration",
)
@click.option(
    "--skip-credentials-check",
    is_flag=True,
    help="Skip AWS credentials validation",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip all confirmation prompts and approve all changes automatically",
)
def migrate(
    repo_path: str, replication_mode: str, skip_credentials_check: bool, yes: bool
):
    """
    Run the complete migration workflow: [cyan]scanner[/cyan] [magenta]->[/magenta] [cyan]data_migrator[/cyan] [magenta]->[/magenta] [cyan]code_migrator[/cyan].

    REPO_PATH: Path to the repository to analyze
    """
    if not skip_credentials_check:
        logger.info("Checking AWS credentials...")
        creds_available, error_message = check_aws_credentials()
        if not creds_available:
            click.secho(f"Error: {error_message}", fg="red", err=True)
            sys.exit(1)
        click.secho("✓ AWS credentials loaded\n", fg="green")

    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(repo_path):
        click.secho(
            f"Error: Repository path does not exist: {repo_path}", fg="red", err=True
        )
        sys.exit(1)

    # Set environment variable for auto-approval if --yes flag is set
    if yes:
        os.environ["CHBUILD_AUTO_APPROVE"] = "true"

    try:
        # Step 1: Run scanner
        click.secho("\n[1/3] Scanner agent", fg="cyan", bold=True)
        if yes:
            response = "y"
        else:
            response = click.prompt(
                "Run scanner agent? (y/n)",
                type=click.Choice(["y", "n"]),
                default="y",
                show_choices=False,
            )
        if response == "y":
            from src.agents.scanner import agent_scanner

            agent_scanner(repo_path)
            click.secho("✓ Scanner completed", fg="green")
        else:
            click.secho("Skipping scanner agent", fg="yellow")

        # Step 2: Run data migrator
        click.secho(
            f"\n[2/3] Data migrator agent (mode: {replication_mode})",
            fg="cyan",
            bold=True,
        )
        if yes:
            response = "y"
        else:
            response = click.prompt(
                "Run data migrator agent? (y/n)",
                type=click.Choice(["y", "n"]),
                default="y",
                show_choices=False,
            )
        if response == "y":
            from src.agents.data_migrator import run_data_migrator_agent

            run_data_migrator_agent(repo_path, replication_mode=replication_mode)
            click.secho("✓ Data migrator completed", fg="green")
        else:
            click.secho("Skipping data migrator agent", fg="yellow")

        # Step 3: Run code migrator
        click.secho("\n[3/3] Code migrator agent", fg="cyan", bold=True)
        if yes:
            response = "y"
        else:
            response = click.prompt(
                "Run code migrator agent? (y/n)",
                type=click.Choice(["y", "n"]),
                default="y",
                show_choices=False,
            )
        if response == "y":
            from src.agents.code_migrator import agent_code_migrator

            agent_code_migrator(repo_path)
            click.secho("✓ Code migrator completed", fg="green")
        else:
            click.secho("Skipping code migrator agent", fg="yellow")

        click.secho(
            "\n✓ Migration workflow completed!",
            fg="green",
            bold=True,
        )
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        click.secho(f"\nError: {e}", fg="red", err=True)
        sys.exit(1)


@main.command()
@click.argument(
    "agent",
    type=click.Choice(
        ["scanner", "data-migrator", "qa-code-migrator"], case_sensitive=False
    ),
    required=True,
)
def eval(agent: str):
    """
    Run evaluations for the specified agent.

    AGENT: The agent to evaluate (scanner, data-migrator, or qa-code-migrator)
    """
    click.secho(f"\nRunning {agent} evaluation...\n", fg="cyan", bold=True)

    eval_dir = Path(__file__).parent / "eval" / agent.replace("-", "_")
    eval_script = eval_dir / "eval.py"

    if not eval_script.exists():
        click.secho(
            f"Error: Evaluation script not found: {eval_script}", fg="red", err=True
        )
        sys.exit(1)

    try:
        # Run the eval script
        import subprocess

        result = subprocess.run(
            [sys.executable, str(eval_script)],
            cwd=str(eval_dir),
            capture_output=False,
        )
        sys.exit(result.returncode)
    except Exception as e:
        logger.error(f"Error running evaluation: {e}")
        click.secho(f"\nError: {e}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

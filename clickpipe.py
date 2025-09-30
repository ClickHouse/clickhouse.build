#!/usr/bin/env python3

import click
import sys
import json
import re
import questionary
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from src.tools import data_migrator, ReplicationMode
from src.data_migrator_agent import run_data_migrator_agent

console = Console()

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version='1.0.0')
def cli(ctx):
    """
    🚀 ClickPipe - PostgreSQL to ClickHouse Migration Tool

    A professional CLI for migrating your PostgreSQL databases to ClickHouse.
    """
    if ctx.invoked_subcommand is None:
        show_interactive_menu()

@cli.command(name='plan')
def plan_migration():
    """📋 Run plan migration (Coming Soon)"""
    click.secho("\n📋 Plan Migration", fg='cyan', bold=True)
    click.secho("=" * 60, fg='cyan')
    click.echo("\nThis feature is coming soon!")
    click.echo("It will help you analyze and plan your migration strategy.\n")

@cli.command(name='data')
@click.option('--database', '-d', prompt='Database name', help='Source PostgreSQL database name')
@click.option('--tables', '-t', prompt='Table names (comma-separated)', help='Tables to migrate')
@click.option('--mode', '-m',
              type=click.Choice(['cdc', 'snapshot', 'cdc_only'], case_sensitive=False),
              default='cdc',
              help='Replication mode')
@click.option('--dest', default='default', help='Destination ClickHouse database')
@click.option('--schema', '-s', default='public', help='Source schema name')
def data_migration(database, tables, mode, dest, schema):
    """📊 Run data migration - Generate ClickPipe configuration"""

    click.secho("\n📊 Data Migration Configuration", fg='green', bold=True)
    click.secho("=" * 60, fg='green')

    # Parse table names
    table_list = [t.strip() for t in tables.split(',')]

    # Convert mode to enum
    mode_map = {
        'cdc': ReplicationMode.CDC,
        'snapshot': ReplicationMode.SNAPSHOT,
        'cdc_only': ReplicationMode.CDC_ONLY
    }
    replication_mode = mode_map[mode]

    # Display configuration summary
    click.echo(f"\n  Database: {click.style(database, fg='yellow')}")
    click.echo(f"  Schema: {click.style(schema, fg='yellow')}")
    click.echo(f"  Tables: {click.style(', '.join(table_list), fg='yellow')}")
    click.echo(f"  Mode: {click.style(mode, fg='yellow')}")
    click.echo(f"  Destination: {click.style(dest, fg='yellow')}")

    click.echo("\nGenerating ClickPipe configuration...")

    # Generate configuration
    result = data_migrator(
        database_name=database,
        schema_tables={schema: table_list},
        replication_mode=replication_mode,
        destination_database=dest
    )

    click.secho("\n✅ Configuration Generated:", fg='green', bold=True)
    click.secho("=" * 60, fg='green')
    click.echo()

    # Parse the result JSON
    try:
        result_data = json.loads(result)

        # Display info text
        click.echo(result_data["info"])
        click.echo()

        # Render curl command as markdown code block
        md = Markdown(f"```bash\n{result_data['command']}\n```")
        console.print(md)
    except (json.JSONDecodeError, KeyError):
        # Fallback if format is different
        md = Markdown(f"```bash\n{result}\n```")
        console.print(md)

    click.secho("\n" + "=" * 60 + "\n", fg='green')

@cli.command(name='code')
def code_migration():
    """💻 Run code migration (Coming Soon)"""
    click.secho("\n💻 Code Migration", fg='magenta', bold=True)
    click.secho("=" * 60, fg='magenta')
    click.echo("\nThis feature is coming soon!")
    click.echo("It will help you convert PostgreSQL queries to ClickHouse.\n")

def show_interactive_menu():
    """Show interactive menu when no command is provided"""
    click.clear()
    click.secho("\n🚀 ClickPipe - PostgreSQL to ClickHouse Migration Tool", fg='cyan', bold=True)
    click.secho("=" * 60, fg='cyan')
    click.echo()

    while True:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "📋 Run plan migration (Coming Soon)",
                "📊 Run data migration",
                "💻 Run code migration (Coming Soon)",
                questionary.Separator(),
                "Exit"
            ],
            default="📊 Run data migration"
        ).ask()

        if choice is None or choice == "Exit":
            click.secho("\n👋 Goodbye!\n", fg='cyan')
            sys.exit(0)
        elif choice == "📋 Run plan migration (Coming Soon)":
            click.echo()
            plan_migration()
            questionary.press_any_key_to_continue().ask()
        elif choice == "📊 Run data migration":
            click.echo()

            # Check if code discovery file exists
            discovery_path = Path(".chbuild/CODE_DISCOVERY.md")
            plan_exists = discovery_path.exists()

            # Show sub-menu for data migration approach
            data_choices = []
            if plan_exists:
                data_choices.append("📄 Use migration data plan")
            data_choices.extend([
                "🤖 Read discovery and provide output",
                "🧙 Human-in-the-loop only"
            ])

            data_approach = questionary.select(
                "How would you like to proceed?",
                choices=data_choices
            ).ask()

            if data_approach is None:
                continue

            if data_approach == "📄 Use migration data plan":
                click.secho("\n📄 Using code discovery data", fg='green', bold=True)
                click.secho("=" * 60, fg='green')
                # TODO: Parse and use the code discovery from .chbuild/CODE_DISCOVERY.md
                click.echo("\nReading code discovery from .chbuild/CODE_DISCOVERY.md...")
                click.echo("(Implementation coming soon)")
                questionary.press_any_key_to_continue().ask()

            elif data_approach == "🤖 Read discovery and provide output":
                click.secho("\n🔄 Running data migration from code discovery", fg='green', bold=True)
                click.secho("=" * 60, fg='green')

                # Ask for replication mode
                mode = questionary.select(
                    "Select replication mode:",
                    choices=['cdc', 'snapshot', 'cdc_only'],
                    default='cdc'
                ).ask()

                if mode is None:
                    continue

                click.echo(f"\nAnalyzing code discovery and generating ClickPipe configuration...")
                click.echo(f"Replication mode: {mode}")
                click.echo()

                # STUB: Use test/pg-expense-direct as repo path
                repo_path = "test/pg-expense-direct"
                click.secho(f"[STUB] Using test project: {repo_path}", fg='yellow')
                click.echo()

                # Run the data migrator agent
                result = run_data_migrator_agent(repo_path, replication_mode=mode)

                click.secho("\n✅ Configuration Generated:", fg='green', bold=True)
                click.secho("=" * 60, fg='green')
                click.echo()

                # Parse the result JSON
                try:
                    # Try to extract JSON from the result (agent might wrap it in text)
                    json_match = re.search(r'\{.*\}', result, re.DOTALL)
                    if json_match:
                        result_data = json.loads(json_match.group(0))
                    else:
                        result_data = json.loads(result)

                    # Check if we have the new format with assumptions
                    if "assumptions" in result_data and "config" in result_data:
                        # Display assumptions if any
                        if result_data["assumptions"]:
                            click.secho("📝 Assumptions made:", fg='yellow', bold=True)
                            for assumption in result_data["assumptions"]:
                                click.echo(f"  • {assumption}")
                            click.echo()

                        # Parse the config
                        config_data = json.loads(result_data["config"]) if isinstance(result_data["config"], str) else result_data["config"]

                        # Display info text
                        click.echo(config_data["info"])
                        click.echo()

                        # Render curl command as markdown code block
                        md = Markdown(f"```bash\n{config_data['command']}\n```")
                        console.print(md)
                    else:
                        # Old format - backward compatibility
                        click.echo(result_data["info"])
                        click.echo()

                        md = Markdown(f"```bash\n{result_data['command']}\n```")
                        console.print(md)
                except (json.JSONDecodeError, KeyError):
                    # Fallback if format is different
                    md = Markdown(f"```bash\n{result}\n```")
                    console.print(md)

                click.secho("\n" + "=" * 60 + "\n", fg='green')

                questionary.press_any_key_to_continue().ask()

            elif data_approach == "🧙 Human-in-the-loop only":
                click.echo()

                # Get database name first
                database = questionary.text("Database name:").ask()
                if not database:
                    click.secho("Database name is required!", fg='red')
                    continue

                # Get replication mode
                mode = questionary.select(
                    "Replication mode:",
                    choices=['cdc', 'snapshot', 'cdc_only'],
                    default='cdc'
                ).ask()

                # Get destination database
                dest = questionary.text("Destination database:", default=database).ask()

                # Collect schemas and tables
                all_tables = []
                schema_tables_map = {}

                click.echo()
                click.secho("Add schemas and tables (leave schema empty to finish)", fg='cyan')

                is_first_schema = True
                while True:
                    # Only default to 'public' for the first schema
                    default_schema = "public" if is_first_schema else ""
                    schema = questionary.text("Schema name (or press Enter to finish):", default=default_schema).ask()

                    if not schema or schema.strip() == "":
                        if not all_tables:
                            click.secho("You must add at least one table!", fg='red')
                            continue
                        break

                    tables = questionary.text(f"Table names for schema '{schema}' (comma-separated):").ask()
                    if not tables or tables.strip() == "":
                        click.secho("No tables provided for this schema, skipping...", fg='yellow')
                        continue

                    table_list = [t.strip() for t in tables.split(',')]
                    all_tables.extend(table_list)
                    schema_tables_map[schema] = table_list

                    click.secho(f"✓ Added {len(table_list)} table(s) from schema '{schema}'", fg='green')
                    is_first_schema = False

                # Convert mode to enum
                mode_map = {
                    'cdc': ReplicationMode.CDC,
                    'snapshot': ReplicationMode.SNAPSHOT,
                    'cdc_only': ReplicationMode.CDC_ONLY
                }
                replication_mode = mode_map[mode]

                # Display configuration summary
                click.secho("\n📊 Data Migration Configuration", fg='green', bold=True)
                click.secho("=" * 60, fg='green')
                click.echo(f"\n  Database: {click.style(database, fg='yellow')}")
                click.echo(f"  Schemas and Tables:", nl=False)
                for schema, tables in schema_tables_map.items():
                    click.echo(f"\n    {click.style(schema, fg='cyan')}: {click.style(', '.join(tables), fg='yellow')}")
                click.echo(f"  Mode: {click.style(mode, fg='yellow')}")
                click.echo(f"  Destination: {click.style(dest, fg='yellow')}")

                click.echo("\nGenerating ClickPipe configuration...")

                # Generate configuration
                result = data_migrator(
                    database_name=database,
                    schema_tables=schema_tables_map,
                    replication_mode=replication_mode,
                    destination_database=dest
                )

                click.secho("\n✅ Configuration Generated:", fg='green', bold=True)
                click.secho("=" * 60, fg='green')
                click.echo()

                # Parse the result JSON
                try:
                    result_data = json.loads(result)

                    # Display info text
                    click.echo(result_data["info"])
                    click.echo()

                    # Render curl command as markdown code block
                    md = Markdown(f"```bash\n{result_data['command']}\n```")
                    console.print(md)
                except (json.JSONDecodeError, KeyError):
                    # Fallback if format is different
                    md = Markdown(f"```bash\n{result}\n```")
                    console.print(md)

                click.secho("\n" + "=" * 60 + "\n", fg='green')

                questionary.press_any_key_to_continue().ask()
        elif choice == "💻 Run code migration (Coming Soon)":
            click.echo()
            code_migration()
            questionary.press_any_key_to_continue().ask()

def main():
    cli()

if __name__ == "__main__":
    main()

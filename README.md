# ClickHouse Build

Agentic PostgreSQL to ClickHouse migration tool.

## What Does It Do?

`clickhouse.build` automates the complex process of migrating from PostgreSQL to ClickHouse:

1. **Scans** your codebase to discover PostgreSQL analytical queries (aggregations, GROUP BY, window functions, etc.)
2. **Generates** ClickPipe configuration for CDC or snapshot-based data replication
3. **Migrates** application code by installing ClickHouse client libraries and implementing strategy patterns for query routing
4. **Supports** multiple ORMs: Prisma, Drizzle, and raw SQL

The tool uses specialized AI agents that understand your code structure, database schema, and ORM patterns to generate production-ready migration code.

## Prerequisites

Before using `clickhouse.build`, ensure you have:

- **Python 3.13+** (uses latest Python features)
- **uv** package manager ([installation guide](https://github.com/astral-sh/uv))
- **AWS credentials** with access to Amazon Bedrock
- **Claude Sonnet 4.5** enabled in your AWS Bedrock account
- A **Git repository** with PostgreSQL-based application code
- **Working branch** for migration changes

## Installation

1. Clone the repository:

```bash
git clone https://github.com/ClickHouse/clickhouse.build.git
cd clickhouse.build
```

2. Set up AWS credentials:

```bash
cp .env.template .env
# Edit .env with your AWS credentials
```

Required environment variables:
- `AWS_ACCESS_KEY_ID` - Your AWS access key
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
- `AWS_DEFAULT_REGION` - AWS region (e.g., us-east-1)
- `LANGFUSE_SECRET_KEY` - (Optional) For observability
- `LANGFUSE_PUBLIC_KEY` - (Optional) For observability
- `LANGFUSE_HOST` - (Optional) Langfuse host URL

3. Install dependencies:

```bash
uv sync
```

## Preparation

Before running the migration:

1. **Work on a branch** - Never run migrations directly on main
2. **Create AGENTS.md** - Add an [AGENTS.md](https://agents.md/) file to your repository to help `chbuild` improve its efficacy when understanding your codebase

### AGENTS.md Example

Create an `AGENTS.md` file in your repository root to provide context about your application:

```markdown
# Agent Context

## Architecture
This is a Node.js expense tracking application using PostgreSQL.

## Database
- ORM: Prisma
- Database: PostgreSQL 14
- Key tables: users, expenses, categories, budgets

## Analytical Queries
We use PostgreSQL for both OLTP and OLAP workloads. The main analytical queries are:
- Monthly expense aggregations by category
- Budget tracking with rolling windows
- User spending analytics

## Migration Goals
- Move analytical queries to ClickHouse for better performance
- Keep transactional operations in PostgreSQL
- Maintain backward compatibility during transition
```

## Running

Display help and available commands:

```bash
uv run main.py --help
```

### Quick Start: Full Migration

Run the complete migration workflow (recommended for first-time users):

```bash
uv run main.py migrate /path/to/your/repo --replication-mode cdc
```

This will:
1. Scan for analytical queries
2. Generate ClickPipe configuration
3. Migrate application code
4. Prompt for approval before making any changes

### Individual Commands

**Scanner Agent** - Analyze a repository and find PostgreSQL analytical queries:

```bash
uv run main.py scanner [REPO_PATH]
```

Output: `.chbuild/scanner/scan_TIMESTAMP.json` with discovered queries

**Data Migrator Agent** - Generate ClickPipe configuration for data migration:

```bash
uv run main.py data-migrator [REPO_PATH] [--replication-mode cdc|snapshot|hybrid]
```

Output: curl command with ClickPipe JSON configuration

**Code Migrator Agent** - Migrate application code:

```bash
uv run main.py code-migrator [REPO_PATH]
```

Output: Modified application files with ClickHouse integration

**Migrate** - Run the complete migration workflow (scanner → data-migrator → code-migrator):

```bash
uv run main.py migrate [REPO_PATH] [--replication-mode cdc|snapshot|hybrid]
```

### Options

- `--skip-credentials-check` - Skip AWS credentials validation
- `--yes` / `-y` - Skip all confirmation prompts and approve all changes automatically (useful for CI/CD)
- `--replication-mode` - Set replication mode for data migration:
  - `cdc` - Change Data Capture for real-time sync
  - `snapshot` - One-time snapshot replication
  - `hybrid` - Snapshot followed by CDC

### Meta Commands

**Eval** - Run evaluations for agents:

```bash
uv run main.py eval scanner
uv run main.py eval data-migrator
```

Evaluations compare agent output against ground truth test cases.

## How It Works

### Architecture

`clickhouse.build` uses a multi-agent architecture where specialized AI agents collaborate:

1. **Scanner Agent** - Uses regex patterns and code analysis to discover analytical queries
2. **Data Migrator Agent** - Generates ClickPipe configurations with proper table mappings
3. **Code Migrator Agent** - Transforms application code using extended thinking (10,000 reasoning tokens)
4. **QA Agent** - Validates code quality before writes

All agents use Claude Sonnet 4.5 via AWS Bedrock and have access to tools:
- `grep` - Content search with regex
- `glob` - File pattern matching
- `read` - File reading with line numbers
- `write` - File writing with diff display and approval
- `bash_run` - Command execution with approval
- `call_human` - Request user input

### Safety Features

- **User approval required** for all file writes
- **Diff display** before making changes
- **Approval workflow** for bash commands
- **QA validation** before code generation
- **Git branch requirement** prevents accidental main branch changes

## Supported ORMs

- Prisma (TypeScript/JavaScript)
- Drizzle ORM (TypeScript)
- Raw SQL queries

## Limitations

This is an **experimental prototype** (v0.1.0). Please be aware:

- **AI-generated code requires human review** - Always review migrations before deployment
- **No automated testing** - Test your migrated code thoroughly
- **PostgreSQL focus** - Only PostgreSQL to ClickHouse migrations supported
- **Node.js primary target** - Best tested with Node.js applications
- **Requires manual ClickPipe setup** - Data migration configuration must be applied manually
- **No rollback mechanism** - Use Git to revert changes if needed

## Example Workflow

### Interactive Mode (Default)

```bash
# 1. Create a migration branch
git checkout -b migrate-to-clickhouse

# 2. Run the migration (interactive - prompts for approval)
uv run main.py migrate ./my-app --replication-mode cdc

# 3. Review changes
git diff

# 4. Test the application
cd my-app
npm test

# 5. If satisfied, commit
git add .
git commit -m "Migrate analytical queries to ClickHouse"
```

### CI/CD Mode (Automated)

```bash
# Run migration with --yes flag to skip all prompts
uv run main.py migrate ./my-app --replication-mode cdc --yes

# This will automatically:
# - Run all migration steps without confirmation
# - Approve all file changes
# - Approve all bash commands
```

## Observability

Optional Langfuse integration provides:
- Agent execution traces
- Tool usage analytics
- Performance metrics
- Debugging information

Configure via `.env` file.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[License TBD - Add before release]

## Support

- **Issues**: [GitHub Issues](https://github.com/ClickHouse/clickhouse.build/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ClickHouse/clickhouse.build/discussions)
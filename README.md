# clickhouse.build

[![DeepWiki](https://img.shields.io/badge/DeepWiki-ClickHouse%2Fclickhouse.build-blue.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/ClickHouse/clickhouse.build)



Agentic PostgreSQL to ClickHouse migration tool for TypeScript projects.

This prototype was co-developed between AWS and ClickHouse. Read more in our [blog post](https://clickhouse.com/blog/clickhouse-build-agentic-cli-accelerate-postgres-clickhouse-apps).

<img src="./.github/static/chbuild.png" alt="clickhouse.build cli tool">

## How Can You Try It?

clickhouse.build is a free, client-side CLI. You can install the CLI from this repo and try it out with your project.

If you don't already have a ClickHouse environment, you can [sign up for a free ClickHouse Cloud trial](https://console.clickhouse.cloud/signUp?utm_source=github&utm_medium=github&utm_referrer=clickhouse_build&ref=clickhouse_build) with $300 in credits.

## What Does It Do?

`clickhouse.build` assists with the  process of migrating from PostgreSQL to ClickHouse:

1. **Scans** your codebase to discover PostgreSQL analytical queries (aggregations, GROUP BY, window functions, etc.)
2. **Generates** ClickPipe configuration for CDC or snapshot-based data replication
3. **Migrates** application code by installing ClickHouse client and implementing patterns for query routing

The tool uses specialized AI agents that understand your code structure, database schema, and ORM patterns to generate production-ready migration code.

## Prerequisites

Before using `clickhouse.build`, ensure you have:

- **Python 3.13+** (uses latest Python features)
- **uv** package manager ([installation guide](https://github.com/astral-sh/uv))
- **AWS credentials** with access to Amazon Bedrock
- **Claude Sonnet 4.5** enabled in your AWS Bedrock account

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

3. Install dependencies:

```bash
uv sync
```

## Preparation

Before running the migration:

1. **Work on a branch** - Never run migrations directly on main
2. **Create AGENTS.md** - Add an [AGENTS.md](https://agents.md/) file to your repository to help `chbuild` improve its efficacy when understanding your codebase
3. Consider running `clickhouse.build` in a VM or container for additional safety precautions

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
uv run main.py data-migrator [REPO_PATH] [--replication-mode cdc|snapshot|cdc_only]
```

Output: curl command with ClickPipe JSON configuration

**Code Migrator Agent** - Migrate application code:

```bash
uv run main.py code-migrator [REPO_PATH]
```

Output: Modified application files with ClickHouse integration

**Migrate** - Run the complete migration workflow (scanner → data-migrator → code-migrator):

```bash
uv run main.py migrate [REPO_PATH] [--replication-mode cdc|snapshot|cdc_only]
```

### Options

- `--skip-credentials-check` - Skip AWS credentials validation
- `--yes` / `-y` - Skip all confirmation prompts and approve all changes automatically (useful for CI/CD)
- `--replication-mode` - Set replication mode for data migration:
  - `cdc` - Change Data Capture with initial snapshot + real-time sync
  - `snapshot` - One-time snapshot replication only
  - `cdc_only` - CDC without initial snapshot

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

We welcome feedback on the direction of this project as we continue to evolve it.

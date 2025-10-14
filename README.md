# ClickHouse Build

Agentic PostgreSQL to ClickHouse migration tool.

## Preparation

  - Ensure you are working on a branch
  - Get AWS keys
  - Add an [AGENTS.md](https://agents.md/) file to your repo to help `chbuild` improve its efficacywh

## Running

Display help and available commands:

```bash
uv run main.py
```

### Commands

**Scanner Agent** - Analyze a repository and find PostgreSQL analytical queries:

```bash
uv run main.py scanner [REPO_PATH]
```

**Data Migrator Agent** - Generate ClickPipe configuration for data migration:

```bash
uv run main.py data-migrator [REPO_PATH] [--replication-mode cdc|snapshot|hybrid]
```

**Code Migrator Agent** - Migrate application code:

```bash
uv run main.py code-migrator [REPO_PATH]
```

**Migrate** - Run the complete migration workflow (scanner → data-migrator → code-migrator):

```bash
uv run main.py migrate [REPO_PATH] [--replication-mode cdc|snapshot|hybrid]
```

### Options

- `--skip-credentials-check` - Skip AWS credentials validation
- `--replication-mode` - Set replication mode for data migration (cdc, snapshot, or hybrid)

### Meta Commands

**Eval** - Run evaluations for agents:

```bash
uv run main.py eval scanner
uv run main.py eval data-migrator
```

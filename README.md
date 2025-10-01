# ClickHouse Build

PostgreSQL to ClickHouse migration tool using AI agents with interleaved thinking.

## Architecture

Uses **agents as tools** pattern with Claude 4's interleaved thinking:
- **Specialist agents** (`code_reader`, `code_converter`, `code_writer`) as individual tools
- **Orchestrator agent** coordinates workflow with reasoning between tool calls
- **Interleaved thinking** enables dynamic strategy adaptation during execution

## Setup

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/installation/) if not already installed:

   **macOS/Linux:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   If your system doesn't have curl, you can use wget:

   ```bash
   wget -qO- https://astral.sh/uv/install.sh | sh
   ```

   **Windows:**
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Install dependencies:
```bash
uv sync
```

3. Ensure AWS credentials profile is enabled in your environment for accessing required services.

## Usage

### Interactive Mode (Default)
Run the migration workflow interactively:
```bash
# Analyze current directory (default)
uv run main.py

# Analyze specific repository
uv run main.py --path /path/to/your/repository
```

### Automated Mode
Run the full workflow automatically:
```bash
# Current directory in auto mode
uv run main.py --mode auto

# Specific repository in auto mode
uv run main.py --path /path/to/your/repository --mode auto
```

### Examples
```bash
# Analyze current directory (most common)
uv run main.py

# Analyze a specific project
uv run main.py --path ./my-postgres-project

# Analyze with absolute path
uv run main.py --path /Users/username/projects/my-app

# Run current directory in automated mode
uv run main.py --mode auto

# Run specific project in automated mode
uv run main.py --path ./my-project --mode auto
```

The tool will:
1. **Read** - Find all PostgreSQL analytics queries in the repository
2. **Convert** - Transform them to ClickHouse equivalents  
3. **Write** - Replace the original queries with converted ones

## CLI Options

- `--path`: Path to the repository to analyze (default: current directory)
- `--mode`: Execution mode
  - `interactive` (default): Interactive mode with back-and-forth
  - `auto`: Automated workflow execution

## Configuration

### URLs and Settings
Copy the template and customize URLs without rebuilding:
```bash
cp config.template.yaml config.yaml
# Edit config.yaml to customize URLs, timeouts, etc.
```

The `config.yaml` file contains:
- **ClickHouse URLs** - NPM package, GitHub releases, documentation sections
- **Research sources** - Official docs, GitHub repos, Stack Overflow, blog
- **Settings** - HTTP timeouts, user agent, retry logic

### Model Settings
- Modify models in `src/tools.py` and `src/orchestrator.py`
- Environment variables: Set AWS profile and region as needed
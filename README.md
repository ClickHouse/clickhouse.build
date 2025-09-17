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

3. Edit repository path in `main.py`:
```python
repo_path = "/path/to/your/repository"  # Change this line
```

4. Ensure AWS credentials profile is enabled in your environment for accessing required services.

## Usage

Run the migration workflow:
```bash
uv run main.py
```

The tool will:
1. **Read** - Find all PostgreSQL analytics queries in the repository
2. **Convert** - Transform them to ClickHouse equivalents  
3. **Write** - Replace the original queries with converted ones

## Configuration

- Repository path: Edit `repo_path` variable in `main.py`
- Model settings: Modify models in `src/tools.py` and `src/orchestrator.py`
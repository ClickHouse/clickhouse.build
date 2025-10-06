# Contributing

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

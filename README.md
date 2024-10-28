# Assistant

> ![IMPORTANT] Why both `assistant` and `app`?
>
> `app` is the actual app where im inlining everything until it proves its worth, `assistant` is the library that contains the core functionality.

A service that monitors and summarizes information from various sources.

## Prerequisites

- Docker
- Gmail API credentials
- `uv` package manager (for local development)

## Environment Variables

Required environment variables in `.env`:

```env
# API Keys
OPENAI_API_KEY=your_openai_key
PREFECT_API_KEY=your_prefect_key
PREFECT_API_URL=your_prefect_workspace_url
HUMANLAYER_API_KEY=your_humanlayer_key

# Service Configuration
ASSISTANT_PORT=8000
EMAIL_CHECK_INTERVAL_SECONDS=10
OBSERVATION_CHECK_INTERVAL_SECONDS=10
```

## Quick Start

```bash
# Setup environment and run service
make

# Development with hot reload
make dev

# Clean up Docker resources
make clean
```

## Development Setup

1. Install `uv`:

   ```bash
   pip install -U uv
   ```

2. Virtual environment:

   ```bash
   uv venv --python 3.12
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   UV_SYSTEM_PYTHON=1 uv pip install --editable ".[gmail]"
   ```

4. Place Gmail credentials relative to the `app_dir`:

   - `gmail_credentials.json`
   - `gmail_token.json`

   For example, I have them in `app/secrets/gmail_credentials.json` and `app/secrets/gmail_token.json`.

5. Run the service:

   ```bash
   make dev
   ```

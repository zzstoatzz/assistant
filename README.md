# Information Observer Service

A service that monitors and summarizes information from various sources.

## Prerequisites

- Docker
- Gmail API credentials
- UV package manager (for local development)

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

1. Install UV:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies:

   ```bash
   UV_SYSTEM_PYTHON=1 uv pip install --editable ".[dev]"
   ```

3. Place Gmail credentials in `email_credentials/`:
   - `gmail_credentials.json`
   - `gmail_token.json`

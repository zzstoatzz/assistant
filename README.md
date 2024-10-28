# Assistant

> [!NOTE]
>
> `app` is the working app (wip), `assistant` is the core library (more-solidified but still wip).

Service that watches information streams (email, GitHub, etc.) and maintains a compressed historical record.

## Prerequisites

- Docker
- Gmail API credentials
- GitHub token with `repo` scope
- `uv` package manager

## Environment

```env
# API Keys
OPENAI_API_KEY=your_openai_key
PREFECT_API_KEY=your_prefect_key
PREFECT_API_URL=your_prefect_workspace_url
HUMANLAYER_API_KEY=your_humanlayer_key
GITHUB_TOKEN=your_github_token  # needs repo scope

# Service Config
ASSISTANT_PORT=8000
EMAIL_CHECK_INTERVAL_SECONDS=300
GITHUB_CHECK_INTERVAL_SECONDS=300
OBSERVATION_CHECK_INTERVAL_SECONDS=300
```

## Quick Start

```bash
make        # setup and run
make dev    # hot reload
make clean  # cleanup
```

## Development

```bash
pip install -U uv
uv venv --python 3.12
source .venv/bin/activate
UV_SYSTEM_PYTHON=1 uv pip install --editable ".[gmail,github]"
```

Add credentials:

```
app/
  └── secrets/
      ├── gmail_credentials.json  # from Google Cloud Console
      └── gmail_token.json       # generated on first run
```

## How It Works

Events flow through three stages:

```python
# 1. Raw observations in summaries/
ObservationSummary(
    timestamp=now,
    summary="PR #123 needs review",
    source_types=["github"]
)

# 2. Compacted into summaries/compact/
CompactedSummary(
    start_time=window_start,
    end_time=window_end,
    summary="Core API redesign in [RFC-123](url)",
    key_points=["Database migration planned"],
    importance_score=0.9
)

# 3. Archived in summaries/processed/
# (raw observations preserved but moved)
```

The system maintains only critical information over time, preserving context through markdown links to source materials. See `app/background.py` for compression logic and `app/agents.py` for the intelligence layer.

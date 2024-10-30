# Assistant App

Implementation of the Assistant service with web UI and API endpoints.

## Prerequisites

- Python 3.10+
- `uv` package manager ([install guide](https://github.com/astral-sh/uv))
- API credentials:
  - OpenAI API key
  - Gmail OAuth2 (`gmail_credentials.json` and `gmail_token.json`)
  - GitHub token with `repo` scope
  - Slack bot token with `channels:history` and `channels:read` scopes
  - Prefect Cloud workspace (optional)
  - HumanLayer API key (optional)

## Setup

1. **Install Dependencies**

```bash
pip install -U uv
uv venv --python 3.12
source .venv/bin/activate
UV_SYSTEM_PYTHON=1 uv pip install --editable ".[dev]"
```

2. **Configure Environment**

```bash
# Create .env file
cat > app/secrets/.env << EOL
# Required
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
SLACK_BOT_TOKEN=xoxb-...

# Optional
PREFECT_API_KEY=pnu_...
PREFECT_API_URL=https://api.prefect.cloud/...
HUMANLAYER_API_KEY=hl_...

# Enable Processors
EMAIL_ENABLED=true
GITHUB_ENABLED=true
SLACK_ENABLED=true

# Intervals (seconds)
EMAIL_CHECK_INTERVAL_SECONDS=300
GITHUB_CHECK_INTERVAL_SECONDS=300
SLACK_CHECK_INTERVAL_SECONDS=300
OBSERVATION_CHECK_INTERVAL_SECONDS=300

# Port for web UI
ASSISTANT_PORT=8000
EOL
```

3. **Add Gmail Credentials**

```bash
mkdir -p app/secrets
# Copy credentials from Google Cloud Console
cp /path/to/credentials.json app/secrets/gmail_credentials.json
# Token will be generated on first run
touch app/secrets/gmail_token.json
```

4. **Storage Management**

The app automatically creates storage directories for observations and summaries. If you want to clear the assistant's memory:

```bash
rm -rf app/summaries/{compact,processed}
```

## Running

```bash
make dev    # Development with hot reload
# or
make        # Production in container
```

Access:

- Web UI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## API Examples

```bash
# Get recent observations
curl "localhost:8000/observations/recent"

# Past 12 hours only
curl "localhost:8000/observations/recent?hours=12"
```

## Directory Structure

```
app/
├── summaries/           # Event storage
│   ├── *.json          # New observations
│   ├── compact/        # Compressed historical record
│   └── processed/      # Archived raw observations
├── secrets/            # Credentials
│   ├── gmail_*.json    # Gmail OAuth2
├── templates/          # Web UI
└── static/            # Assets
```

## Troubleshooting

1. **Gmail Authentication**

```bash
# If token expires:
rm app/secrets/gmail_token.json
# Restart app and follow OAuth prompt
```

2. **GitHub Rate Limits**

- Increase `GITHUB_CHECK_INTERVAL_SECONDS` in `.env`
- Use a token with appropriate scopes

3. **Slack Issues**

- Ensure bot is invited to channels
- Verify bot has required scopes
- Check token validity

4. **Missing Summaries**

- Create directories: `mkdir -p app/summaries/{compact,processed}`
- Check file permissions

## Development

- Use `make dev` for hot reload during development
- Run `make check-env` to verify configuration
- See `scripts/configure.py` for environment validation

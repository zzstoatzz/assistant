# Information Observer

AI assistant that processes information streams and maintains a compressed historical record.

## Sources

- **GitHub**: PRs, issues, and workflow runs
- **Gmail**: Unread messages
- _More coming soon_

## Structure

```
app/
├── summaries/           # Event storage
│   ├── *.json          # New observations
│   ├── compact/        # Compressed historical record
│   └── processed/      # Archived raw observations
├── secrets/            # Credentials
│   ├── gmail_*.json
│   └── .env           # Environment variables
├── templates/          # Web UI
└── static/            # Assets
```

## Features

- Web UI at `http://localhost:8000`
- JSON API at `/observations/recent`
- Markdown support in summaries
- Link preservation for context
- LSM tree-like compression (recent detailed, history condensed)

## Running Locally

```bash
# 1. Install dependencies
UV_SYSTEM_PYTHON=1 uv pip install --editable ".[gmail,github]"

# 2. Set up environment variables
cat > app/secrets/.env << EOL
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...  # needs repo scope
PREFECT_API_KEY=pnu_...
PREFECT_API_URL=https://api.prefect.cloud/...
HUMANLAYER_API_KEY=hl_...
EMAIL_CHECK_INTERVAL_SECONDS=300
GITHUB_CHECK_INTERVAL_SECONDS=300
OBSERVATION_CHECK_INTERVAL_SECONDS=300
EOL

# 3. Add Gmail credentials
# Get these from Google Cloud Console
cp gmail_credentials.json app/secrets/
# Token will be generated on first run
touch app/secrets/gmail_token.json

# 4. Run
make dev  # hot reload
# or
make      # production mode
```

## API Examples

```bash
# Get recent and historical summaries
curl "localhost:8000/observations/recent"

# Past 12 hours only
curl "localhost:8000/observations/recent?hours=12"
```

Response format:

```json
{
  "timespan_hours": 24,
  "recent_summary": "Recent GitHub activity: [PR #123](url) needs review...",
  "historical_summary": "Core API redesign ([RFC-123](url)) in progress...",
  "num_recent_summaries": 5,
  "num_historical_summaries": 1,
  "source_types": ["github", "email"]
}
```

## Common Issues

1. Gmail authentication:

```bash
# If token expires
rm app/secrets/gmail_token.json
# Restart app and follow OAuth prompt
```

2. GitHub rate limits:

```python
# Adjust in settings.py
GITHUB_CHECK_INTERVAL_SECONDS = 300  # 5 minutes minimum
```

3. Missing summaries directory:

```bash
mkdir -p app/summaries/{compact,processed}
```

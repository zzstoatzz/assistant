# Assistant

## Quick Start

See `app/README.md` for detailed setup, or run:

> [!NOTE]
> `just` is _"just"_ (🙂) like `make`, but in Rust (trying it out for fun). [install](https://github.com/casey/just?tab=readme-ov-file#packages)

```bash
just setup  # Setup environment
just dev    # Development with hot reload
just run    # Build and run in container
just clean  # Cleanup
```

To see all available commands:

```bash
just -l
```

---

An AI-powered service that observes information streams (email, GitHub, Slack) and maintains a compressed historical record, focusing on what's important while preserving context.

## How It Works

Events flow through three stages:

1. **Raw Observations**: New events from various sources are collected and summarized
2. **Compression**: Related events are grouped and compressed over time
3. **Archive**: Historical context is preserved with links to source materials

```python
# Example: How information flows through the system
ObservationSummary(
    timestamp=now,
    summary="PR #123 needs review",
    source_types=["github", "slack"]
)
↓
CompactedSummary(
    start_time=window_start,
    end_time=window_end,
    summary="Core API redesign in [RFC-123](url)",
    key_points=["Database migration planned"],
    importance_score=0.9
)
```

## Project Structure

> [!WARNING]
> The project is under active development and the structure is subject to change.

- `app/`: The main application (work in progress)
- `assistant/`: Core library with more stable abstractions
- See `app/README.md` for detailed setup instructions

## Features

- Multi-source observation (Email, GitHub, Slack)
- Intelligent summarization using LLMs
- LSM-tree inspired compression strategy
- Context preservation through markdown links
- Web UI and API access

## Demo

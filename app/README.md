# Information Observer System

## Overview
A system that lets an AI assistant process information streams like a human would - checking sources, understanding content, and reporting back meaningfully.

## Core Structure

### Observer Protocol
```python
class Observer[S, E](ABC):
    def connect(self) -> None: ...
    def observe(self) -> Iterator[E]: ...
    def disconnect(self) -> None: ...
```

- Generic over source type `S` and event type `E`
- Simple sync interface (no fake async)
- Standardized event structure via `BaseEvent`

### Event Model
```python
@dataclass
class BaseEvent:
    id: str
    source_type: str
    timestamp: datetime = field(default_factory=...)
    raw_source: str | None = None
```

### Gmail Implementation
- Concrete observer watching email
- Handles OAuth flow and credentials
- Processes unread messages
- Marks messages as read after processing

## FastAPI Service

### Background Processing
- Prefect deployment runs observation flows
- Serializes summaries to disk as JSON
- Each summary includes:
  - Timestamp
  - Event details
  - Agent-generated overview
  - Source metadata

### API Endpoints
`GET /observations/recent`
- Aggregates stored summaries
- Uses ControlFlow agent to generate insights
- Configurable time window

## Key Design Choices
1. **Simple Storage**: JSON files instead of a database
2. **Sync Protocol**: Clear, honest interfaces
3. **Standard Events**: Common structure across sources
4. **Agent Processing**: Uses ControlFlow

## Usage
```bash
# From the root directory
uv run app/main.py

# Get recent observations (default 24h)
curl "http://localhost:8000/observations/recent"

# Get custom timespan
curl "http://localhost:8000/observations/recent?hours=12"
```
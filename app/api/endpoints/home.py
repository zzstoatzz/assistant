import httpx
from fastapi import APIRouter, Request

from app.api.dependencies import get_enabled_processors, load_summaries
from app.api.templates import templates
from app.settings import settings
from app.storage import DiskStorage
from assistant.utilities.loggers import get_logger

router = APIRouter()
storage = DiskStorage(settings.summaries_dir)
logger = get_logger('app.api.endpoints.home')


async def get_random_duck() -> dict:
    """Get a random duck image and message"""
    async with httpx.AsyncClient() as client:
        response = await client.get('https://random-d.uk/api/v2/random')
        return response.json()


@router.get('/')
async def home(request: Request, hours: int = 24):
    """Home page showing daily cards and historical pinboard"""
    recent_summaries, compact_summaries = load_summaries(hours)

    # Load all entities with debug logging
    entities_by_id = {e.id: e for e in storage.get_entities()}
    logger.debug(f'Loaded {len(entities_by_id)} entities')
    for entity_id, entity in entities_by_id.items():
        logger.debug(f'Entity {entity_id}: {entity.name} ({entity.type}) from {entity.source}')

    # Group recent summaries by day and sort newest first within each day
    daily_summaries = {}
    for summary in sorted(recent_summaries, key=lambda s: s.timestamp, reverse=True):
        # Convert UTC timestamp to local time for display
        logger.debug(f'Using timezone: {settings.tz}')
        day_id = summary.timestamp.strftime('%Y-%m-%d')

        # Add referenced entities to summary
        summary.referenced_entities = [
            entities_by_id[entity_id] for entity_id in summary.entity_mentions if entity_id in entities_by_id
        ]

        daily_summaries.setdefault(day_id, []).append(summary)

    # Sort each day's summaries newest first
    for day_summaries in daily_summaries.values():
        day_summaries.sort(key=lambda s: s.timestamp, reverse=True)

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'daily_summaries': daily_summaries,
            'compact_summaries': sorted(compact_summaries, key=lambda s: s.end_time, reverse=True),
            'hours': hours,
            'has_data': bool(daily_summaries or compact_summaries),
            'duck_data': await get_random_duck(),
            'enabled_processors': get_enabled_processors(),
            'entities': sorted(entities_by_id.values(), key=lambda e: e.importance, reverse=True),
        },
    )

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.api.dependencies import get_enabled_sources, load_summaries
from app.api.templates import templates
from app.storage import DiskStorage
from assistant.utilities.loggers import get_logger

router = APIRouter()
storage = DiskStorage()
logger = get_logger('app.api.home')


async def get_random_duck() -> dict:
    """Get a random duck image and message"""
    async with httpx.AsyncClient() as client:
        response = await client.get('https://random-d.uk/api/v2/random')
        return response.json()


@router.get('/')
async def home(request: Request, hours: int = 24) -> HTMLResponse:
    """Render home page with recent observations and summaries"""
    try:
        recent_summaries, compact_summaries = load_summaries(hours=hours)

        # Get all entities for lookup
        all_entities = {e.id: e for e in storage.get_entities()}

        # Add referenced entities to each summary
        for summary in recent_summaries:
            summary.referenced_entities = [
                all_entities[entity_id] for entity_id in (summary.entity_mentions or []) if entity_id in all_entities
            ]

        # Sort summaries by timestamp in descending order
        recent_summaries.sort(key=lambda x: x.timestamp, reverse=True)
        compact_summaries.sort(key=lambda x: x.end_time, reverse=True)

        # Group summaries by day for the template
        daily_summaries = {}
        for summary in recent_summaries:
            day = summary.timestamp.strftime('%Y-%m-%d')
            if day not in daily_summaries:
                daily_summaries[day] = []
            daily_summaries[day].append(summary)

        return templates.TemplateResponse(
            'home.html',
            {
                'request': request,
                'daily_summaries': daily_summaries,
                'compact_summaries': compact_summaries,
                'hours': hours,
                'duck_data': await get_random_duck(),
                'enabled_processors': get_enabled_sources(),
                'entities': storage.get_entities(),
            },
        )
    except Exception as e:
        logger.error(f'Error rendering home page: {e}', exc_info=True)
        raise

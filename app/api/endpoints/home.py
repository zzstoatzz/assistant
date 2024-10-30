import httpx
from fastapi import APIRouter, Request

from app.api.dependencies import get_enabled_processors, load_summaries
from app.api.templates import templates
from app.settings import settings
from app.storage import DiskStorage
from assistant.utilities.loggers import get_logger

router = APIRouter()
storage = DiskStorage(settings.app_dir)

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

    # Group recent summaries by day and sort newest first within each day
    daily_summaries = {}
    for summary in sorted(recent_summaries, key=lambda s: s.timestamp, reverse=True):
        # Convert UTC timestamp to local time for display
        logger.debug(f'Using timezone: {settings.tz}')
        local_ts = summary.timestamp.astimezone(settings.tz)
        day_id = local_ts.strftime('%Y-%m-%d')
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
        },
    )

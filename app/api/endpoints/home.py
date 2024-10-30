import httpx
from fastapi import APIRouter, Request

from app.api.dependencies import get_enabled_processors, load_summaries
from app.api.templates import templates
from app.types import ObservationSummary

router = APIRouter()


async def get_random_duck() -> dict:
    """Get a random duck image and message"""
    async with httpx.AsyncClient() as client:
        response = await client.get('https://random-d.uk/api/v2/random')
        return response.json()


@router.get('/')
async def home(request: Request, hours: int = 24):
    """Home page showing daily cards and historical pinboard"""
    recent_summaries, compact_summaries = load_summaries(hours)

    # Organize summaries by day and time
    daily_summaries: dict[str, list[ObservationSummary]] = {}
    for summary in sorted(recent_summaries, key=lambda s: s.timestamp, reverse=True):
        daily_summaries.setdefault(summary.day_id, []).append(summary)

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'daily_summaries': daily_summaries,
            'compact_summaries': sorted(compact_summaries, key=lambda s: s.end_time, reverse=True),
            'hours': hours,
            'has_data': bool(recent_summaries or compact_summaries),
            'duck_data': await get_random_duck(),
            'enabled_processors': get_enabled_processors(),
        },
    )

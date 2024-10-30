from datetime import datetime

import httpx
from fastapi import APIRouter, Request

from app.api.dependencies import load_summaries
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

    duck_data = None
    # Show duck for empty days as well as completely empty state
    if not daily_summaries.get(datetime.now().strftime('%Y-%m-%d'), []):
        duck_data = await get_random_duck()

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'daily_summaries': daily_summaries,
            'compact_summaries': sorted(compact_summaries, key=lambda s: s.end_time, reverse=True),
            'hours': hours,
            'has_data': bool(recent_summaries or compact_summaries),
            'duck_data': duck_data,
        },
    )

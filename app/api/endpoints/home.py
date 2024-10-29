import httpx
from fastapi import APIRouter, Request

from app.api.dependencies import load_summaries
from app.api.templates import templates

router = APIRouter()


async def get_random_duck() -> dict:
    """Get a random duck image and message"""
    async with httpx.AsyncClient() as client:
        response = await client.get('https://random-d.uk/api/v2/random')
        return response.json()


@router.get('/')
async def home(request: Request, hours: int = 24):
    """Home page showing both recent and compacted observations"""
    recent_summaries, compact_summaries = load_summaries(hours)

    duck_data = None
    if not (recent_summaries or compact_summaries):
        duck_data = await get_random_duck()

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'recent_summaries': recent_summaries,
            'compact_summaries': compact_summaries,
            'hours': hours,
            'has_data': bool(recent_summaries or compact_summaries),
            'duck_data': duck_data,
        },
    )

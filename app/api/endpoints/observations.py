import controlflow as cf
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.agents import secretary
from app.api.dependencies import load_summaries
from assistant.utilities.loggers import get_logger

logger = get_logger()
router = APIRouter(prefix='/observations')


@router.get('/recent')
async def get_recent_observations(hours: int = 24) -> JSONResponse:
    """Get recent and historical observations"""
    logger.info(f'Loading observations for past {hours} hours')
    recent_summaries, compact_summaries = load_summaries(hours)

    if not recent_summaries and not compact_summaries:
        logger.info(f'Successfully searched past {hours} hours - no observations found')
        return JSONResponse(content={'message': 'No observations found'}, status_code=200)

    recent_aggregate = None
    if recent_summaries:
        recent_aggregate = cf.run(
            'Summarize recent activity',
            agent=secretary,
            instructions="""
            Create a clear summary of recent activity.
            Focus on what's happening now and immediate implications.
            Use markdown for formatting if needed.
            """,
            context={'summaries': [s.model_dump() for s in recent_summaries]},
            result_type=str,
        )

    historical_aggregate = None
    if compact_summaries:
        historical_aggregate = cf.run(
            'Distill historical significance',
            agent=secretary,
            instructions="""
            Create an extremely condensed historical record.
            Include only the most significant developments and enduring patterns.
            This should read like a brief historical record - just the key milestones.
            Use markdown for critical emphasis only. Good links can replace long descriptions.
            """,
            context={'summaries': [s.model_dump() for s in compact_summaries]},
            result_type=str,
        )

    return JSONResponse(
        {
            'timespan_hours': hours,
            'recent_summary': recent_aggregate,
            'historical_summary': historical_aggregate,
            'num_recent_summaries': len(recent_summaries),
            'num_historical_summaries': len(compact_summaries),
            'source_types': list(set(st for s in recent_summaries + compact_summaries for st in s.source_types)),
        }
    )

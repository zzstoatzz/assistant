from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import partial

import controlflow as cf
import markdown
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents import secretary
from app.background import check_observations
from app.processors.email import check_email
from app.processors.github import check_github
from app.settings import settings
from app.types import CompactedSummary, ObservationSummary
from assistant.background.task_manager import BackgroundTask, BackgroundTaskManager
from assistant.utilities.loggers import get_logger

logger = get_logger()


def render_markdown(text: str) -> str:
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code', 'tables'])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background task processing"""
    # Start all tasks
    task_manager = BackgroundTaskManager.from_background_tasks(
        [
            BackgroundTask(
                func=partial(check_email, agents=[secretary]),
                interval_seconds=settings.email_check_interval_seconds,
                name='check email',
            ),
            BackgroundTask(
                func=partial(check_github, agents=[secretary]),
                interval_seconds=settings.github_check_interval_seconds,
                name='check github',
            ),
            BackgroundTask(
                func=partial(check_observations, agents=[secretary]),
                interval_seconds=settings.observation_check_interval_seconds,
                name='review observations',
            ),
        ]
    )
    await task_manager.start_all()
    try:
        yield
    finally:
        await task_manager.stop_all()


app = FastAPI(title='Information Observer Service', lifespan=lifespan)

# Mount static files using settings
app.mount('/static', StaticFiles(directory=str(settings.static_dir)), name='static')

# Initialize templates with absolute path
templates = Jinja2Templates(directory=str(settings.templates_dir))


templates.env.filters['markdown'] = render_markdown


@app.get('/')
async def home(request: Request, hours: int = 24):
    """Home page showing both recent and compacted observations"""
    cutoff = datetime.now() - timedelta(hours=hours)

    # Get recent (unprocessed) summaries
    recent_summaries = []
    for summary_file in settings.summaries_dir.glob('summary_*.json'):
        try:
            summary = ObservationSummary.model_validate_json(summary_file.read_text())
            if summary.timestamp > cutoff:
                recent_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {summary_file.name}: {e}')
            continue

    # Get compact summaries from the compact directory
    compact_dir = settings.summaries_dir / 'compact'
    compact_summaries = []
    if compact_dir.exists():
        for summary_file in compact_dir.glob('compact_*.json'):
            try:
                summary = CompactedSummary.model_validate_json(summary_file.read_text())
                if summary.end_time > cutoff:
                    compact_summaries.append(summary)
            except Exception as e:
                logger.error(f'Failed to load compact summary {summary_file.name}: {e}')
                continue

    # Sort summaries
    recent_summaries.sort(key=lambda x: x.timestamp, reverse=True)
    compact_summaries.sort(key=lambda x: (x.end_time, x.importance_score), reverse=True)

    return templates.TemplateResponse(
        'home.html',
        {
            'request': request,
            'recent_summaries': recent_summaries,
            'compact_summaries': compact_summaries,
            'hours': hours,
            'has_data': bool(recent_summaries or compact_summaries),
        },
    )


@app.get('/observations/recent')
async def get_recent_observations(hours: int = 24) -> JSONResponse:
    """Get recent and historical observations"""
    cutoff = datetime.now() - timedelta(hours=hours)
    logger.info(f'Loading observations for past {hours} hours (cutoff: {cutoff})')

    # Load recent summaries
    recent_summaries = []
    for summary_file in settings.summaries_dir.glob('summary_*.json'):
        try:
            summary = ObservationSummary.model_validate_json(summary_file.read_text())
            if summary.timestamp > cutoff:
                recent_summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {summary_file.name}: {e}')
            continue

    # Load compact summaries (historical record)
    compact_summaries = []
    compact_dir = settings.summaries_dir / 'compact'
    if compact_dir.exists():
        for summary_file in compact_dir.glob('compact_*.json'):
            try:
                summary = CompactedSummary.model_validate_json(summary_file.read_text())
                compact_summaries.append(summary)
            except Exception as e:
                logger.error(f'Failed to load compact summary {summary_file.name}: {e}')
                continue

    if not recent_summaries and not compact_summaries:
        return JSONResponse(content={'message': 'No observations found'}, status_code=200)

    # Get recent activity summary
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

    # Get historical record (extremely condensed)
    historical_aggregate = None
    if compact_summaries:
        historical_aggregate = cf.run(
            'Distill historical significance',
            agent=secretary,
            instructions="""
            Create an extremely condensed historical record.
            Include only the most significant developments and enduring patterns.
            This should read like a brief historical record - just the key milestones.
            Use markdown for critical emphasis only.
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


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from app.agents import email_agent, github_agent, secretary, slack_agent
from app.api.dependencies import get_enabled_sources
from app.api.endpoints import entities, home, observations, sources
from app.background import compress_observations
from app.settings import settings
from app.sources.email import check_email, email_settings
from app.sources.github import check_github, github_settings
from app.sources.slack import check_slack, slack_settings
from app.storage import DiskStorage
from assistant.background.task_manager import PeriodicTaskManager, TaskDef
from assistant.utilities.loggers import get_logger

logger = get_logger('main')


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application background tasks"""
    storage = DiskStorage()

    background_tasks: list[TaskDef] = []

    if email_settings.enabled:
        background_tasks.append(
            (BackgroundTask(check_email, storage=storage, agents=[email_agent]), email_settings.check_interval_seconds)
        )

    if github_settings.enabled:
        background_tasks.append(
            (
                BackgroundTask(check_github, storage=storage, agents=[github_agent]),
                github_settings.check_interval_seconds,
            )
        )

    if slack_settings.enabled:
        background_tasks.append(
            (BackgroundTask(check_slack, storage=storage, agents=[slack_agent]), slack_settings.check_interval_seconds)
        )

    if not background_tasks:
        logger.warning('☹️ No 3rd party processors enabled')

    background_tasks.append(
        (
            BackgroundTask(compress_observations, storage=storage, agents=[secretary]),
            settings.observation_check_interval_seconds,
            settings.observation_initial_delay_seconds,
        )
    )

    if settings.user_identity:
        logger.info(f'🧾 Using configured identity: {settings.user_identity}')

    logger.info(f'👀 Watching sources: {get_enabled_sources()!r}')
    logger.info(
        f'🔍 Compressing observations every {settings.observation_check_interval_seconds} seconds '
        f'(after {settings.observation_initial_delay_seconds}s initial delay)'
    )

    task_manager = PeriodicTaskManager(background_tasks)
    await task_manager.start_all()

    try:
        yield
    finally:
        await task_manager.stop_all()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title='Information Observer Service',
        version='1.0.0',
        description=f"""
        An intelligent service that observes and summarizes information from multiple sources:

        {email_settings.enabled and '* 📧 **Email**: Processes Gmail messages' or ''}
        {github_settings.enabled and '* 🐙 **GitHub**: Tracks PRs, issues, and workflow runs' or ''}
        {slack_settings.enabled and '* 📢 **Slack**: Processes Slack messages' or ''}
        '* 📚 **Historical**: Maintains compressed historical records'

        ### Features

        * LSM-tree inspired storage for efficient historical data
        * Intelligent summarization using AI
        * Real-time updates with configurable intervals

        ### Intervals
        * Email checks: Every {email_settings.check_interval_seconds} seconds
        * GitHub checks: Every {github_settings.check_interval_seconds} seconds
        * Slack checks: Every {slack_settings.check_interval_seconds} seconds
        * Observation compression: Every {settings.observation_check_interval_seconds} seconds
        """,
        routes=app.routes,
    )

    openapi_schema['info']['x-logo'] = {'url': 'https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png'}

    openapi_schema['servers'] = [{'url': '', 'description': 'Current server'}]

    if hasattr(settings, 'github_token'):
        openapi_schema['components']['securitySchemes'] = {
            'GitHubToken': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': 'GitHub Personal Access Token',
            }
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app = FastAPI(
    title='Information Observer Service',
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc',
    openapi_url='/openapi.json',
    swagger_ui_parameters={'defaultModelsExpandDepth': -1},
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=['*'],  # Allows all methods
    allow_headers=['*'],  # Allows all headers
)

app.openapi = custom_openapi

app.mount('/static', StaticFiles(directory=str(settings.paths.static)), name='static')


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(str(settings.paths.static / 'favicon.ico'))


app.include_router(home.router)
app.include_router(observations.router)
app.include_router(entities.router)
app.include_router(sources.router)

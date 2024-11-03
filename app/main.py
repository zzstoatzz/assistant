from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents import email_agent, github_agent, secretary, slack_agent
from app.api.dependencies import get_enabled_processors
from app.api.endpoints import entities, home, observations, sources
from app.background import compress_observations
from app.processors.email import check_email
from app.processors.email import settings as email_settings
from app.processors.github import check_github
from app.processors.github import settings as github_settings
from app.processors.slack import check_slack
from app.processors.slack import settings as slack_settings
from app.settings import settings
from app.storage import DiskStorage
from assistant.background.task_manager import BackgroundTaskManager
from assistant.utilities.loggers import get_logger

logger = get_logger('main')


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background task processing"""
    summary_storage = DiskStorage()
    functions: list[tuple[Callable[..., None], float]] = []

    if email_settings.enabled:
        functions.append(
            (partial(check_email, storage=summary_storage, agents=[email_agent]), email_settings.check_interval_seconds)
        )

    if github_settings.enabled:
        functions.append(
            (
                partial(check_github, storage=summary_storage, agents=[github_agent]),
                github_settings.check_interval_seconds,
            )
        )

    if slack_settings.enabled:
        functions.append(
            (partial(check_slack, storage=summary_storage, agents=[slack_agent]), slack_settings.check_interval_seconds)
        )

    if not functions:
        logger.warning('☹️ No 3rd party processors enabled')

    if settings.user_identity:
        logger.info(f'🧾 Using configured identity: {settings.user_identity}')

    logger.info(f'👀 Watching sources: {get_enabled_processors()!r}')

    logger.info(f'🔍 Compressing observations every {settings.observation_check_interval_seconds} seconds')

    functions.append(
        (
            partial(
                compress_observations,
                storage=summary_storage,
                agents=[secretary],
            ),
            settings.observation_check_interval_seconds,
        )
    )

    task_manager = BackgroundTaskManager(functions)
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

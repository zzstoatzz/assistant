from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents import email_agent, github_agent, slack_agent
from app.processors.email import check_email
from app.processors.email import settings as email_settings
from app.processors.github import check_github
from app.processors.github import settings as github_settings
from app.processors.slack import check_slack
from app.processors.slack import settings as slack_settings
from app.storage import DiskStorage
from assistant.utilities.loggers import get_logger

router = APIRouter(prefix='/api/sources')
storage = DiskStorage()
logger = get_logger('app.api.sources')


class RefreshResponse(BaseModel):
    source: str
    status: str
    message: str


@router.post('/refresh/{source}')
async def refresh_source(source: str) -> RefreshResponse:
    """Manually trigger a source refresh"""
    try:
        if source == 'email' and email_settings.enabled:
            summary = check_email(storage=storage, agents=[email_agent])
            message = 'Found new emails' if summary else 'no new emails'
            return RefreshResponse(source=source, status='success', message=message)

        elif source == 'github' and github_settings.enabled:
            summary = check_github(storage=storage, agents=[github_agent])
            message = 'Found new notifications' if summary else 'no new notifications'
            return RefreshResponse(source=source, status='success', message=message)

        elif source == 'slack' and slack_settings.enabled:
            summary = check_slack(storage=storage, agents=[slack_agent])
            message = 'Found new messages' if summary else 'no new messages'
            return RefreshResponse(source=source, status='success', message=message)

        else:
            raise HTTPException(status_code=400, detail=f"Source '{source}' not found or not enabled")

    except Exception as e:
        logger.error(f'Failed to refresh {source}: {e}')
        raise HTTPException(status_code=500, detail=f'Failed to refresh {source}: {str(e)}')

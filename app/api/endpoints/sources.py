from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.agents import email_agent, github_agent, slack_agent
from app.sources.email import check_email, email_settings
from app.sources.github import check_github, github_settings
from app.sources.slack import check_slack, slack_settings
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
async def refresh_source(source: str, request: Request):
    """Manually trigger a source refresh"""
    try:
        if source == 'email' and email_settings.enabled:
            summary = check_email(storage=storage, agents=[email_agent])
            message = 'Found new emails' if summary else 'no new emails'
            status = 'success'
        elif source == 'github' and github_settings.enabled:
            summary = check_github(storage=storage, agents=[github_agent])
            message = 'Found new notifications' if summary else 'no new notifications'
            status = 'success'
        elif source == 'slack' and slack_settings.enabled:
            summary = check_slack(storage=storage, agents=[slack_agent])
            message = 'Found new messages' if summary else 'no new messages'
            status = 'success'
        else:
            raise HTTPException(status_code=400, detail=f"Source '{source}' not found or not enabled")

        if request.headers.get('hx-request') == 'true':
            # Return HTML snippet for HTMX
            if 'no new' in message:
                button_html = f"""
                <button class="refresh-button" disabled title="{message}">
                  ✓
                  <span class="refresh-indicator-{source} htmx-indicator" style="display:none">⏳</span>
                </button>
                """
            else:
                button_html = f"""
                <button class="refresh-button success" title="{message}" hx-post="/api/sources/refresh/{source}" hx-trigger="click" hx-target="this" hx-swap="outerHTML" hx-indicator=".refresh-indicator-{source}">
                  ✓
                  <span class="refresh-indicator-{source} htmx-indicator" style="display:none">⏳</span>
                </button>
                """
            return HTMLResponse(button_html)
        else:
            return JSONResponse({'source': source, 'status': status, 'message': message})
    except Exception as e:
        logger.error(f'Failed to refresh {source}: {e}')
        raise HTTPException(status_code=500, detail=f'Failed to refresh {source}: {str(e)}')

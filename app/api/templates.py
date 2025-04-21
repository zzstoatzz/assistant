import markdown
from fastapi.templating import Jinja2Templates

from app.settings import settings


def render_markdown(text: str) -> str:
    """Convert markdown to HTML"""
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code', 'tables'], output_format='html')


def id_safe(value: str) -> str:
    return value.encode('utf-8').hex()


templates = Jinja2Templates(directory=str(settings.paths.templates))
templates.env.filters['markdown'] = render_markdown
templates.env.filters['id_safe'] = id_safe

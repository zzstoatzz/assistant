import markdown
from fastapi.templating import Jinja2Templates

from app.settings import settings


def render_markdown(text: str) -> str:
    """Convert markdown to HTML"""
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code', 'tables'], output_format='html5')


templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.filters['markdown'] = render_markdown

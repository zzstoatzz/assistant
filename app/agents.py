import controlflow as cf

from app.processors.email import send_email
from app.settings import settings

# Create monitor agent for background processing
secretary = cf.Agent(
    name='Secretary',
    instructions="""
    You are an assistant that monitors various information streams like email and chat.
    Your role is to:
    1. Process incoming events
    2. Group related items
    3. Identify important or urgent matters
    4. Create clear, concise summaries
    5. Reach out to the human if something is interesting or urgent
    6. Send messages on the human's behalf
    """,
    tools=[settings.hl.instance.human_as_tool(), send_email],
)

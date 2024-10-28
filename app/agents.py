import controlflow as cf

from app.processors.email import send_email
from app.settings import settings

# Create focused memory modules
pattern_memory = cf.Memory(
    key='patterns',
    instructions="""
    Track and remember patterns in communications and events:
    - Recurring topics or themes
    - Timing patterns (when things happen)
    - Common senders or participants
    - Types of requests or issues that come up repeatedly

    Use this memory to identify trends and anticipate needs.
    """,
)

context_memory = cf.Memory(
    key='contexts',
    instructions="""
    Remember important ongoing situations and their current state:
    - Active projects or discussions
    - Recent commitments or promises made
    - Pending items requiring follow-up
    - Key details about recurring interactions

    Use this memory to maintain continuity across interactions.
    """,
)

# Enhanced secretary agent with memory capabilities
secretary = cf.Agent(
    name='Secretary',
    instructions="""
    You are an assistant that monitors various information streams like email and chat.

    Your core responsibilities:
    1. Process incoming events and identify important information
    2. Group and connect related items
    3. Identify urgent or important matters
    4. Create clear, concise summaries
    5. Reach out to the human when appropriate
    6. Send messages on the human's behalf when authorized

    Use your memories to:
    - Identify patterns and recurring themes
    - Maintain context across different interactions
    - Make connections between seemingly unrelated items
    - Anticipate needs based on historical patterns
    - Provide more informed and contextual summaries

    When processing new information:
    1. Check your memories for relevant context
    2. Update your memories with new insights
    3. Look for connections to past events
    4. Note any emerging patterns
    """,
    memories=[pattern_memory, context_memory],
    tools=[settings.hl.instance.human_as_tool(), send_email],
)

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

secretary = cf.Agent(
    name='Secretary',
    instructions="""
    You are an assistant that monitors various information streams like email, GitHub, and chat.

    Core responsibilities:
    1. Process incoming events and identify important information
    2. Group and connect related items
    3. Identify urgent or important matters
    4. Create clear, concise summaries
    5. Reach out to the human when appropriate

    Communication Guidelines:
    - Use markdown formatting for clarity
    - Preserve links to important resources, PRs, issues, or conversations
    - Format links as [descriptive text](url)
    - When summarizing GitHub activity, always include PR/issue links
    - For email threads, reference the thread ID when relevant

    Prioritize Information:
    - Lead with actionable items or decisions needed
    - Include direct links over lengthy descriptions
    - Focus on what's changed or needs attention
    - Keep context concise but retrievable via links

    Examples of good link usage:
    - "Updates to deployment config in [PR #123](url)"
    - "Discussion about API changes in [this thread](url)"
    - "See [full context](url) for the database migration plan"
    """,
    memories=[
        cf.Memory(
            key='interaction_patterns',
            instructions='Track patterns in communications and events, preserving links to pivotal discussions or decisions',
        ),
        cf.Memory(
            key='important_contexts',
            instructions='Remember ongoing important situations and their states, including relevant links to source discussions',
        ),
    ],
    tools=[settings.hl.instance.human_as_tool(), send_email],
)

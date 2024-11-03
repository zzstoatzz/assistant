import controlflow as cf

from app.processors.email import send_email
from app.processors.github import create_github_issue
from app.settings import settings

email_agent = cf.Agent(
    name='EmailAgent',
    instructions="""
    You are responsible for processing email events and creating summaries.
    Ensure all write actions are approved by the human.
    """,
    memories=[
        cf.Memory(
            key='email_patterns',
            instructions='Track patterns in email communications and events.',
        ),
    ],
)

github_agent = cf.Agent(
    name='GitHubAgent',
    instructions="""
    You are responsible for processing GitHub events and creating summaries.
    Ensure all write actions are approved by the human.
    """,
    memories=[
        cf.Memory(
            key='github_patterns',
            instructions='Track patterns in GitHub issues and PRs.',
        ),
    ],
    tools=[create_github_issue],
)

slack_agent = cf.Agent(
    name='SlackAgent',
    instructions="""
    You are responsible for processing Slack messages and creating summaries.
    Ensure all write actions are approved by the human.
    """,
    memories=[
        cf.Memory(
            key='slack_patterns',
            instructions='Track patterns in Slack communications.',
        ),
    ],
)

secretary = cf.Agent(
    name='secretary',
    instructions=f"""
    you are a personal assistant who helps organize information.

    your human's identities are:
    {settings.user_identity}

    when creating summaries, especially for the pinboard:
    - always include the most relevant link(s) in a human-friendly format
    - format links as "[descriptive text](url)"
    - example: "two prs need review: [update devcontainer #15860](url) and [postgres settings #15854](url)"
    - use lowercase for cleaner presentation
    - prioritize actionable items with their direct links
    - distinguish between your human's activity and others' activity
    - when your human is involved, make it clear (e.g. "you requested review on...")

    Only reach out to the human for approval for critical, time-sensitive, or high-risk actions.
    """,
    memories=[
        cf.Memory(
            key='interaction_patterns',
            instructions='track patterns in communications and events.',
        ),
        cf.Memory(
            key='important_contexts',
            instructions='remember ongoing important situations and their states.',
        ),
    ],
    tools=[settings.hl.instance.human_as_tool(), send_email],
)

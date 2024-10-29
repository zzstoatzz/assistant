import controlflow as cf

from app.processors.email import send_email
from app.processors.github import create_github_issue
from app.settings import settings

# Define an agent for email processing
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
    tools=[send_email],
)

# Define an agent for GitHub processing
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

# Define an agent for Slack processing
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

# Update the Secretary agent
secretary = cf.Agent(
    name='Secretary',
    instructions="""
    You are the central delegator, responsible for overseeing all information streams.
    You can use the human as a tool for urgent or important matters.
    """,
    memories=[
        cf.Memory(
            key='interaction_patterns',
            instructions='Track patterns in communications and events.',
        ),
        cf.Memory(
            key='important_contexts',
            instructions='Remember ongoing important situations and their states.',
        ),
    ],
    tools=[settings.hl.instance.human_as_tool()],
)

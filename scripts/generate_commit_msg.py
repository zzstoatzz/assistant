#!/usr/bin/env python3

import controlflow as cf
from pydantic import BaseModel, Field

from app.agents import secretary
from assistant.utilities.loggers import get_logger

logger = get_logger('commit-msg')


class CommitMessage(BaseModel):
    """AI-generated commit message"""

    message: str = Field(description='Concise description of changes')
    type: str = Field(description='Commit type (feat, fix, docs, style, refactor, test, chore)')
    scope: str | None = Field(default=None, description='Optional scope of changes')


def get_staged_diff() -> str:
    """Get unified diff of staged changes"""
    import subprocess

    result = subprocess.run(
        ['git', 'diff', '--cached'],
        capture_output=True,
        text=True,
    )
    return result.stdout


def main() -> int:
    """Generate commit message for staged changes"""
    try:
        diff = get_staged_diff()
        if not diff:
            logger.warning('No staged changes')
            return 1

        msg = cf.run(
            'Generate commit message',
            agent=secretary,
            instructions="""
            Analyze the git diff and generate a conventional commit message.
            Be concise but descriptive. Focus on the what and why.

            Examples:
            - feat(api): add user authentication endpoints
            - fix: handle timezone-naive datetimes
            - refactor(storage): centralize path management
            """,
            context={'diff': diff},
            result_type=CommitMessage,
        )

        # Format conventional commit
        commit_msg = f'{msg.type}'
        if msg.scope:
            commit_msg += f'({msg.scope})'
        commit_msg += f': {msg.message}'

        print(commit_msg)  # pre-commit will use this as the commit message
        return 0

    except Exception as e:
        logger.error(f'Failed to generate message: {e}')
        return 1


if __name__ == '__main__':
    exit(main())

#!/usr/bin/env python3
import subprocess
from pathlib import Path
from typing import TypeAlias

import controlflow as cf
from pydantic import BaseModel, Field

from app.agents import secretary
from assistant.utilities.loggers import get_logger

logger = get_logger('pre-commit')

GitDiff: TypeAlias = dict[str, str]


class CommitMetadata(BaseModel):
    """Structured commit message with optional metadata"""

    message: str = Field(description='Main commit message')
    body: str | None = Field(default=None, description='Optional detailed description')
    type: str = Field(default='chore', description='Commit type (feat, fix, docs, style, refactor, test, chore)')
    scope: str | None = Field(default=None, description='Scope of changes (e.g., api, storage, ui)')
    breaking: bool = Field(default=False, description='Whether this is a breaking change')


def get_staged_changes() -> GitDiff:
    """Get staged file changes and their diffs"""
    # Get staged files
    staged = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'], capture_output=True, text=True
    ).stdout.splitlines()

    changes = {}
    for file in staged:
        if Path(file).exists():  # Skip deleted files
            # Get diff for each staged file
            diff = subprocess.run(['git', 'diff', '--cached', file], capture_output=True, text=True).stdout
            changes[file] = diff

    return changes


def generate_commit_metadata(changes: GitDiff) -> CommitMetadata:
    """Generate commit metadata using controlflow"""
    return cf.run(
        'Generate commit metadata',
        agent=secretary,
        instructions="""
        Analyze the staged changes and generate appropriate commit metadata.

        Guidelines:
        1. Message should be clear and concise (<50 chars if possible)
        2. Use conventional commit types (feat, fix, etc.)
        3. Include scope if changes are focused
        4. Add body for complex changes
        5. Mark breaking changes

        Focus on the most important changes if multiple files are modified.
        """,
        context={'changes': changes},
        result_type=CommitMetadata,
    )


def main() -> int:
    """Main pre-commit hook logic"""
    try:
        changes = get_staged_changes()
        if not changes:
            logger.warning('No staged changes found')
            return 1

        metadata = generate_commit_metadata(changes)

        # Format conventional commit message
        msg_parts = []
        if metadata.breaking:
            msg_parts.append('BREAKING CHANGE: ')

        msg_parts.append(metadata.type)
        if metadata.scope:
            msg_parts.append(f'({metadata.scope})')
        msg_parts.append(f': {metadata.message}')

        commit_msg = ''.join(msg_parts)

        # Write to temporary commit message file
        commit_msg_file = Path('.git/COMMIT_EDITMSG')
        with commit_msg_file.open('w') as f:
            f.write(commit_msg)
            if metadata.body:
                f.write(f'\n\n{metadata.body}')

        logger.info(f'Generated commit message: {commit_msg}')
        return 0

    except Exception as e:
        logger.error(f'Failed to generate commit message: {e}')
        return 1


if __name__ == '__main__':
    exit(main())

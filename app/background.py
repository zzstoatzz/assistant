import asyncio
from collections.abc import Callable, Sequence
from typing import Any

import controlflow as cf
from prefect import flow
from prefect.logging.loggers import get_logger

from app.settings import settings

logger = get_logger()


@flow
def check_observations(agents: list[cf.Agent]) -> None:
    """Check observations on disk and process if necessary"""

    # Only get unprocessed summaries
    summary_files = list(settings.summaries_dir.glob('*.json'))
    unprocessed_summaries = [
        p
        for p in summary_files
        if p.parent == settings.summaries_dir  # Exclude files in processed subdir
    ]

    if not unprocessed_summaries:
        return None

    summaries = [p.read_text() for p in unprocessed_summaries]

    maybe_interesting_stuff = cf.run(
        'Check if any of the summaries are interesting, reach out to the human if they are',
        agents=agents,
        context={'summaries': summaries},
    )

    # Move processed files to processed directory
    for file_path in unprocessed_summaries:
        new_path = settings.processed_summaries_dir / file_path.name
        file_path.rename(new_path)
        logger.info(f'Moved processed summary: {file_path.name}')

    return maybe_interesting_stuff


class BackgroundTask:
    """Represents a periodic background task"""

    def __init__(self, func: Callable[[], Any], interval_seconds: float, name: str = None):
        self.func = func
        self.interval_seconds = interval_seconds
        self.name = name or func.__name__
        self.task: asyncio.Task | None = None

    async def run(self) -> None:
        """Run the task periodically"""
        logger.info(f'Starting {self.name} with {self.interval_seconds} second interval')
        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self.func)
            except Exception as e:
                logger.error(f'{self.name} failed: {e}')
            await asyncio.sleep(self.interval_seconds)


class BackgroundTaskManager:
    """Manages multiple background tasks"""

    def __init__(self):
        self.tasks: list[BackgroundTask] = []

    @classmethod
    def from_background_tasks(cls, tasks: Sequence[BackgroundTask]) -> 'BackgroundTaskManager':
        """Create a task manager from a sequence of background tasks"""
        manager = cls()
        for task in tasks:
            manager.tasks.append(task)
        return manager

    def add_task(self, func: Callable[[], Any], interval_seconds: float, name: str = None) -> None:
        """Add a new background task"""
        self.tasks.append(BackgroundTask(func, interval_seconds, name))

    async def start_all(self) -> None:
        """Start all registered tasks"""
        for bg_task in self.tasks:
            bg_task.task = asyncio.create_task(bg_task.run())

    async def stop_all(self) -> None:
        """Stop all running tasks"""
        for bg_task in self.tasks:
            if bg_task.task:
                bg_task.task.cancel()
                try:
                    await bg_task.task
                except asyncio.CancelledError:
                    pass


task_manager = BackgroundTaskManager()

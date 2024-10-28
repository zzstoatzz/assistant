import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)


class BackgroundTask:
    """Represents a periodic background task"""

    def __init__(self, func: Callable[[], Any], interval_seconds: float, name: str | None = None):
        self.func = func
        self.interval_seconds = interval_seconds
        self.name = name or func.__name__
        self.task: asyncio.Task | None = None

    async def run(self) -> None:
        """Run the task periodically"""
        logger.debug(f'Starting {self.name!r} with {self.interval_seconds} second interval')
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

    def add_task(self, func: Callable[[], Any], interval_seconds: float, name: str | None = None) -> None:
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

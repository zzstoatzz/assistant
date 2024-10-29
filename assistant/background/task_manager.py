import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)


class BackgroundTaskManager:
    """Manages periodic background tasks from callable functions"""

    def __init__(self, tasks: Sequence[tuple[Callable[[], Any], float]]):
        """Initialize with sequence of (callable, interval_seconds) pairs"""
        self.tasks = tasks
        self._running_tasks: list[asyncio.Task] = []

    async def _run_periodic(self, func: Callable[[], Any], interval: float) -> None:
        """Run a function periodically with specified interval"""
        while True:
            try:
                await asyncio.get_event_loop().run_in_executor(None, func)
            except Exception as e:
                logger.error(f'Task {func.__name__} failed: {e}')
            await asyncio.sleep(interval)

    async def start_all(self) -> None:
        """Start all background tasks"""
        for func, interval in self.tasks:
            task = asyncio.create_task(self._run_periodic(func, interval))
            self._running_tasks.append(task)

    async def stop_all(self) -> None:
        """Stop all running tasks"""
        for task in self._running_tasks:
            task.cancel()

        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()

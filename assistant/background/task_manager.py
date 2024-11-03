import asyncio
from collections.abc import Callable, Sequence
from typing import ParamSpec, TypeVar

from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


class BackgroundTaskManager:
    """Manages periodic background tasks from callable functions"""

    def __init__(self, tasks: Sequence[tuple[Callable[P, T], float]]):
        """Initialize with sequence of (callable, interval_seconds) pairs"""
        self.tasks = tasks
        self._running_tasks: list[asyncio.Task] = []

    async def _run_periodic(self, func: Callable[P, T], interval: float) -> None:
        """Run a function periodically with specified interval"""
        while True:
            try:
                # Verify callable before execution
                if not callable(func):
                    raise TypeError(f'Task must be callable, got {type(func)}')

                await asyncio.get_event_loop().run_in_executor(None, func)
            except TypeError as e:
                logger.error(f'Task {func.__name__} has incorrect signature: {e}')
                raise  # Fail loudly on signature mismatch
            except Exception as e:
                logger.error(f'Task {func.__name__} failed: {e}')
            await asyncio.sleep(interval)

    async def start_all(self) -> None:
        """Start all background tasks"""
        for func, interval in self.tasks:
            # Verify callable before creating task
            if not callable(func):
                raise TypeError(f'Task must be callable, got {type(func)}')

            task = asyncio.create_task(self._run_periodic(func, interval))
            self._running_tasks.append(task)

    async def stop_all(self) -> None:
        """Stop all running tasks"""
        for task in self._running_tasks:
            task.cancel()

        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()

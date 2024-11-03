import asyncio
from collections.abc import Callable
from typing import TypeAlias

from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)

BackgroundFunc: TypeAlias = Callable[[], None]
TaskInterval: TypeAlias = float
InitialDelay: TypeAlias = float

TaskDef: TypeAlias = tuple[BackgroundFunc, TaskInterval] | tuple[BackgroundFunc, TaskInterval, InitialDelay]


async def _run_periodic(func: BackgroundFunc, interval: TaskInterval, delay: InitialDelay = 0) -> None:
    """Run a function periodically with optional initial delay"""
    if delay > 0:
        await asyncio.sleep(delay)

    while True:
        try:
            func()
        except Exception as e:
            logger.error(f'Error in background task {func.__name__}: {e}', exc_info=True)
        await asyncio.sleep(interval)


class BackgroundTaskManager:
    """Manages periodic background tasks with configurable intervals and delays"""

    def __init__(self, tasks: list[TaskDef]) -> None:
        self.running_tasks: list[asyncio.Task] = []
        self.task_defs = tasks

    async def start_all(self) -> None:
        """Start all defined background tasks"""
        for task_def in self.task_defs:
            func, interval, *delay = task_def
            coro = _run_periodic(func, interval, delay[0] if delay else 0)
            self.running_tasks.append(asyncio.create_task(coro))

    async def stop_all(self) -> None:
        """Stop all running tasks"""
        for task in self.running_tasks:
            task.cancel()
        self.running_tasks.clear()

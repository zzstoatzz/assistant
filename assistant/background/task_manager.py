from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, TypeAlias

from starlette.background import BackgroundTask

from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)

TaskInterval: TypeAlias = float
InitialDelay: TypeAlias = float
TaskDef: TypeAlias = tuple[BackgroundTask, TaskInterval] | tuple[BackgroundTask, TaskInterval, InitialDelay]


async def _run_periodic(task: BackgroundTask, interval: TaskInterval, delay: InitialDelay = 0) -> None:
    """Run a background task periodically with optional initial delay"""
    if delay > 0:
        await asyncio.sleep(delay)

    while True:
        try:
            await task()
        except Exception as e:
            logger.error(f'Error in background task: {e}', exc_info=True)
        await asyncio.sleep(interval)


class PeriodicTaskManager:
    """Manages periodic background tasks with configurable intervals and delays"""

    def __init__(self, tasks: Sequence[TaskDef]) -> None:
        self.running_tasks: list[asyncio.Task] = []
        self.task_defs = tasks

    async def start_all(self) -> None:
        """Start all defined background tasks"""
        for task_def in self.task_defs:
            task, interval, *delay = task_def
            coro = _run_periodic(task, interval, delay[0] if delay else 0)
            self.running_tasks.append(asyncio.create_task(coro))

    async def stop_all(self) -> None:
        """Stop all running tasks"""
        for task in self.running_tasks:
            task.cancel()
        self.running_tasks.clear()


def periodic_task(interval: float, delay: float = 0):
    """Decorator to create a periodic background task"""

    def decorator(func: Any) -> tuple[BackgroundTask, float, float]:
        return BackgroundTask(func), interval, delay

    return decorator

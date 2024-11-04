import asyncio
from collections import defaultdict
from time import time

from starlette.background import BackgroundTask

from assistant.background.task_manager import PeriodicTaskManager


def create_test_task(task_id: str, execution_times: defaultdict[str, list[float]]) -> BackgroundTask:
    """Creates a test task that records its execution times"""

    def task():
        execution_times[task_id].append(time())

    return BackgroundTask(task)


async def test_tasks_run_concurrently():
    """Test that multiple tasks can run concurrently without blocking each other"""
    execution_times = defaultdict(list)

    task1 = create_test_task('task1', execution_times)
    task2 = create_test_task('task2', execution_times)

    tasks = [
        (task1, 0.1),
        (task2, 0.2),
    ]

    manager = PeriodicTaskManager(tasks)
    await manager.start_all()
    await asyncio.sleep(0.5)
    await manager.stop_all()

    assert 4 <= len(execution_times['task1']) <= 6
    assert 2 <= len(execution_times['task2']) <= 3

    all_times = [(t, task_id) for task_id, times in execution_times.items() for t in times]
    all_times.sort()

    task_sequence = [task_id for _, task_id in all_times]
    assert len(set(task_sequence)) > 1, 'Tasks should interleave'


async def test_long_running_tasks_dont_block():
    """Test that long-running tasks don't block other tasks"""
    execution_times = defaultdict(list)

    async def long_task():
        execution_times['long'].append(time())
        await asyncio.sleep(0.3)

    def quick_task():
        execution_times['quick'].append(time())

    tasks = [
        (BackgroundTask(long_task), 0.2),
        (BackgroundTask(quick_task), 0.1),
    ]

    manager = PeriodicTaskManager(tasks)
    await manager.start_all()
    await asyncio.sleep(0.5)
    await manager.stop_all()

    assert 4 <= len(execution_times['quick']) <= 6
    assert 1 <= len(execution_times['long']) <= 3

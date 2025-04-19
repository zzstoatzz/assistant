from typing import Any, TypeVar

import marvin

T = TypeVar('T')


def run(
    objective: str,
    *,
    agents: list[marvin.Agent] | marvin.Agent,
    instructions: str,
    context: dict[str, Any],
    result_type: type[T] | None = None,
    **kwargs: Any,
) -> T:
    """Execute an AI task with given agents and context.

    Args:
        objective: Name/description of the task being performed
        agents: One or more agents to execute the task
        instructions: Detailed instructions for the agents
        context: Relevant context data for the task
        result_type: Expected return type (must be Pydantic model)
        **kwargs: additional framework-specific arguments
    Returns:
        The agent's response parsed into the specified type
    """
    if isinstance(agents, marvin.Agent):
        agents = [agents]

    return marvin.run(
        objective,
        agents=agents,
        context=context | {'instructions': instructions},
        result_type=result_type,
        **kwargs,
    )


async def run_async(
    objective: str,
    *,
    agents: list[marvin.Agent] | marvin.Agent,
    instructions: str,
    context: dict[str, Any],
    result_type: type[T] | None = None,
    **kwargs: Any,
) -> T:
    """Execute an AI task with given agents and context.

    Args:
        See `run`
    Returns:
        The agent's response parsed into the specified type
    """
    return await marvin.run_async(
        objective,
        agents=agents,
        context=context | {'instructions': instructions},
        result_type=result_type,
        **kwargs,
    )

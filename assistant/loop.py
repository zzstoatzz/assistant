from typing import Any, TypeVar

import controlflow as cf

T = TypeVar('T')


def run(
    objective: str,
    *,
    agents: list[cf.Agent] | cf.Agent,
    instructions: str,
    context: dict[str, Any],
    result_type: type[T] | None = None,
    **kwargs: Any,
) -> T:
    """Execute an AI task with given agents and context.

    Args:
        task: Name/description of the task being performed
        agents: One or more agents to execute the task
        instructions: Detailed instructions for the agents
        context: Relevant context data for the task
        result_type: Expected return type (must be Pydantic model)
        **kwargs: additional framework-specific arguments
    Returns:
        The agent's response parsed into the specified type
    """
    if isinstance(agents, cf.Agent):
        agents = [agents]

    return cf.run(
        objective=objective,
        agents=agents,
        instructions=instructions,
        context=context,
        result_type=result_type,
        **kwargs,
    )


async def run_async(
    objective: str,
    *,
    agents: list[cf.Agent] | cf.Agent,
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
    return await cf.run_async(
        objective=objective,
        agents=agents,
        instructions=instructions,
        context=context,
        result_type=result_type,
        **kwargs,
    )

from functools import partial

import controlflow as cf
from prefect import flow, task
from prefect.runtime.flow_run import get_parameters

from app.agents import ALL_AGENTS
from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, Entity, ObservationSummary
from assistant import run_agent_loop
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.background')


def _make_task_run_name(parameters: dict, verb: str) -> str:
    return f'{verb} using {" | ".join([a.name for a in parameters["agents"]])}'


@task(task_run_name=partial(_make_task_run_name, verb='process raw summaries'))
def process_raw_summaries(storage: DiskStorage, agents: list[cf.Agent]) -> list[ObservationSummary]:
    """Process raw summaries and detect entities"""
    processed = []

    for path in storage.get_unprocessed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())

            entities = run_agent_loop(
                'Analyze observation for entities',
                agents=agents,
                instructions="""
                Review this observation and:
                1. Identify any key entities
                2. Reconcile with existing entities
                3. For each entity:
                   - Set importance based on current context
                   - Write clear description of current state
                   - Link to related entities if any
                Return list of entities to track.
                """,
                context={
                    'observation': summary.model_dump(),
                    'entities': storage.get_entities(),
                },
                result_type=list[Entity],
            )

            for entity in entities:
                storage.store_entity(entity)

            # Add entity references to summary
            summary.entity_mentions = [e.id for e in entities]
            storage.store_processed(summary)
            processed.append(summary)

            # Move raw to processed
            path.rename(storage.processed_dir / path.name)

        except Exception as e:
            logger.error(f'Failed to process summary {path}: {e}')

    return processed


@task(task_run_name=partial(_make_task_run_name, verb='update historical pins'))
def update_historical_pins(
    storage: DiskStorage,
    agents: list[cf.Agent],
    recent_summaries: list[ObservationSummary],
) -> None:
    """Update historical pins based on recent activity and entities"""
    # Get active entities for context
    entities = storage.get_entities()

    # Let secretary evaluate historical significance
    pin: CompactedSummary = run_agent_loop(
        'Evaluate historical significance',
        agents=agents,
        instructions="""
        Review recent observations and active entities to determine:
        1. What deserves historical preservation
        2. How this connects to existing knowledge
        3. What patterns or trends are emerging

        If nothing significant to pin, return a CompactedSummary with empty=True.
        """,
        context={
            'recent_summaries': [s.model_dump() for s in recent_summaries],
            'active_entities': [e.model_dump() for e in entities],
            'user_identity': settings.user_identity,
        },
        result_type=CompactedSummary,
    )

    if not pin.empty:
        storage.store_compact(pin)
        logger.info('Created new historical pin')
    else:
        logger.info('No significant events to pin')


@task(task_run_name=partial(_make_task_run_name, verb='check alerts'))
def check_agent_alerts(
    recent_summaries: list[ObservationSummary],
    entities: list[Entity],
) -> None:
    """Have all agents assess if they should alert about anything"""
    logger.info('Checking to see if anything requires human attention')
    run_agent_loop(
        'Assess if human should be alerted',
        agents=ALL_AGENTS,
        instructions="""
        Review recent observations and entities from your domain expertise.
        Determine if there's anything the human should be alerted about.

        Consider:
        1. Urgency and importance
        2. Your specific domain knowledge
        3. Patterns you've observed
        4. The human's preferences and identity

        If you need to alert the human, use your tools to do so.
        """,
        context={
            'recent_summaries': [s.model_dump() for s in recent_summaries],
            'active_entities': [e.model_dump() for e in entities],
            'user_identity': settings.user_identity,
        },
    )


def _make_flow_run_name_from_agents() -> str:
    agents = get_parameters()['agents']
    return f'Employing {", ".join([a.name for a in agents])!r} to compress observations'


@flow(flow_run_name=_make_flow_run_name_from_agents)
def compress_observations(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process observations and maintain historical context"""
    logger.info('🔄 Starting observation compression')

    if recent := process_raw_summaries(storage, agents):
        logger.info(f'Processed {len(recent)} new summaries')

        check_agent_alerts(recent, storage.get_entities())

        update_historical_pins(storage, agents, recent)

    else:
        logger.info('No new observations to process')

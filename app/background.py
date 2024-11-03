from functools import partial

import controlflow as cf
from prefect import flow, task
from prefect.cache_policies import NONE
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

    for path in sorted(storage.get_unprocessed())[-settings.max_unprocessed_batch_size :]:
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())

            existing_entities = sorted(storage.get_entities(), key=lambda e: e.importance, reverse=True)[
                : settings.max_context_entities
            ]

            entities = run_agent_loop(
                'Analyze observation for entities',
                agents=agents,
                instructions=f"""
                Review this observation and identify/update key entities.

                Guidelines:
                1. Focus on important entities (importance > {settings.entity_importance_threshold})
                2. Merge similar or related entities
                3. Keep entity descriptions concise but informative

                Return only entities worth tracking long-term.
                """,
                context={
                    'observation': summary.model_dump(),
                    'entities': [e.model_dump() for e in existing_entities],
                },
                result_type=list[Entity],
            )

            # Store only significant entities
            for entity in entities:
                if entity.importance > settings.entity_importance_threshold:
                    storage.store_entity(entity)

            summary.entity_mentions = [e.id for e in entities]
            storage.store_processed(summary)
            processed.append(summary)
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
    # Get only high-importance entities
    entities = [e for e in storage.get_entities() if e.importance > settings.context_entity_threshold]
    compacted = [CompactedSummary.model_validate_json(p.read_text()) for p in storage.get_compact()]
    # Get recent pins using configured limit
    existing_pins = sorted(
        compacted,
        key=lambda p: p.importance_score,
        reverse=True,
    )[: settings.max_historical_pins]

    pin: CompactedSummary = run_agent_loop(
        'Evaluate historical significance',
        agents=agents,
        instructions=f"""
        Review recent observations and determine historical significance.

        Guidelines:
        1. Focus on significant events (importance > {settings.historical_pin_threshold})
        2. Consolidate related historical events
        3. Update existing pins if topics overlap
        4. Keep summaries concise but informative

        Return CompactedSummary with empty=True if nothing warrants preservation.
        """,
        context={
            'recent_summaries': [s.model_dump() for s in recent_summaries],
            'active_entities': [e.model_dump() for e in entities],
            'existing_pins': [p.model_dump() for p in existing_pins],
            'user_identity': settings.user_identity,
        },
        result_type=CompactedSummary,
    )

    if not pin.empty and pin.importance_score > settings.historical_pin_threshold:
        storage.store_compact(pin)
        logger.info('Created new historical pin')
    else:
        logger.info('No significant events to pin')


@task(cache_policy=NONE)
def check_for_humanworthy_events(
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

        check_for_humanworthy_events(recent, storage.get_entities())

        update_historical_pins(storage, agents, recent)

    else:
        logger.info('No new observations to process')

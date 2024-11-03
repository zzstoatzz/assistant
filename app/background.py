import controlflow as cf
from prefect import flow, task

from app.settings import settings
from app.storage import DiskStorage
from app.types import CompactedSummary, Entity, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger('assistant.background')


@task
def process_raw_summaries(storage: DiskStorage, agents: list[cf.Agent]) -> list[ObservationSummary]:
    """Process raw summaries and detect entities"""
    processed = []

    for path in storage.get_unprocessed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())

            # Detect/update entities from this summary
            entities = cf.run(
                'Analyze observation for entities',
                agents=agents,
                instructions="""
                Review this observation and:
                1. Identify key entities (users, repos, topics)
                2. For each entity:
                   - Set importance based on current context
                   - Write clear description of current state
                   - Link to related entities if any
                Return list of entities to track.
                """,
                context={'observation': summary.model_dump()},
                result_type=list[Entity],
            )

            # Store/update entities
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


@task
def update_historical_pins(
    storage: DiskStorage,
    agents: list[cf.Agent],
    recent_summaries: list[ObservationSummary],
) -> None:
    """Update historical pins based on recent activity and entities"""

    # Get active entities for context
    entities = storage.get_entities()

    # Let secretary evaluate historical significance
    pin = cf.run(
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


@flow
def compress_observations(storage: DiskStorage, agents: list[cf.Agent]) -> None:
    """Process observations and maintain historical context"""
    logger.info('🔄 Starting observation compression')

    # 1. Process any raw summaries
    if recent := process_raw_summaries(storage, agents):
        logger.info(f'Processed {len(recent)} new summaries')

        # 2. Update historical pins with new context
        update_historical_pins(storage, agents, recent)
    else:
        logger.info('No new observations to process')

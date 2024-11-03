from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.settings import settings
from app.storage import DiskStorage
from app.types import Entity, ObservationSummary
from assistant.utilities.loggers import get_logger

router = APIRouter(prefix='/api')
storage = DiskStorage(settings.app_dir)
logger = get_logger('app.api.entities')


# Request Models
class EntityUpdate(BaseModel):
    description: str | None = None
    importance: float | None = None


# Entity CRUD
@router.get('/entities')
async def list_entities(
    source: str | None = None, min_importance: Annotated[float | None, Query(ge=0, le=1)] = None
) -> list[Entity]:
    """Get all entities, optionally filtered"""
    entities = storage.get_entities()

    if source:
        entities = [e for e in entities if e.source == source]
    if min_importance is not None:
        entities = [e for e in entities if e.importance >= min_importance]

    return sorted(entities, key=lambda e: e.importance, reverse=True)


@router.get('/entities/{entity_id}')
async def get_entity(entity_id: str) -> Entity:
    """Get entity by ID"""
    if entity := storage.get_entity(entity_id):
        return entity
    raise HTTPException(status_code=404, detail='Entity not found')


@router.patch('/entities/{entity_id}')
async def update_entity(entity_id: str, update: EntityUpdate) -> Entity:
    """Update entity fields"""
    if entity := storage.get_entity(entity_id):
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        entity.last_updated = datetime.now(settings.tz)
        storage.store_entity(entity)
        return entity
    raise HTTPException(status_code=404, detail='Entity not found')


@router.delete('/entities/{entity_id}')
async def delete_entity(entity_id: str) -> dict[str, str]:
    """Delete entity"""
    if storage.delete_entity(entity_id):
        return {'status': 'deleted'}
    raise HTTPException(status_code=404, detail='Entity not found')


# Summary CRUD
@router.get('/summaries')
async def list_summaries(
    hours: Annotated[int, Query(ge=1)] = 24, consolidate: bool = False, window_minutes: Annotated[int, Query(ge=1)] = 15
) -> list[ObservationSummary]:
    """
    Get recent summaries

    - hours: How far back to look
    - consolidate: Whether to group nearby events
    - window_minutes: Time window for consolidation
    """
    cutoff = datetime.now(settings.tz) - timedelta(hours=hours)
    summaries = []

    for path in storage.get_processed():
        try:
            summary = ObservationSummary.model_validate_json(path.read_text())
            if summary.timestamp >= cutoff:
                summaries.append(summary)
        except Exception as e:
            logger.error(f'Failed to load summary {path}: {e}')

    if not consolidate:
        return sorted(summaries, key=lambda s: s.timestamp, reverse=True)

    # Group summaries by time windows
    consolidated = []
    window_delta = timedelta(minutes=window_minutes)

    summaries.sort(key=lambda s: s.timestamp)
    current_window = []

    for summary in summaries:
        if not current_window or (summary.timestamp - current_window[0].timestamp) <= window_delta:
            current_window.append(summary)
        else:
            # Consolidate window
            consolidated.append(
                ObservationSummary(
                    timestamp=current_window[0].timestamp,
                    summary='\n\n'.join(s.summary for s in current_window),
                    events=[e for s in current_window for e in s.events],
                    source_types=list(set(st for s in current_window for st in s.source_types)),
                    entity_mentions=list(set(em for s in current_window for em in s.entity_mentions)),
                )
            )
            current_window = [summary]

    # Handle last window
    if current_window:
        consolidated.append(
            ObservationSummary(
                timestamp=current_window[0].timestamp,
                summary='\n\n'.join(s.summary for s in current_window),
                events=[e for s in current_window for e in s.events],
                source_types=list(set(st for s in current_window for st in s.source_types)),
                entity_mentions=list(set(em for s in current_window for em in s.entity_mentions)),
            )
        )

    return sorted(consolidated, key=lambda s: s.timestamp, reverse=True)

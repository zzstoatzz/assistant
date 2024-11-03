from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from app.settings import settings
from app.types import CompactedSummary, Entity, ObservationSummary
from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)


def _get_timestamped_path(directory: Path, prefix: str) -> Path:
    """Get a timestamped path using consistent timezone"""
    timestamp = datetime.now(settings.tz).strftime('%Y%m%d_%H%M%S')
    return directory / f'{prefix}_{timestamp}.json'


def _safe_write(path: Path, data: BaseModel) -> Path:
    """Safely write data to path"""
    path.write_text(data.model_dump_json(indent=2))
    return path


class DiskStorage:
    """Storage for observations, summaries, and entities"""

    def __init__(self) -> None:
        """Initialize storage using paths from settings"""
        storage = settings.paths.storage
        self.raw_dir = storage.raw
        self.processed_dir = storage.processed
        self.compact_dir = storage.compact
        self.entities_dir = storage.entities

    # Raw observations
    def store_raw(self, data: ObservationSummary) -> Path:
        """Store raw observation data"""
        path = _get_timestamped_path(self.raw_dir, 'raw')
        return _safe_write(path, data)

    def get_unprocessed(self) -> Iterator[Path]:
        """Get paths of unprocessed observations"""
        return self.raw_dir.glob('raw_*.json')

    # Processed summaries
    def store_processed(self, data: ObservationSummary) -> Path:
        """Store processed summary data"""
        path = _get_timestamped_path(self.processed_dir, 'summary')
        return _safe_write(path, data)

    def get_processed(self) -> Iterator[Path]:
        """Get paths of processed summaries"""
        return self.processed_dir.glob('summary_*.json')

    # Compact summaries
    def store_compact(self, data: CompactedSummary) -> Path:
        """Store compacted summary data"""
        path = _get_timestamped_path(self.compact_dir, 'compact')
        return _safe_write(path, data)

    def get_compact(self) -> Iterator[Path]:
        """Get paths of compact summaries"""
        return self.compact_dir.glob('compact_*.json')

    # Entity operations
    def store_entity(self, entity: Entity) -> Path:
        """Store an entity"""
        path = self.entities_dir / f'{entity.id}.json'
        return _safe_write(path, entity)

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID"""
        path = self.entities_dir / f'{entity_id}.json'
        if not path.exists():
            return None
        try:
            return Entity.model_validate_json(path.read_text())
        except Exception as e:
            logger.error(f'Failed to load entity {path}: {e}')
            return None

    def get_entities(self) -> list[Entity]:
        """Get all entities"""
        entities = []
        for path in self.entities_dir.glob('*.json'):
            try:
                entities.append(Entity.model_validate_json(path.read_text()))
            except Exception as e:
                logger.error(f'Failed to load entity {path}: {e}')
        return entities

    def delete_entity(self, entity_id: str) -> bool:
        """Delete entity by ID"""
        path = self.entities_dir / f'{entity_id}.json'
        if path.exists():
            path.unlink()
            return True
        return False

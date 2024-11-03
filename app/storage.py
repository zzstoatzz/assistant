from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.settings import settings
from app.types import Entity
from assistant.utilities.loggers import get_logger

logger = get_logger(__name__)

M = TypeVar('M', bound=BaseModel)


def _get_timestamped_path(directory: Path, prefix: str) -> Path:
    """Get a timestamped path using consistent timezone"""
    timestamp = datetime.now(settings.tz).strftime('%Y%m%d_%H%M%S')
    return directory / f'{prefix}_{timestamp}.json'


def _safe_write(path: Path, data: BaseModel) -> Path:
    """Safely write data to path, creating parent dirs if needed"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2))
    return path


class DiskStorage(Generic[M]):
    """Simple disk-based storage for observations and summaries"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.raw_dir = base_dir / 'raw'
        self.processed_dir = base_dir / 'processed'
        self.compact_dir = base_dir / 'compact'
        self.entities_dir = base_dir / 'entities'

    def store_raw(self, data: M) -> Path:
        """Store raw observation data"""
        path = _get_timestamped_path(self.raw_dir, 'raw')
        return _safe_write(path, data)

    def store_processed(self, data: M) -> Path:
        """Store processed summary data"""
        path = _get_timestamped_path(self.processed_dir, 'summary')
        return _safe_write(path, data)

    def store_compact(self, data: M) -> Path:
        """Store compacted summary data"""
        path = _get_timestamped_path(self.compact_dir, 'compact')
        return _safe_write(path, data)

    def store_entity(self, entity: Entity) -> Path:
        """Store an entity"""
        path = self.entities_dir / f'{entity.id}.json'
        return _safe_write(path, entity)

    def get_unprocessed(self) -> Iterator[Path]:
        """Get paths of unprocessed observations"""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        return self.raw_dir.glob('raw_*.json')

    def get_processed(self) -> Iterator[Path]:
        """Get paths of processed summaries"""
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        return self.processed_dir.glob('summary_*.json')

    def get_compact(self) -> Iterator[Path]:
        """Get paths of compact summaries"""
        self.compact_dir.mkdir(parents=True, exist_ok=True)
        return self.compact_dir.glob('compact_*.json')

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
        self.entities_dir.mkdir(parents=True, exist_ok=True)
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

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

M = TypeVar('M', bound=BaseModel)


class DiskStorage(Generic[M]):
    """Simple disk-based storage for observations and summaries"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.raw_dir = base_dir / 'raw'
        self.processed_dir = base_dir / 'processed'
        self.compact_dir = base_dir / 'compact'

        # Ensure directories exist
        for dir in [self.raw_dir, self.processed_dir, self.compact_dir]:
            dir.mkdir(parents=True, exist_ok=True)

    def store_raw(self, data: M) -> Path:
        """Store raw observation data"""
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        path = self.raw_dir / f'raw_{timestamp}.json'
        path.write_text(data.model_dump_json(indent=2))
        return path

    def store_processed(self, data: M) -> Path:
        """Store processed summary data"""
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        path = self.processed_dir / f'summary_{timestamp}.json'
        path.write_text(data.model_dump_json(indent=2))
        return path

    def store_compact(self, data: M) -> Path:
        """Store compacted summary data"""
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        path = self.compact_dir / f'compact_{timestamp}.json'
        path.write_text(data.model_dump_json(indent=2))
        return path

    def get_unprocessed(self) -> Iterator[Path]:
        """Get paths of unprocessed observations"""
        return self.raw_dir.glob('raw_*.json')

    def get_processed(self) -> Iterator[Path]:
        """Get paths of processed summaries"""
        return self.processed_dir.glob('summary_*.json')

    def get_compact(self) -> Iterator[Path]:
        """Get paths of compact summaries"""
        return self.compact_dir.glob('compact_*.json')

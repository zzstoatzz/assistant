"""SQLite-based storage implementation for observations, summaries, and entities."""

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, String, create_engine, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from app.settings import settings
from app.types import CompactedSummary, Entity, ObservationSummary

Base = declarative_base()


class RawObservation(Base):
    """Raw observation data stored in SQLite."""

    __tablename__ = "raw_observations"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    data = Column(JSON, nullable=False)


class ProcessedSummary(Base):
    """Processed summary data stored in SQLite."""

    __tablename__ = "processed_summaries"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    data = Column(JSON, nullable=False)


class CompactSummary(Base):
    """Compacted summary data stored in SQLite."""

    __tablename__ = "compact_summaries"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    data = Column(JSON, nullable=False)


class StoredEntity(Base):
    """Entity data stored in SQLite."""

    __tablename__ = "entities"

    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)


class SQLiteStorage:
    """Storage for observations, summaries, and entities using SQLite."""

    def __init__(self) -> None:
        """Initialize storage using paths from settings."""
        db_path = settings.paths.storage.root / "storage.db"
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)

    def _get_session(self) -> Session:
        """Get a new database session."""
        return Session(self.engine)

    def store_raw(self, data: ObservationSummary) -> Path:
        """Store raw observation data."""
        timestamp = datetime.now(settings.tz)
        raw = RawObservation(
            id=timestamp.strftime("%Y%m%d_%H%M%S"),
            timestamp=timestamp,
            data=data.model_dump(),
        )
        with self._get_session() as session:
            session.add(raw)
            session.commit()
        return Path(str(raw.id))

    def get_unprocessed(self) -> Iterator[Path]:
        """Get paths of unprocessed observations."""
        with self._get_session() as session:
            stmt = select(RawObservation).order_by(RawObservation.timestamp)
            for raw in session.execute(stmt).scalars():
                yield Path(str(raw.id))

    def store_processed(self, data: ObservationSummary) -> Path:
        """Store processed summary data."""
        timestamp = datetime.now(settings.tz)
        summary = ProcessedSummary(
            id=timestamp.strftime("%Y%m%d_%H%M%S"),
            timestamp=timestamp,
            data=data.model_dump(),
        )
        with self._get_session() as session:
            session.add(summary)
            session.commit()
        return Path(str(summary.id))

    def get_processed(self) -> Iterator[Path]:
        """Get paths of processed summaries."""
        with self._get_session() as session:
            stmt = select(ProcessedSummary).order_by(ProcessedSummary.timestamp)
            for summary in session.execute(stmt).scalars():
                yield Path(str(summary.id))

    def store_compact(self, data: CompactedSummary) -> Path:
        """Store compacted summary data."""
        timestamp = datetime.now(settings.tz)
        summary = CompactSummary(
            id=timestamp.strftime("%Y%m%d_%H%M%S"),
            timestamp=timestamp,
            data=data.model_dump(),
        )
        with self._get_session() as session:
            session.add(summary)
            session.commit()
        return Path(str(summary.id))

    def get_compact(self) -> Iterator[Path]:
        """Get paths of compact summaries."""
        with self._get_session() as session:
            stmt = select(CompactSummary).order_by(CompactSummary.timestamp)
            for summary in session.execute(stmt).scalars():
                yield Path(str(summary.id))

    def store_entity(self, entity: Entity) -> Path:
        """Store an entity."""
        stored = StoredEntity(
            id=entity.id,
            data=entity.model_dump(),
        )
        with self._get_session() as session:
            session.merge(stored)
            session.commit()
        return Path(str(stored.id))

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        with self._get_session() as session:
            stored = session.get(StoredEntity, entity_id)
            if stored is None:
                return None
            return Entity.model_validate(stored.data)

    def get_entities(self) -> list[Entity]:
        """Get all entities."""
        entities = []
        with self._get_session() as session:
            stmt = select(StoredEntity)
            for stored in session.execute(stmt).scalars():
                try:
                    entities.append(Entity.model_validate(stored.data))
                except Exception as e:
                    logger.error(f"Failed to load entity {stored.id}: {e}")
        return entities

    def delete_entity(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        with self._get_session() as session:
            stored = session.get(StoredEntity, entity_id)
            if stored is None:
                return False
            session.delete(stored)
            session.commit()
            return True
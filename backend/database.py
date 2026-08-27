"""
database.py — SQLAlchemy async models and session management.
"""
import uuid
import enum
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings


# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------

def _make_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs = {}
    if url.startswith("sqlite"):
        # Enable WAL mode for SQLite concurrent reads
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(url, echo=False, **kwargs)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    C2PA = "c2pa"
    AUDIO = "audio"
    VISION = "vision"
    OSINT = "osint"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(SAEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    source_type = Column(String(10), nullable=False)   # "url" | "file"
    source_url = Column(Text, nullable=True)            # original URL if applicable
    original_filename = Column(Text, nullable=True)     # uploaded filename
    video_path = Column(Text, nullable=True)            # abs path on disk
    audio_path = Column(Text, nullable=True)
    user_claim = Column(Text, nullable=True)            # user caption/claim text for OSINT context checks
    virality_speed = Column(Text, nullable=True)        # virality velocity metric
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)           # full verdict JSON string
    telegram_chat_id = Column(String(100), nullable=True) # chat ID of user who requested via bot
    # ── Blockchain Provenance ────────────────────────────────────────────────
    sha256_hash = Column(String(64),  nullable=True)  # Hex SHA-256 of raw video bytes
    perceptual_hash = Column(String(64), nullable=True)  # imagehash pHash fingerprint
    ipfs_cid = Column(String(100),    nullable=True)  # IPFS CID of pinned report JSON
    tx_hash = Column(String(100),     nullable=True)  # On-chain transaction hash
    on_chain_status = Column(String(20), nullable=True)  # "sealed" | "off_chain" | "pending"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class OsintCache(Base):
    """Persistent OSINT reverse-image-search result cache, keyed by source URL."""
    __tablename__ = "osint_cache"

    url_hash    = Column(String(16), primary_key=True)   # first 16 hex chars of SHA-256(source_url)
    source_url  = Column(Text, nullable=False)
    result_json = Column(Text, nullable=False)            # JSON-serialised list of OsintMatch dicts
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

async def init_db():
    """Create all tables if they don't exist and ensure missing columns are added."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQLite schema auto-migration for newly added model columns
        def _sync_schema(sync_conn):
            from sqlalchemy import inspect
            inspector = inspect(sync_conn)
            if "jobs" in inspector.get_table_names():
                columns = {col["name"] for col in inspector.get_columns("jobs")}
                expected_columns = {
                    "user_claim": "TEXT",
                    "virality_speed": "TEXT",
                    "telegram_chat_id": "VARCHAR(100)",
                    "sha256_hash": "VARCHAR(64)",
                    "perceptual_hash": "VARCHAR(64)",
                    "ipfs_cid": "VARCHAR(100)",
                    "tx_hash": "VARCHAR(100)",
                    "on_chain_status": "VARCHAR(20)",
                }
                for col_name, col_type in expected_columns.items():
                    if col_name not in columns:
                        sync_conn.execute(
                            __import__("sqlalchemy").text(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
                        )

        await conn.run_sync(_sync_schema)
        # Create OsintCache table if not already present
        await conn.run_sync(Base.metadata.create_all)

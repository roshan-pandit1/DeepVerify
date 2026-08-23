"""
database.py — SQLAlchemy async models and session management.
"""
import uuid
import enum
from datetime import datetime
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
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)           # full verdict JSON string
    telegram_chat_id = Column(String(100), nullable=True) # chat ID of user who requested via bot
    # ── Blockchain Provenance ────────────────────────────────────────────────
    sha256_hash = Column(String(64),  nullable=True)  # Hex SHA-256 of raw video bytes
    perceptual_hash = Column(String(64), nullable=True)  # imagehash pHash fingerprint
    ipfs_cid = Column(String(100),    nullable=True)  # IPFS CID of pinned report JSON
    tx_hash = Column(String(100),     nullable=True)  # On-chain transaction hash
    on_chain_status = Column(String(20), nullable=True)  # "sealed" | "off_chain" | "pending"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

"""
database.py — SQLAlchemy async models and session management for DeepVerify.
"""
import uuid
import enum
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    Integer,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config import get_settings


# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------

def _make_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs = {}
    if url.startswith("sqlite"):
        # Enable WAL mode and multi-thread connection sharing for SQLite
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(url, echo=False, **kwargs)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Base & Enums
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class ClaimInputType(str, enum.Enum):
    TEXT = "text"
    URL = "url"
    MEDIA = "media"


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    EXTRACTED = "extracted"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceStance(str, enum.Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class VerdictType(str, enum.Enum):
    VERIFIED = "Verified"
    UNCERTAIN = "Uncertain"
    UNSUPPORTED = "Unsupported"
    CONTESTED = "Contested"


# ---------------------------------------------------------------------------
# Core Narrative Verification Engine Models
# ---------------------------------------------------------------------------

class Claim(Base):
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_input = Column(Text, nullable=False)
    input_type = Column(SAEnum(ClaimInputType), nullable=False, default=ClaimInputType.TEXT)
    normalized_text = Column(Text, nullable=True)
    status = Column(SAEnum(ClaimStatus), nullable=False, default=ClaimStatus.SUBMITTED)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    assertions = relationship("Assertion", back_populates="claim", cascade="all, delete-orphan")
    verification_result = relationship("VerificationResult", back_populates="claim", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogEntry", back_populates="claim", cascade="all, delete-orphan")


class Assertion(Base):
    __tablename__ = "assertions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    assertion_text = Column(Text, nullable=False)
    entity_names_json = Column(Text, nullable=True, default="[]")
    confidence_weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    claim = relationship("Claim", back_populates="assertions")
    evidence_items = relationship("EvidenceItem", back_populates="assertion", cascade="all, delete-orphan")


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assertion_id = Column(String(36), ForeignKey("assertions.id", ondelete="CASCADE"), nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(String(2048), nullable=True)
    content_snippet = Column(Text, nullable=False)
    stance = Column(SAEnum(EvidenceStance), nullable=False, default=EvidenceStance.NEUTRAL)
    credibility_score = Column(Float, nullable=False, default=0.5)
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    assertion = relationship("Assertion", back_populates="evidence_items")


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), unique=True, nullable=False)
    verdict = Column(SAEnum(VerdictType), nullable=False, default=VerdictType.UNCERTAIN)
    confidence_score = Column(Float, nullable=False, default=0.0)
    summary_explanation = Column(Text, nullable=False)
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    claim = relationship("Claim", back_populates="verification_result")


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    stage_name = Column(String(100), nullable=False)
    input_summary = Column(Text, nullable=False)
    output_summary = Column(Text, nullable=False)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    claim = relationship("Claim", back_populates="audit_logs")


# ---------------------------------------------------------------------------
# Legacy Job & OsintCache Models (Preserved for compatibility)
# ---------------------------------------------------------------------------

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
    source_type = Column(String(10), nullable=False)
    source_url = Column(Text, nullable=True)
    original_filename = Column(Text, nullable=True)
    video_path = Column(Text, nullable=True)
    audio_path = Column(Text, nullable=True)
    user_claim = Column(Text, nullable=True)
    virality_speed = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    perceptual_hash = Column(String(64), nullable=True)
    ipfs_cid = Column(String(100), nullable=True)
    tx_hash = Column(String(100), nullable=True)
    on_chain_status = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class OsintCache(Base):
    __tablename__ = "osint_cache"

    url_hash = Column(String(16), primary_key=True)
    source_url = Column(Text, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# DB Init & Auto Migration
# ---------------------------------------------------------------------------

async def init_db():
    """Create all tables if they don't exist and ensure schema is up to date."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

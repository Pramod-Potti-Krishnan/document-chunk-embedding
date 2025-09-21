from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean,
    ForeignKey, JSON, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255))
    full_name = Column(String(255))
    organization = Column(String(255))
    role = Column(String(50), default="user")

    # Quotas
    storage_quota_mb = Column(Integer, default=5000)
    storage_used_mb = Column(Float, default=0.0)
    documents_quota = Column(Integer, default=10000)
    documents_count = Column(Integer, default=0)
    api_calls_quota = Column(Integer, default=100000)
    api_calls_count = Column(Integer, default=0)

    # Settings
    preferences = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_activity = Column(DateTime(timezone=True))

    # Relationships
    sessions = relationship("UserSession", back_populates="profile", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="profile", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), ForeignKey("profiles.user_id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(255), nullable=False)
    project_id = Column(String(255), default="-")

    # Session metadata
    session_name = Column(String(255))
    session_type = Column(String(50))
    session_metadata = Column("metadata", JSONB, default={})
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_accessed = Column(DateTime(timezone=True))

    # Relationships
    profile = relationship("Profile", back_populates="sessions")
    documents = relationship("Document", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_user_session_project", "user_id", "session_id", "project_id"),
        UniqueConstraint("user_id", "session_id", "project_id", name="uq_user_session_project"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), ForeignKey("profiles.user_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), default="-", index=True)
    user_session_id = Column(UUID(as_uuid=True), ForeignKey("user_sessions.id", ondelete="CASCADE"))

    # Document metadata
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64))
    mime_type = Column(String(100))

    # Processing status
    status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_error = Column(Text)
    processing_attempts = Column(Integer, default=0)

    # Extracted content
    total_pages = Column(Integer)
    total_chunks = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    language = Column(String(10))

    # Storage
    storage_path = Column(String(500))
    storage_url = Column(String(1000))

    # Metadata
    doc_metadata = Column("metadata", JSONB, default={})
    tags = Column(ARRAY(String), default=[])

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    profile = relationship("Profile", back_populates="documents")
    session = relationship("UserSession", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_document_hierarchy", "user_id", "session_id", "project_id"),
        Index("idx_document_status", "status", "created_at"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="check_document_status"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    project_id = Column(String(255), default="-", index=True)

    # Chunk content
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    token_count = Column(Integer)

    # Chunk metadata
    page_number = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    overlap_start = Column(Integer)
    overlap_end = Column(Integer)

    # Embedding
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small dimension
    embedding_model = Column(String(100))
    embedding_created_at = Column(DateTime(timezone=True))

    # Metadata
    chunk_metadata = Column("metadata", JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")

    # Indexes
    __table_args__ = (
        Index("idx_chunk_hierarchy", "user_id", "session_id", "project_id"),
        Index("idx_chunk_document", "document_id", "chunk_index"),
        Index("idx_chunk_embedding", "embedding", postgresql_using="ivfflat", postgresql_ops={"embedding": "vector_cosine_ops"}),
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)

    # Job details
    job_type = Column(String(50), nullable=False)  # processing, extraction, chunking, embedding
    status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed, cancelled
    priority = Column(Integer, default=5)

    # Progress tracking
    progress_percentage = Column(Integer, default=0)
    progress_message = Column(Text)

    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    processing_time_seconds = Column(Float)

    # Error handling
    error_message = Column(Text)
    error_details = Column(JSONB)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Results
    result = Column(JSONB)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    document = relationship("Document", back_populates="processing_jobs")

    # Indexes
    __table_args__ = (
        Index("idx_job_status", "status", "created_at"),
        Index("idx_job_user", "user_id", "status"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", name="check_job_status"),
    )


class ProcessingStats(Base):
    __tablename__ = "processing_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)

    # Daily statistics
    documents_processed = Column(Integer, default=0)
    documents_failed = Column(Integer, default=0)
    total_chunks_created = Column(Integer, default=0)
    total_embeddings_created = Column(Integer, default=0)
    total_bytes_processed = Column(Integer, default=0)

    # Performance metrics
    avg_processing_time_seconds = Column(Float)
    max_processing_time_seconds = Column(Float)
    min_processing_time_seconds = Column(Float)

    # API usage
    api_calls_count = Column(Integer, default=0)
    embedding_api_calls = Column(Integer, default=0)

    # Costs (if applicable)
    estimated_cost_usd = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Indexes
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date_stats"),
        Index("idx_stats_user_date", "user_id", "date"),
    )
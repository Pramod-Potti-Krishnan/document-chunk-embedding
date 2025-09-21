from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    EXTRACTION = "extraction"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


# Request Models
class DocumentUploadRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255, description="User identifier")
    session_id: str = Field(..., min_length=1, max_length=255, description="Session identifier")
    project_id: Optional[str] = Field(default="-", max_length=255, description="Project identifier")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")
    tags: Optional[List[str]] = Field(default=[], description="Document tags")

    @validator("project_id")
    def validate_project_id(cls, v):
        return v if v else "-"


class DocumentListRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    session_id: Optional[str] = Field(None, min_length=1, max_length=255)
    project_id: Optional[str] = Field(None, max_length=255)
    status: Optional[DocumentStatus] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str = Field(default="created_at", pattern="^(created_at|updated_at|filename)$")
    order_desc: bool = Field(default=True)


class ChunkListRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    include_embeddings: bool = Field(default=False)


# Response Models
class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    mime_type: Optional[str] = None
    total_pages: Optional[int] = None
    total_chunks: int = 0
    total_tokens: int = 0
    language: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


class DocumentStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    session_id: str
    project_id: str
    filename: str
    file_type: str
    status: str
    progress_percentage: int = 0
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    session_id: str
    project_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    total_pages: Optional[int] = None
    total_chunks: int = 0
    total_tokens: int = 0
    storage_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias='doc_metadata')
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chunk_index: int
    text_content: str
    chunk_size: int
    token_count: Optional[int] = None
    page_number: Optional[int] = None
    start_char: int
    end_char: int
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime


class ChunkListResponse(BaseModel):
    chunks: List[ChunkResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    job_type: str
    celery_task_id: Optional[str] = None
    status: str
    progress_percentage: int = 0
    progress_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime


class UploadResponse(BaseModel):
    document_id: UUID
    status: str
    message: str
    processing_job_id: Optional[UUID] = None
    estimated_processing_time: Optional[int] = None  # in seconds


class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_chunks: int = 0


class ErrorResponse(BaseModel):
    error: str
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    services: Dict[str, bool]
    metrics: Dict[str, Any] = {}  # Additional metrics (non-boolean values)
    uptime_seconds: float
    timestamp: datetime


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    type: str


class ValidationErrorResponse(BaseModel):
    error: str = "validation_error"
    message: str = "Request validation failed"
    details: List[ValidationErrorDetail]
    correlation_id: Optional[str] = None
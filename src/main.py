from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import logging
import asyncio
from pathlib import Path

from src.config.settings import settings
from src.core.database import init_database, get_db

# Patch auth BEFORE importing auth functions if in test mode
if os.getenv('TESTING_MODE', 'false').lower() == 'true':
    from src.core.auth_dev import patch_auth_for_development
    patch_auth_for_development()

from src.core.auth import get_current_user, check_rate_limit, PermissionChecker
from src.models.schemas import (
    DocumentUploadRequest, DocumentListRequest, DocumentListResponse,
    DocumentResponse, DocumentStatus, UploadResponse, DeleteResponse,
    ErrorResponse, HealthResponse, ChunkListRequest, ChunkListResponse
)
from src.models.database import Document, DocumentChunk, Profile, ProcessingJob
from src.services.document_processor import DocumentProcessor
from src.services.async_processor import get_async_processor
from sqlalchemy.orm import Session

# Configure production-grade logging
import json
from datetime import datetime as dt

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for production logging."""

    def format(self, record):
        log_entry = {
            "timestamp": dt.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add environment info
        if settings.is_production:
            log_entry["environment"] = settings.environment
            if settings.is_railway:
                log_entry["platform"] = "railway"

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry["request_id"] = record.request_id
        if hasattr(record, 'document_id'):
            log_entry["document_id"] = record.document_id

        return json.dumps(log_entry)

# Configure logging based on environment
if settings.log_format == 'json' or settings.is_production:
    formatter = JSONFormatter()
else:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Set up root logger
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    handlers=[handler],
    force=True
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Document Processing Microservice...")

    if os.getenv('TESTING_MODE', 'false').lower() == 'true':
        logger.warning("TESTING MODE ACTIVE - Authentication already patched")

    init_database()
    yield
    # Shutdown
    logger.info("Shutting down Document Processing Microservice...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add CORS middleware with environment-specific origins
cors_origins = settings.get_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add request logging and error handling middleware
@app.middleware("http")
async def logging_middleware(request, call_next):
    """Production-grade request logging and error handling."""
    import time
    import uuid
    from fastapi import status
    from fastapi.responses import JSONResponse

    # Generate request ID for tracing
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Add request ID to request state
    request.state.request_id = request_id

    # Log incoming request
    logger.info(
        f"Request started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    )

    try:
        # Process request
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time

        # Log successful response
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
            }
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(process_time, 4))

        return response

    except Exception as e:
        # Calculate response time for errors
        process_time = time.time() - start_time

        # Log error with full context
        logger.error(
            f"Request failed with exception: {str(e)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "process_time": round(process_time, 4),
                "exception_type": type(e).__name__,
            },
            exc_info=settings.is_production  # Include traceback in production logs
        )

        # Return structured error response
        error_detail = str(e) if not settings.is_production else "Internal server error"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": error_detail,
                "request_id": request_id,
                "timestamp": dt.utcnow().isoformat() + "Z"
            },
            headers={
                "X-Request-ID": request_id,
                "X-Process-Time": str(round(process_time, 4))
            }
        )


# Health check endpoint
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check for production monitoring."""
    import psutil
    from src.core.database import engine, supabase
    from src.services.embeddings_service import EmbeddingsService

    # Check services
    services = {}
    metrics = {}  # For non-boolean metrics
    errors = []

    # Database connection check
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1, NOW() as db_time"))
            row = result.fetchone()
            services["database"] = True
            metrics["database_time"] = str(row[1]) if row else None
    except Exception as e:
        services["database"] = False
        errors.append(f"Database: {str(e)[:100]}")

    # Supabase connectivity
    try:
        supabase.auth.get_session()
        services["supabase"] = True
    except Exception as e:
        services["supabase"] = False
        errors.append(f"Supabase: {str(e)[:100]}")

    # Vector database check
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL"))
        services["vector_database"] = True
    except Exception as e:
        services["vector_database"] = False
        errors.append(f"Vector DB: {str(e)[:100]}")

    # OpenAI API check
    try:
        embeddings = EmbeddingsService()
        services["embeddings"] = await embeddings.test_connection()
    except Exception as e:
        services["embeddings"] = False
        errors.append(f"OpenAI: {str(e)[:100]}")

    # File system check
    try:
        temp_dir = settings.temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        test_file = os.path.join(temp_dir, "health_check.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        services["filesystem"] = True
    except Exception as e:
        services["filesystem"] = False
        errors.append(f"Filesystem: {str(e)[:100]}")

    # Memory and system resources
    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        services["memory_available"] = memory.available > 100 * 1024 * 1024  # 100MB
        services["disk_available"] = disk.free > 500 * 1024 * 1024  # 500MB
        metrics["memory_usage_percent"] = memory.percent
        metrics["disk_usage_percent"] = (disk.used / disk.total) * 100
    except Exception as e:
        services["memory_available"] = False
        services["disk_available"] = False
        errors.append(f"System resources: {str(e)[:100]}")

    # Background processing
    services["background_processing"] = True  # Always available with BackgroundTasks

    # Calculate uptime
    current_time = datetime.utcnow()
    start_time = getattr(app.state, 'start_time', current_time)
    uptime_seconds = (current_time - start_time).total_seconds()

    # Determine overall health status
    critical_services = ["database", "embeddings", "filesystem"]
    health_status = "healthy"

    if not all(services.get(service, False) for service in critical_services):
        health_status = "unhealthy"
    elif not all(services.get(key, True) for key in ["supabase", "vector_database", "memory_available", "disk_available"]):
        health_status = "degraded"

    response_data = {
        "status": health_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "services": services,
        "metrics": metrics,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.utcnow()
    }

    # Add errors for debugging (only in non-production)
    if not settings.is_production and errors:
        response_data["errors"] = errors

    # Add platform info for Railway
    if settings.is_railway:
        response_data["platform"] = "railway"
        response_data["railway_environment"] = os.getenv("RAILWAY_ENVIRONMENT")

    return HealthResponse(**response_data)


# Document upload endpoint
@app.post("/api/documents/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    project_id: Optional[str] = Form(default="-"),
    metadata: Optional[str] = Form(default="{}"),
    tags: Optional[str] = Form(default="[]"),
    current_user: Dict[str, Any] = Depends(check_rate_limit),
    db: Session = Depends(get_db)
):
    """Upload and process a document."""
    # Validate user access
    if current_user["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only upload documents for your own user_id"
        )

    # Parse metadata and tags
    import json
    try:
        metadata_dict = json.loads(metadata)
        tags_list = json.loads(tags)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in metadata or tags"
        )

    # Read file content
    file_content = await file.read()

    # Validate file
    processor = DocumentProcessor()
    validation = processor.validate_file(file_content, file.filename)

    if not validation['valid']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation['error']
        )

    # Check storage quota
    if not await PermissionChecker.check_storage_quota(user_id, validation['file_size']):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Storage quota exceeded"
        )

    # Check for duplicate file (by hash)
    existing_doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.session_id == session_id,
        Document.file_hash == validation['file_hash']
    ).first()

    if existing_doc:
        return UploadResponse(
            document_id=existing_doc.id,
            status=existing_doc.status,
            message="Document already exists with same content",
            processing_job_id=None
        )

    # Save file temporarily
    temp_dir = settings.temp_dir
    os.makedirs(temp_dir, exist_ok=True)

    temp_file_path = os.path.join(temp_dir, f"{uuid4()}_{file.filename}")
    with open(temp_file_path, 'wb') as f:
        f.write(file_content)

    # Create document record
    document = Document(
        user_id=user_id,
        session_id=session_id,
        project_id=project_id or "-",
        filename=file.filename,
        file_type=validation['file_type'],
        file_size_bytes=validation['file_size'],
        file_hash=validation['file_hash'],
        mime_type=file.content_type,
        status='pending',
        storage_path=temp_file_path,
        doc_metadata=metadata_dict,
        tags=tags_list
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # Create processing job record
    job = ProcessingJob(
        document_id=document.id,
        user_id=user_id,
        job_type='processing',
        status='pending',
        priority=5,
        result={'file_path': temp_file_path, 'file_type': validation['file_type']}
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Get async processor
    processor = get_async_processor()

    # Process document in background using FastAPI BackgroundTasks
    # Note: Create a new database session for the background task
    async def process_with_new_session():
        from src.core.database import get_db
        with next(get_db()) as background_db:
            await processor.process_document(
                document_id=str(document.id),
                user_id=user_id,
                file_path=temp_file_path,
                file_type=validation['file_type'],
                db=background_db
            )

    background_tasks.add_task(process_with_new_session)

    # Estimate processing time based on file size (rough estimate)
    estimated_time = min(300, max(10, validation['file_size'] // 100000))

    return UploadResponse(
        document_id=document.id,
        status="processing",
        message="Document uploaded successfully and queued for processing",
        processing_job_id=str(job.id),
        estimated_processing_time=estimated_time
    )


# Document status endpoint
@app.get("/api/documents/status/{document_id}", response_model=DocumentStatus)
async def get_document_status(
    document_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document processing status."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user["user_id"]
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get progress from ProcessingJob if available
    progress_percentage = 0
    processing_message = None

    job = db.query(ProcessingJob).filter(
        ProcessingJob.document_id == document_id,
        ProcessingJob.job_type == 'processing'
    ).order_by(ProcessingJob.created_at.desc()).first()

    if job:
        progress_percentage = job.progress_percentage or 0
        processing_message = job.progress_message
    elif document.status == 'completed':
        progress_percentage = 100
    elif document.status == 'processing':
        progress_percentage = 50
    elif document.status == 'pending':
        progress_percentage = 0

    return DocumentStatus(
        id=document.id,
        user_id=document.user_id,
        session_id=document.session_id,
        project_id=document.project_id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        progress_percentage=progress_percentage,
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        processing_error=document.processing_error,
        created_at=document.created_at,
        updated_at=document.updated_at
    )


# Document list endpoint
@app.get("/api/documents/list", response_model=DocumentListResponse)
async def list_documents(
    user_id: str,
    session_id: Optional[str] = None,
    project_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's documents with filtering."""
    # Validate user access
    if current_user["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only list your own documents"
        )

    # Build query
    query = db.query(Document).filter(Document.user_id == user_id)

    if session_id:
        query = query.filter(Document.session_id == session_id)

    if project_id:
        query = query.filter(Document.project_id == project_id)

    if status_filter:
        query = query.filter(Document.status == status_filter)

    # Get total count
    total = query.count()

    # Get documents with pagination
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total
    )


# Document metadata endpoint
@app.get("/api/documents/{document_id}/metadata", response_model=DocumentResponse)
async def get_document_metadata(
    document_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed document metadata."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user["user_id"]
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return DocumentResponse.model_validate(document)


# Document chunks endpoint
@app.get("/api/documents/{document_id}/chunks", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: UUID,
    limit: int = 50,
    offset: int = 0,
    include_embeddings: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document chunks."""
    # Verify document access
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user["user_id"]
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get chunks
    query = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)

    total = query.count()
    chunks = query.order_by(DocumentChunk.chunk_index).offset(offset).limit(limit).all()

    # Format response
    chunk_responses = []
    for chunk in chunks:
        chunk_data = {
            'id': chunk.id,
            'document_id': chunk.document_id,
            'chunk_index': chunk.chunk_index,
            'text_content': chunk.text_content,
            'chunk_size': chunk.chunk_size,
            'token_count': chunk.token_count,
            'page_number': chunk.page_number,
            'start_char': chunk.start_char,
            'end_char': chunk.end_char,
            'metadata': chunk.chunk_metadata,
            'created_at': chunk.created_at
        }

        if include_embeddings and chunk.embedding:
            chunk_data['embedding'] = chunk.embedding

        chunk_responses.append(chunk_data)

    return ChunkListResponse(
        chunks=chunk_responses,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total
    )


# Document delete endpoint
@app.delete("/api/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: UUID,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document and all associated data."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user["user_id"]
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Get chunk count
    chunk_count = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).count()

    # Delete file from storage if exists
    if document.storage_path and os.path.exists(document.storage_path):
        os.remove(document.storage_path)

    # Update user storage quota
    profile = db.query(Profile).filter(Profile.user_id == current_user["user_id"]).first()
    if profile:
        file_size_mb = document.file_size_bytes / (1024 * 1024)
        current_storage = profile.storage_used_mb or 0.0
        current_count = profile.documents_count or 0
        profile.storage_used_mb = max(0, current_storage - file_size_mb)
        profile.documents_count = max(0, current_count - 1)

    # Delete document (cascades to chunks and jobs)
    db.delete(document)
    db.commit()

    return DeleteResponse(
        success=True,
        message=f"Document {document_id} deleted successfully",
        deleted_chunks=chunk_count
    )


# Initialize app state
app.state.start_time = datetime.utcnow()


# Serve test interface in development mode
if settings.environment == 'development':
    @app.get("/test")
    async def serve_test_interface():
        """Serve the test interface HTML file."""
        interface_path = Path(__file__).parent.parent / "test_interface.html"
        if interface_path.exists():
            return FileResponse(interface_path, media_type="text/html")
        else:
            raise HTTPException(404, "Test interface not found")

    @app.get("/")
    async def root():
        """Root endpoint with links to documentation and test interface."""
        return {
            "message": "Document Processing Microservice",
            "version": settings.app_version,
            "environment": settings.environment,
            "links": {
                "api_docs": "/api/docs",
                "redoc": "/api/redoc",
                "health": "/api/health",
                "test_interface": "/test" if settings.environment == 'development' else None
            }
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers if not settings.reload else 1
    )
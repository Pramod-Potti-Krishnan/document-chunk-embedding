"""
Async document processing service using FastAPI BackgroundTasks.
Replaces Celery for simplified deployment.
"""

import os
import asyncio
import tempfile
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from src.services.document_processor import DocumentProcessor
from src.services.text_chunker import TextChunker
from src.services.embeddings_service import EmbeddingsService
from src.models.database import Document, DocumentChunk, ProcessingJob, Profile
from src.config.settings import settings

logger = logging.getLogger(__name__)


class AsyncDocumentProcessor:
    """
    Handles asynchronous document processing without Celery.
    Uses FastAPI BackgroundTasks for non-blocking processing.
    """

    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.text_chunker = TextChunker()
        self.embeddings_service = None  # Initialized when needed

    async def _get_embeddings_service(self) -> EmbeddingsService:
        """Lazy initialization of embeddings service."""
        if self.embeddings_service is None:
            self.embeddings_service = EmbeddingsService()
        return self.embeddings_service

    async def process_document(
        self,
        document_id: str,
        user_id: str,
        file_path: str,
        file_type: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Main async processing function for documents.

        Args:
            document_id: UUID of the document
            user_id: User ID who owns the document
            file_path: Path to the temporary file
            file_type: Type of the file (pdf, docx, txt, md)
            db: Database session

        Returns:
            Processing result dictionary
        """
        job_id = None

        try:
            logger.info(f"Starting async processing for document {document_id}")

            # Get document and update status
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            document.status = 'processing'
            document.processing_started_at = datetime.utcnow()

            # Create or update processing job
            job = db.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id,
                ProcessingJob.job_type == 'processing'
            ).first()

            if not job:
                job = ProcessingJob(
                    document_id=document_id,
                    user_id=user_id,
                    job_type='processing',
                    status='processing',
                    started_at=datetime.utcnow(),
                    progress_percentage=0
                )
                db.add(job)
            else:
                job.status = 'processing'
                job.started_at = datetime.utcnow()
                job.progress_percentage = 0

            db.commit()
            job_id = job.id

            # Step 1: Extract text (25% progress)
            logger.info(f"Extracting text from {file_type} file")
            job.progress_percentage = 25
            job.progress_message = "Extracting text from document..."
            db.commit()

            extraction_result = self.document_processor.extract_text(file_path, file_type)
            text = extraction_result.get('text', '')

            # Update document with extraction metadata
            document.total_pages = extraction_result.get('total_pages', 1)
            document.doc_metadata = {
                **document.doc_metadata,
                **extraction_result.get('metadata', {})
            }
            db.commit()

            # Step 2: Chunk text (50% progress)
            logger.info(f"Chunking text for document {document_id}")
            job.progress_percentage = 50
            job.progress_message = "Creating text chunks..."
            db.commit()

            chunks = self.text_chunker.chunk_text(
                text,
                chunk_size_max=settings.chunk_size_max,
                chunk_overlap=settings.chunk_overlap
            )

            if not chunks:
                raise ValueError("No chunks created from document")

            # Step 3: Generate embeddings (75% progress)
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            job.progress_percentage = 75
            job.progress_message = f"Generating embeddings for {len(chunks)} chunks..."
            db.commit()

            # Initialize embeddings service
            embeddings_service = await self._get_embeddings_service()

            # Extract text from chunks for embedding
            chunk_texts = [chunk['text_content'] for chunk in chunks]

            # Generate embeddings in batches
            embeddings = await embeddings_service.generate_embeddings_batch(chunk_texts)

            # Step 4: Store chunks and embeddings (90% progress)
            logger.info(f"Storing {len(chunks)} chunks in database")
            job.progress_percentage = 90
            job.progress_message = "Storing chunks and embeddings..."
            db.commit()

            # Store chunks with embeddings
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if embedding is None:
                    logger.warning(f"No embedding for chunk {i}, skipping")
                    continue

                db_chunk = DocumentChunk(
                    document_id=document_id,
                    user_id=user_id,
                    session_id=document.session_id,
                    project_id=document.project_id,
                    chunk_index=i,
                    text_content=chunk['text_content'],
                    chunk_size=chunk['chunk_size'],
                    token_count=chunk.get('token_count'),
                    page_number=chunk.get('page_number'),
                    start_char=chunk['start_char'],
                    end_char=chunk['end_char'],
                    overlap_start=chunk.get('overlap_start', 0),
                    overlap_end=chunk.get('overlap_end', 0),
                    embedding=embedding,
                    embedding_model=settings.openai_embedding_model,
                    embedding_created_at=datetime.utcnow(),
                    chunk_metadata=chunk.get('metadata', {})
                )
                db.add(db_chunk)

            # Update document status
            document.status = 'completed'
            document.processing_completed_at = datetime.utcnow()
            document.total_chunks = len(chunks)
            document.total_tokens = sum(chunk.get('token_count', 0) for chunk in chunks)

            # Update user storage stats
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            if profile:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                profile.storage_used_mb += file_size_mb
                profile.documents_count += 1

            # Update job status
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            # Calculate processing time with timezone handling
            if job.started_at:
                # Handle potential timezone mismatches
                started_at = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
                completed_at = job.completed_at.replace(tzinfo=None) if job.completed_at.tzinfo else job.completed_at
                job.processing_time_seconds = (completed_at - started_at).total_seconds()
            else:
                job.processing_time_seconds = 0
            job.progress_percentage = 100
            job.progress_message = "Processing completed successfully"
            job.result = {
                'total_chunks': len(chunks),
                'total_tokens': document.total_tokens,
                'total_pages': document.total_pages,
                'embeddings_generated': len([e for e in embeddings if e is not None])
            }

            db.commit()

            # Clean up temporary file
            if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {file_path}: {e}")

            logger.info(f"Document {document_id} processed successfully")

            return {
                'document_id': str(document_id),
                'status': 'completed',
                'total_chunks': len(chunks),
                'total_tokens': sum(chunk.get('token_count', 0) for chunk in chunks),
                'total_pages': extraction_result.get('total_pages', 1),
                'processing_time': job.processing_time_seconds
            }

        except Exception as e:
            logger.error(f"Document processing failed for {document_id}: {e}")

            # Update document status
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = 'failed'
                document.processing_error = str(e)
                document.processing_completed_at = datetime.utcnow()

            # Update job status
            if job_id:
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    # Calculate processing time with timezone handling
                    if job.started_at and job.completed_at:
                        # Handle potential timezone mismatches
                        started_at = job.started_at.replace(tzinfo=None) if job.started_at.tzinfo else job.started_at
                        completed_at = job.completed_at.replace(tzinfo=None) if job.completed_at.tzinfo else job.completed_at
                        job.processing_time_seconds = (completed_at - started_at).total_seconds()
                    else:
                        job.processing_time_seconds = 0

            db.commit()

            # Clean up temporary file even on failure
            if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temp file on error: {cleanup_error}")

            raise e


class DatabaseJobQueue:
    """
    Optional: Database-backed job queue for more reliable processing.
    Can be used instead of or alongside BackgroundTasks.
    """

    def __init__(self, db: Session):
        self.db = db
        self.processor = AsyncDocumentProcessor()

    async def enqueue_job(
        self,
        document_id: str,
        user_id: str,
        file_path: str,
        file_type: str
    ) -> str:
        """Add a job to the database queue."""
        job = ProcessingJob(
            document_id=document_id,
            user_id=user_id,
            job_type='processing',
            status='pending',
            created_at=datetime.utcnow(),
            priority=5,  # Default priority
            result={
                'file_path': file_path,
                'file_type': file_type
            }
        )
        self.db.add(job)
        self.db.commit()
        return str(job.id)

    async def process_pending_jobs(self):
        """
        Background worker that polls for pending jobs.
        This would run in a separate asyncio task.
        """
        while True:
            try:
                # Get next pending job
                job = self.db.query(ProcessingJob).filter(
                    ProcessingJob.status == 'pending',
                    ProcessingJob.job_type == 'processing'
                ).order_by(
                    ProcessingJob.priority.desc(),
                    ProcessingJob.created_at
                ).first()

                if job:
                    # Extract job data
                    file_path = job.result.get('file_path')
                    file_type = job.result.get('file_type')

                    # Process the job
                    await self.processor.process_document(
                        document_id=str(job.document_id),
                        user_id=job.user_id,
                        file_path=file_path,
                        file_type=file_type,
                        db=self.db
                    )
                else:
                    # No pending jobs, wait before checking again
                    await asyncio.sleep(settings.job_polling_interval or 5)

            except Exception as e:
                logger.error(f"Error in job queue processor: {e}")
                await asyncio.sleep(10)  # Wait longer on error


# Singleton instance for reuse
_processor_instance = None

def get_async_processor() -> AsyncDocumentProcessor:
    """Get or create singleton processor instance."""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = AsyncDocumentProcessor()
    return _processor_instance
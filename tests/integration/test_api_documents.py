"""
Integration tests for document API endpoints.
"""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, Mock
from uuid import uuid4
import hashlib


class TestDocumentUploadAPI:
    """Test cases for document upload endpoint."""

    @pytest.mark.integration
    def test_upload_document_success(self, client, test_user, auth_headers, sample_text_content):
        """Test successful document upload."""
        with patch('src.tasks.document_tasks.process_document') as mock_task, \
             patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True):

            mock_task.delay.return_value.id = str(uuid4())

            # Create test file
            file_content = sample_text_content.encode('utf-8')
            files = {"file": ("test.txt", file_content, "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "project_id": test_user["project_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 200
            result = response.json()

            assert "document_id" in result
            assert result["status"] == "processing"
            assert "processing_job_id" in result
            assert "estimated_processing_time" in result

    @pytest.mark.integration
    def test_upload_document_invalid_user(self, client, test_user, auth_headers):
        """Test document upload with mismatched user ID."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": str(uuid4()),  # Different user ID
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 403
            assert "can only upload documents for your own user_id" in response.json()["detail"]

    @pytest.mark.integration
    def test_upload_document_invalid_json(self, client, test_user, auth_headers):
        """Test document upload with invalid JSON in metadata/tags."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user):
            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "invalid json",  # Invalid JSON
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 400
            assert "Invalid JSON" in response.json()["detail"]

    @pytest.mark.integration
    def test_upload_document_invalid_file(self, client, test_user, auth_headers):
        """Test document upload with invalid file."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.services.document_processor.DocumentProcessor.validate_file') as mock_validate:

            mock_validate.return_value = {
                'valid': False,
                'error': 'File type not allowed'
            }

            files = {"file": ("test.exe", b"content", "application/octet-stream")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 400
            assert "File type not allowed" in response.json()["detail"]

    @pytest.mark.integration
    def test_upload_document_quota_exceeded(self, client, test_user, auth_headers):
        """Test document upload when storage quota is exceeded."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=False), \
             patch('src.services.document_processor.DocumentProcessor.validate_file') as mock_validate:

            mock_validate.return_value = {
                'valid': True,
                'file_type': 'txt',
                'file_hash': 'test_hash',
                'file_size': 1024
            }

            files = {"file": ("test.txt", b"content", "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 402
            assert "Storage quota exceeded" in response.json()["detail"]

    @pytest.mark.integration
    def test_upload_duplicate_document(self, client, test_user, auth_headers, test_db_session):
        """Test uploading duplicate document (same hash)."""
        from src.models.database import Document

        file_content = b"test content"
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Create existing document
        existing_doc = Document(
            id=uuid4(),
            user_id=test_user["user_id"],
            session_id=test_user["session_id"],
            project_id=test_user["project_id"],
            filename="existing.txt",
            file_type="txt",
            file_size_bytes=len(file_content),
            file_hash=file_hash,
            mime_type="text/plain",
            status="completed"
        )
        test_db_session.add(existing_doc)
        test_db_session.commit()

        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True), \
             patch('src.services.document_processor.DocumentProcessor.validate_file') as mock_validate:

            mock_validate.return_value = {
                'valid': True,
                'file_type': 'txt',
                'file_hash': file_hash,
                'file_size': len(file_content)
            }

            files = {"file": ("duplicate.txt", file_content, "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            response = client.post("/api/documents/upload", files=files, data=data)

            assert response.status_code == 200
            result = response.json()
            assert result["document_id"] == str(existing_doc.id)
            assert "already exists" in result["message"]


class TestDocumentStatusAPI:
    """Test cases for document status endpoint."""

    @pytest.mark.integration
    def test_get_document_status_success(self, client, test_user, auth_headers, sample_document):
        """Test successful document status retrieval."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(f"/api/documents/status/{sample_document.id}")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(sample_document.id)
            assert data["user_id"] == sample_document.user_id
            assert data["filename"] == sample_document.filename
            assert data["status"] == sample_document.status
            assert "progress_percentage" in data

    @pytest.mark.integration
    def test_get_document_status_not_found(self, client, test_user, auth_headers):
        """Test document status for non-existent document."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            fake_id = uuid4()
            response = client.get(f"/api/documents/status/{fake_id}")

            assert response.status_code == 404
            assert "Document not found" in response.json()["detail"]

    @pytest.mark.integration
    def test_get_document_status_wrong_user(self, client, test_user, auth_headers, sample_document):
        """Test document status access by wrong user."""
        wrong_user = test_user.copy()
        wrong_user["user_id"] = str(uuid4())

        with patch('src.core.auth.get_current_user', return_value=wrong_user):
            response = client.get(f"/api/documents/status/{sample_document.id}")

            assert response.status_code == 404
            assert "Document not found" in response.json()["detail"]


class TestDocumentListAPI:
    """Test cases for document list endpoint."""

    @pytest.mark.integration
    def test_list_documents_success(self, client, test_user, auth_headers, sample_document):
        """Test successful document listing."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/list?user_id={test_user['user_id']}"
            )

            assert response.status_code == 200
            data = response.json()

            assert "documents" in data
            assert "total" in data
            assert "limit" in data
            assert "offset" in data
            assert "has_more" in data

            assert len(data["documents"]) >= 1
            assert data["total"] >= 1

    @pytest.mark.integration
    def test_list_documents_with_filters(self, client, test_user, auth_headers, sample_document):
        """Test document listing with filters."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/list?user_id={test_user['user_id']}"
                f"&session_id={test_user['session_id']}"
                f"&status_filter=completed"
            )

            assert response.status_code == 200
            data = response.json()

            # Should filter results
            for doc in data["documents"]:
                assert doc["session_id"] == test_user["session_id"]
                assert doc["status"] == "completed"

    @pytest.mark.integration
    def test_list_documents_pagination(self, client, test_user, auth_headers):
        """Test document listing pagination."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/list?user_id={test_user['user_id']}"
                "&limit=10&offset=0"
            )

            assert response.status_code == 200
            data = response.json()

            assert data["limit"] == 10
            assert data["offset"] == 0

    @pytest.mark.integration
    def test_list_documents_wrong_user(self, client, test_user, auth_headers):
        """Test document listing for wrong user."""
        wrong_user = test_user.copy()
        wrong_user["user_id"] = str(uuid4())

        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/list?user_id={wrong_user['user_id']}"
            )

            assert response.status_code == 403
            assert "can only list your own documents" in response.json()["detail"]


class TestDocumentMetadataAPI:
    """Test cases for document metadata endpoint."""

    @pytest.mark.integration
    def test_get_document_metadata_success(self, client, test_user, auth_headers, sample_document):
        """Test successful document metadata retrieval."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(f"/api/documents/{sample_document.id}/metadata")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == str(sample_document.id)
            assert data["filename"] == sample_document.filename
            assert data["file_type"] == sample_document.file_type
            assert data["metadata"] == sample_document.metadata
            assert data["tags"] == sample_document.tags

    @pytest.mark.integration
    def test_get_document_metadata_not_found(self, client, test_user, auth_headers):
        """Test document metadata for non-existent document."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            fake_id = uuid4()
            response = client.get(f"/api/documents/{fake_id}/metadata")

            assert response.status_code == 404


class TestDocumentChunksAPI:
    """Test cases for document chunks endpoint."""

    @pytest.mark.integration
    def test_get_document_chunks_success(self, client, test_user, auth_headers, sample_document, sample_chunks):
        """Test successful document chunks retrieval."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(f"/api/documents/{sample_document.id}/chunks")

            assert response.status_code == 200
            data = response.json()

            assert "chunks" in data
            assert "total" in data
            assert len(data["chunks"]) == len(sample_chunks)

            for chunk_data in data["chunks"]:
                assert "id" in chunk_data
                assert "chunk_index" in chunk_data
                assert "text_content" in chunk_data
                assert "chunk_size" in chunk_data

    @pytest.mark.integration
    def test_get_document_chunks_with_embeddings(self, client, test_user, auth_headers, sample_document, sample_chunks):
        """Test document chunks retrieval with embeddings."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/{sample_document.id}/chunks?include_embeddings=true"
            )

            assert response.status_code == 200
            data = response.json()

            for chunk_data in data["chunks"]:
                if "embedding" in chunk_data:
                    assert isinstance(chunk_data["embedding"], list)

    @pytest.mark.integration
    def test_get_document_chunks_pagination(self, client, test_user, auth_headers, sample_document):
        """Test document chunks pagination."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            response = client.get(
                f"/api/documents/{sample_document.id}/chunks?limit=2&offset=0"
            )

            assert response.status_code == 200
            data = response.json()

            assert data["limit"] == 2
            assert data["offset"] == 0

    @pytest.mark.integration
    def test_get_document_chunks_not_found(self, client, test_user, auth_headers):
        """Test document chunks for non-existent document."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            fake_id = uuid4()
            response = client.get(f"/api/documents/{fake_id}/chunks")

            assert response.status_code == 404


class TestDocumentDeleteAPI:
    """Test cases for document delete endpoint."""

    @pytest.mark.integration
    def test_delete_document_success(self, client, test_user, auth_headers, test_db_session):
        """Test successful document deletion."""
        from src.models.database import Document, Profile

        # Create test document
        doc = Document(
            id=uuid4(),
            user_id=test_user["user_id"],
            session_id=test_user["session_id"],
            project_id=test_user["project_id"],
            filename="test.txt",
            file_type="txt",
            file_size_bytes=1024,
            file_hash="test_hash",
            mime_type="text/plain",
            status="completed",
            storage_path="/tmp/test.txt"
        )
        test_db_session.add(doc)

        # Create user profile
        profile = Profile(
            user_id=test_user["user_id"],
            email=test_user["email"],
            storage_used_mb=1.0,
            documents_count=1
        )
        test_db_session.add(profile)
        test_db_session.commit()

        with patch('src.core.auth.get_current_user', return_value=test_user), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:

            response = client.delete(f"/api/documents/{doc.id}")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "deleted successfully" in data["message"]
            mock_remove.assert_called_once_with("/tmp/test.txt")

    @pytest.mark.integration
    def test_delete_document_not_found(self, client, test_user, auth_headers):
        """Test document deletion for non-existent document."""
        with patch('src.core.auth.get_current_user', return_value=test_user):
            fake_id = uuid4()
            response = client.delete(f"/api/documents/{fake_id}")

            assert response.status_code == 404

    @pytest.mark.integration
    def test_delete_document_wrong_user(self, client, test_user, auth_headers, sample_document):
        """Test document deletion by wrong user."""
        wrong_user = test_user.copy()
        wrong_user["user_id"] = str(uuid4())

        with patch('src.core.auth.get_current_user', return_value=wrong_user):
            response = client.delete(f"/api/documents/{sample_document.id}")

            assert response.status_code == 404
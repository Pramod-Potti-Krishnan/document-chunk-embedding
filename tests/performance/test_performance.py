"""
Performance tests for document processing microservice.
"""

import pytest
import time
import asyncio
import statistics
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, Mock
import tempfile
import os


class TestDocumentProcessingPerformance:
    """Performance tests for document processing components."""

    @pytest.mark.performance
    @pytest.mark.slow
    def test_large_text_file_processing_performance(self, large_text_content):
        """Test performance of processing large text files."""
        from src.services.document_processor import DocumentProcessor

        processor = DocumentProcessor()

        # Create large text file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_text_content)
            temp_path = f.name

        try:
            # Measure processing time
            start_time = time.time()
            result = processor.extract_text(temp_path, "txt")
            processing_time = time.time() - start_time

            # Performance assertions
            assert processing_time < 5.0  # Should process in under 5 seconds
            assert result['text'] is not None
            assert len(result['text']) > 0

            # Memory efficiency check
            import psutil
            process = psutil.Process()
            memory_usage_mb = process.memory_info().rss / 1024 / 1024
            assert memory_usage_mb < 500  # Should use less than 500MB

        finally:
            os.unlink(temp_path)

    @pytest.mark.performance
    @pytest.mark.slow
    def test_text_chunking_performance(self, large_text_content):
        """Test performance of text chunking with large content."""
        from src.services.text_chunker import TextChunker

        chunker = TextChunker()

        # Measure chunking time
        start_time = time.time()
        chunks = chunker.chunk_text(
            large_text_content,
            chunk_size_max=1000,
            chunk_overlap=100
        )
        chunking_time = time.time() - start_time

        # Performance assertions
        assert chunking_time < 3.0  # Should chunk in under 3 seconds
        assert len(chunks) > 0
        assert all(chunk['chunk_size'] <= 1000 for chunk in chunks)

        # Check chunk generation rate
        chunks_per_second = len(chunks) / chunking_time
        assert chunks_per_second > 10  # Should generate at least 10 chunks per second

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_embeddings_generation_performance(self, mock_embeddings_service):
        """Test performance of embeddings generation."""
        texts = ["Sample text for embedding generation"] * 100

        # Measure batch processing time
        start_time = time.time()
        embeddings = await mock_embeddings_service.generate_embeddings_batch(texts)
        processing_time = time.time() - start_time

        # Performance assertions
        assert processing_time < 10.0  # Should process 100 embeddings in under 10 seconds
        assert len(embeddings) == 100
        assert all(emb is not None for emb in embeddings)

        # Check processing rate
        embeddings_per_second = len(embeddings) / processing_time
        assert embeddings_per_second > 10  # Should process at least 10 embeddings per second

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_api_requests_performance(self, async_client, test_user):
        """Test API performance under concurrent requests."""

        async def make_health_request():
            response = await async_client.get("/api/health")
            return response.status_code == 200

        # Test concurrent health checks
        num_requests = 50
        start_time = time.time()

        # Execute requests concurrently
        tasks = [make_health_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        # Performance assertions
        assert total_time < 5.0  # Should handle 50 requests in under 5 seconds
        successful_requests = sum(1 for r in results if r is True)
        assert successful_requests >= num_requests * 0.9  # At least 90% success rate

        # Check request throughput
        requests_per_second = num_requests / total_time
        assert requests_per_second > 10  # Should handle at least 10 requests per second

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_document_upload_performance(self, async_client, test_user, large_file_content):
        """Test performance of document upload with large files."""
        with patch('src.core.auth.check_rate_limit', return_value=test_user), \
             patch('src.core.auth.PermissionChecker.check_storage_quota', return_value=True), \
             patch('src.tasks.document_tasks.process_document') as mock_task:

            mock_task.delay.return_value.id = "test_job_id"

            files = {"file": ("large_file.txt", large_file_content, "text/plain")}
            data = {
                "user_id": test_user["user_id"],
                "session_id": test_user["session_id"],
                "metadata": "{}",
                "tags": "[]"
            }

            # Measure upload time
            start_time = time.time()
            response = await async_client.post("/api/documents/upload", files=files, data=data)
            upload_time = time.time() - start_time

            # Performance assertions
            assert upload_time < 10.0  # Should upload in under 10 seconds
            assert response.status_code == 200

            # Check upload throughput
            file_size_mb = len(large_file_content) / (1024 * 1024)
            throughput_mbps = file_size_mb / upload_time
            assert throughput_mbps > 0.1  # Should achieve at least 0.1 MB/s

    @pytest.mark.performance
    def test_memory_usage_during_processing(self, large_text_content):
        """Test memory usage during document processing."""
        import psutil
        from src.services.document_processor import DocumentProcessor
        from src.services.text_chunker import TextChunker

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        processor = DocumentProcessor()
        chunker = TextChunker()

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_text_content)
            temp_path = f.name

        try:
            # Process document
            extracted = processor.extract_text(temp_path, "txt")
            chunks = chunker.chunk_text(extracted['text'])

            # Check peak memory usage
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = peak_memory - initial_memory

            # Memory assertions
            assert memory_increase < 200  # Should not increase memory by more than 200MB
            assert len(chunks) > 0

        finally:
            os.unlink(temp_path)

    @pytest.mark.performance
    @pytest.mark.slow
    def test_database_query_performance(self, test_db_session, test_user):
        """Test database query performance with large datasets."""
        from src.models.database import Document, DocumentChunk
        from uuid import uuid4

        # Create many test documents
        documents = []
        for i in range(100):
            doc = Document(
                id=uuid4(),
                user_id=test_user["user_id"],
                session_id=test_user["session_id"],
                project_id=test_user["project_id"],
                filename=f"perf_test_{i}.txt",
                file_type="txt",
                file_size_bytes=1000,
                file_hash=f"hash_{i}",
                mime_type="text/plain",
                status="completed"
            )
            documents.append(doc)

        test_db_session.add_all(documents)
        test_db_session.commit()

        # Test query performance
        start_time = time.time()

        # Query all documents for user
        user_docs = test_db_session.query(Document).filter(
            Document.user_id == test_user["user_id"]
        ).all()

        query_time = time.time() - start_time

        # Performance assertions
        assert query_time < 1.0  # Should query in under 1 second
        assert len(user_docs) >= 100

        # Test pagination query performance
        start_time = time.time()

        paginated_docs = test_db_session.query(Document).filter(
            Document.user_id == test_user["user_id"]
        ).offset(0).limit(10).all()

        pagination_time = time.time() - start_time

        assert pagination_time < 0.5  # Pagination should be faster
        assert len(paginated_docs) == 10

    @pytest.mark.performance
    def test_text_processing_algorithms_performance(self):
        """Test performance of text processing algorithms."""
        from src.services.text_chunker import TextChunker

        # Generate test text of varying sizes
        test_sizes = [1000, 10000, 50000, 100000]  # characters
        chunker = TextChunker()

        processing_times = []

        for size in test_sizes:
            test_text = "This is a test sentence. " * (size // 25)

            start_time = time.time()
            chunks = chunker.chunk_text(test_text, chunk_size_max=1000)
            processing_time = time.time() - start_time

            processing_times.append(processing_time)

            # Performance should scale reasonably
            chars_per_second = size / processing_time
            assert chars_per_second > 10000  # Should process at least 10k chars/sec

        # Check that performance scales reasonably (not exponentially)
        # Larger texts should take more time, but not exponentially more
        time_ratios = [processing_times[i+1] / processing_times[i] for i in range(len(processing_times)-1)]
        avg_ratio = statistics.mean(time_ratios)
        assert avg_ratio < 20  # Shouldn't increase by more than 20x per 10x size increase

    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_api_response_time_distribution(self, async_client):
        """Test API response time distribution under load."""

        async def measure_health_check():
            start_time = time.time()
            response = await async_client.get("/api/health")
            response_time = time.time() - start_time
            return response_time, response.status_code

        # Collect response times
        num_requests = 100
        tasks = [measure_health_check() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)

        response_times = [r[0] for r in results if r[1] == 200]

        if response_times:  # Only if we have successful responses
            # Calculate statistics
            avg_response_time = statistics.mean(response_times)
            p95_response_time = sorted(response_times)[int(0.95 * len(response_times))]
            p99_response_time = sorted(response_times)[int(0.99 * len(response_times))]

            # Performance assertions
            assert avg_response_time < 0.5  # Average response time under 500ms
            assert p95_response_time < 1.0  # 95th percentile under 1 second
            assert p99_response_time < 2.0  # 99th percentile under 2 seconds

    @pytest.mark.performance
    @pytest.mark.slow
    def test_file_validation_performance(self, large_file_content):
        """Test performance of file validation with large files."""
        from src.services.document_processor import DocumentProcessor

        processor = DocumentProcessor()

        # Test with different file sizes
        test_sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB

        for size in test_sizes:
            content = large_file_content[:size]

            start_time = time.time()
            result = processor.validate_file(content, "test.txt")
            validation_time = time.time() - start_time

            # Validation should be fast regardless of file size
            assert validation_time < 0.1  # Should validate in under 100ms
            assert result['valid'] in [True, False]

    @pytest.mark.performance
    @pytest.mark.slow
    def test_concurrent_file_processing(self, sample_text_content):
        """Test performance of concurrent file processing."""
        from src.services.document_processor import DocumentProcessor
        from src.services.text_chunker import TextChunker
        import threading

        processor = DocumentProcessor()
        chunker = TextChunker()

        # Create multiple temporary files
        temp_files = []
        for i in range(5):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(f"{sample_text_content} - File {i}")
                temp_files.append(f.name)

        def process_file(file_path):
            start_time = time.time()
            extracted = processor.extract_text(file_path, "txt")
            chunks = chunker.chunk_text(extracted['text'])
            processing_time = time.time() - start_time
            return len(chunks), processing_time

        try:
            # Process files concurrently
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(process_file, temp_files))
            total_time = time.time() - start_time

            # Performance assertions
            assert total_time < 10.0  # Should process 5 files concurrently in under 10 seconds
            assert all(chunks > 0 for chunks, _ in results)

            # Concurrent processing should be faster than sequential
            sequential_time = sum(time for _, time in results)
            speedup = sequential_time / total_time
            assert speedup > 1.5  # Should achieve at least 1.5x speedup

        finally:
            # Cleanup
            for file_path in temp_files:
                os.unlink(file_path)

    @pytest.mark.performance
    def test_token_counting_performance(self):
        """Test performance of token counting operations."""
        from src.services.text_chunker import TextChunker

        chunker = TextChunker()

        # Test with different text sizes
        test_texts = [
            "Short text.",
            "Medium length text with multiple sentences and words." * 10,
            "Very long text that should test the performance of token counting algorithms." * 100
        ]

        for text in test_texts:
            start_time = time.time()
            token_count = chunker._count_tokens(text)
            counting_time = time.time() - start_time

            # Token counting should be fast
            assert counting_time < 0.1  # Should count tokens in under 100ms
            assert token_count > 0
            assert isinstance(token_count, int)

            # Check counting rate
            chars_per_second = len(text) / counting_time
            assert chars_per_second > 50000  # Should process at least 50k chars/sec
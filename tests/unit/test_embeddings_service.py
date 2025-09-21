"""
Unit tests for EmbeddingsService.
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import AsyncMock, Mock, patch
import httpx

from src.services.embeddings_service import EmbeddingsService, MockEmbeddingsService


class TestEmbeddingsService:
    """Test cases for EmbeddingsService class."""

    @pytest.fixture
    def embeddings_service(self):
        """Create EmbeddingsService instance."""
        return EmbeddingsService()

    @pytest.fixture
    def mock_embeddings_service(self):
        """Create MockEmbeddingsService instance."""
        return MockEmbeddingsService()

    @pytest.fixture
    def sample_embedding(self):
        """Sample embedding vector."""
        return [0.1, 0.2, -0.3, 0.4, -0.5] * 307  # 1535 dimensions (close to 1536)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_init(self, embeddings_service):
        """Test EmbeddingsService initialization."""
        assert embeddings_service.api_key is not None
        assert embeddings_service.base_url is not None
        assert embeddings_service.model is not None
        assert embeddings_service.batch_size > 0
        assert embeddings_service.dimension > 0
        assert embeddings_service.client is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager(self, embeddings_service):
        """Test EmbeddingsService as async context manager."""
        async with embeddings_service as service:
            assert service is embeddings_service
        # Client should be closed after context

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, embeddings_service, sample_embedding):
        """Test successful embedding generation."""
        with patch.object(embeddings_service.client, 'post') as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"embedding": sample_embedding}]
            }
            mock_post.return_value = mock_response

            result = await embeddings_service.generate_embedding("test text")

            assert result == sample_embedding
            mock_post.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, embeddings_service):
        """Test embedding generation with API error."""
        with patch.object(embeddings_service.client, 'post') as mock_post:
            # Mock error response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_post.return_value = mock_response

            result = await embeddings_service.generate_embedding("test text")

            assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_network_error(self, embeddings_service):
        """Test embedding generation with network error."""
        with patch.object(embeddings_service.client, 'post') as mock_post:
            # Mock network error
            mock_post.side_effect = httpx.RequestError("Network error")

            result = await embeddings_service.generate_embedding("test text")

            assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_dimension_mismatch(self, embeddings_service):
        """Test embedding generation with dimension mismatch."""
        wrong_size_embedding = [0.1, 0.2, 0.3]  # Wrong size

        with patch.object(embeddings_service.client, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"embedding": wrong_size_embedding}]
            }
            mock_post.return_value = mock_response

            result = await embeddings_service.generate_embedding("test text")

            # Should still return the embedding despite warning
            assert result == wrong_size_embedding

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self, embeddings_service, sample_embedding):
        """Test successful batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]

        with patch.object(embeddings_service.client, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"embedding": sample_embedding},
                    {"embedding": sample_embedding},
                    {"embedding": sample_embedding}
                ]
            }
            mock_post.return_value = mock_response

            result = await embeddings_service.generate_embeddings_batch(texts)

            assert len(result) == 3
            assert all(emb == sample_embedding for emb in result)
            mock_post.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_partial_failure(self, embeddings_service, sample_embedding):
        """Test batch embedding generation with partial failure."""
        texts = ["text 1", "text 2"] * 10  # Create larger batch to test batching

        call_count = 0

        def mock_post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = Mock()
            if call_count == 1:
                # First batch succeeds
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": [{"embedding": sample_embedding}] * embeddings_service.batch_size
                }
            else:
                # Second batch fails
                mock_response.status_code = 500
            return mock_response

        with patch.object(embeddings_service.client, 'post', side_effect=mock_post_side_effect):
            with patch('asyncio.sleep'):  # Skip sleep in tests
                result = await embeddings_service.generate_embeddings_batch(texts)

                assert len(result) == len(texts)
                # Some should succeed, some should be None
                assert any(emb is not None for emb in result)
                assert any(emb is None for emb in result)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_with_delay(self, embeddings_service, sample_embedding):
        """Test that batch processing includes delays."""
        texts = ["text"] * (embeddings_service.batch_size + 1)  # Force multiple batches

        with patch.object(embeddings_service.client, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [{"embedding": sample_embedding}]
            }
            mock_post.return_value = mock_response

            with patch('asyncio.sleep') as mock_sleep:
                await embeddings_service.generate_embeddings_batch(texts)

                # Should have called sleep between batches
                mock_sleep.assert_called_with(1.0)

    @pytest.mark.unit
    def test_calculate_similarity_normal(self, embeddings_service):
        """Test cosine similarity calculation."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = embeddings_service.calculate_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0, rel=1e-5)

    @pytest.mark.unit
    def test_calculate_similarity_orthogonal(self, embeddings_service):
        """Test similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = embeddings_service.calculate_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0, abs=1e-5)

    @pytest.mark.unit
    def test_calculate_similarity_opposite(self, embeddings_service):
        """Test similarity of opposite vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        similarity = embeddings_service.calculate_similarity(vec1, vec2)

        # Should be 0 (clamped from -1)
        assert similarity == 0.0

    @pytest.mark.unit
    def test_calculate_similarity_zero_vectors(self, embeddings_service):
        """Test similarity with zero vectors."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = embeddings_service.calculate_similarity(vec1, vec2)

        assert similarity == 0.0

    @pytest.mark.unit
    def test_calculate_similarity_error_handling(self, embeddings_service):
        """Test similarity calculation error handling."""
        # Test with incompatible vectors
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]  # Different dimensions

        similarity = embeddings_service.calculate_similarity(vec1, vec2)

        assert similarity == 0.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_test_connection_success(self, embeddings_service, sample_embedding):
        """Test successful connection test."""
        with patch.object(embeddings_service, 'generate_embedding') as mock_generate:
            mock_generate.return_value = sample_embedding

            result = await embeddings_service.test_connection()

            assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_test_connection_failure(self, embeddings_service):
        """Test failed connection test."""
        with patch.object(embeddings_service, 'generate_embedding') as mock_generate:
            mock_generate.return_value = None

            result = await embeddings_service.test_connection()

            assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_test_connection_exception(self, embeddings_service):
        """Test connection test with exception."""
        with patch.object(embeddings_service, 'generate_embedding') as mock_generate:
            mock_generate.side_effect = Exception("Connection failed")

            result = await embeddings_service.test_connection()

            assert result is False

    @pytest.mark.unit
    def test_chunk_text_for_embedding_short_text(self, embeddings_service):
        """Test text chunking for short text."""
        text = "This is a short text."

        result = embeddings_service.chunk_text_for_embedding(text, max_tokens=100)

        assert len(result) == 1
        assert result[0] == text

    @pytest.mark.unit
    def test_chunk_text_for_embedding_long_text(self, embeddings_service):
        """Test text chunking for long text."""
        # Create text that exceeds token limit
        text = "This is a long sentence. " * 200  # Should exceed default limit

        result = embeddings_service.chunk_text_for_embedding(text, max_tokens=100)

        assert len(result) > 1
        for chunk in result:
            # Each chunk should be roughly within limit
            assert len(chunk) <= 100 * 4  # max_tokens * 4 chars

    @pytest.mark.unit
    def test_chunk_text_for_embedding_sentence_breaks(self, embeddings_service):
        """Test that chunking respects sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence."

        result = embeddings_service.chunk_text_for_embedding(text, max_tokens=20)

        # Should prefer breaking at sentence boundaries
        for chunk in result:
            if '. ' in chunk and not chunk.endswith('. '):
                # If chunk contains sentence break but doesn't end with it,
                # it should end at a sentence boundary
                assert chunk.rstrip().endswith('.')

    @pytest.mark.unit
    def test_chunk_text_for_embedding_word_breaks(self, embeddings_service):
        """Test that chunking respects word boundaries."""
        text = "word1 word2 word3 word4 word5 word6 word7 word8"

        result = embeddings_service.chunk_text_for_embedding(text, max_tokens=10)

        for chunk in result:
            if ' ' in chunk:
                # Should not break in middle of words
                assert not chunk.endswith(' ')


class TestMockEmbeddingsService:
    """Test cases for MockEmbeddingsService."""

    @pytest.fixture
    def mock_service(self):
        """Create MockEmbeddingsService instance."""
        return MockEmbeddingsService()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_consistent(self, mock_service):
        """Test that mock embedding generation is consistent."""
        text = "test text"

        result1 = await mock_service.generate_embedding(text)
        result2 = await mock_service.generate_embedding(text)

        assert result1 == result2
        assert len(result1) == mock_service.dimension

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embedding_different_texts(self, mock_service):
        """Test that different texts produce different embeddings."""
        text1 = "first text"
        text2 = "second text"

        result1 = await mock_service.generate_embedding(text1)
        result2 = await mock_service.generate_embedding(text2)

        assert result1 != result2
        assert len(result1) == len(result2) == mock_service.dimension

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, mock_service):
        """Test mock batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]

        result = await mock_service.generate_embeddings_batch(texts)

        assert len(result) == 3
        assert all(isinstance(emb, list) for emb in result)
        assert all(len(emb) == mock_service.dimension for emb in result)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_test_connection_always_succeeds(self, mock_service):
        """Test that mock connection test always succeeds."""
        result = await mock_service.test_connection()

        assert result is True

    @pytest.mark.unit
    def test_mock_inheritance(self, mock_service):
        """Test that MockEmbeddingsService inherits properly."""
        assert isinstance(mock_service, EmbeddingsService)
        assert hasattr(mock_service, 'calculate_similarity')
        assert hasattr(mock_service, 'chunk_text_for_embedding')

    @pytest.mark.unit
    def test_mock_similarity_calculation(self, mock_service):
        """Test similarity calculation with mock embeddings."""
        # Use the inherited similarity method
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = mock_service.calculate_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0, rel=1e-5)


class TestEmbeddingsServiceIntegration:
    """Integration-like tests that test multiple components together."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_full_embedding_workflow(self, mock_embeddings_service):
        """Test complete embedding workflow with mock service."""
        # Test connection
        connection_ok = await mock_embeddings_service.test_connection()
        assert connection_ok

        # Generate single embedding
        text = "This is a test document for embedding."
        embedding = await mock_embeddings_service.generate_embedding(text)
        assert embedding is not None
        assert len(embedding) == mock_embeddings_service.dimension

        # Generate batch embeddings
        texts = ["First text", "Second text", "Third text"]
        embeddings = await mock_embeddings_service.generate_embeddings_batch(texts)
        assert len(embeddings) == 3
        assert all(emb is not None for emb in embeddings)

        # Calculate similarities
        similarity_same = mock_embeddings_service.calculate_similarity(
            embeddings[0], embeddings[0]
        )
        assert similarity_same == 1.0

        similarity_different = mock_embeddings_service.calculate_similarity(
            embeddings[0], embeddings[1]
        )
        assert 0.0 <= similarity_different <= 1.0

    @pytest.mark.unit
    def test_text_chunking_with_embeddings_context(self, mock_embeddings_service):
        """Test text chunking in context of embeddings."""
        long_text = "This is a very long document. " * 100

        # Test chunking for embedding
        chunks = mock_embeddings_service.chunk_text_for_embedding(long_text)

        assert len(chunks) > 1
        for chunk in chunks:
            # Each chunk should be processable
            assert len(chunk) > 0
            assert isinstance(chunk, str)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_recovery_patterns(self, embeddings_service):
        """Test various error recovery patterns."""
        # Test with None input
        result = await embeddings_service.generate_embedding(None)
        assert result is None

        # Test with empty input
        result = await embeddings_service.generate_embedding("")
        # Should either return None or handle gracefully
        # (behavior depends on API)

        # Test batch with mixed valid/invalid inputs
        texts = ["valid text", None, "", "another valid text"]
        # This would depend on implementation details,
        # but should not crash
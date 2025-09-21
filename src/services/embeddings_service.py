import httpx
import asyncio
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
import numpy as np

from src.config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """
    Service for generating embeddings using OpenAI API.
    """

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.openai_embedding_model
        self.batch_size = settings.embedding_batch_size
        self.dimension = settings.embedding_dimension
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(settings.embedding_max_retries),
        wait=wait_exponential(multiplier=settings.embedding_retry_delay)
    )
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of float values representing the embedding vector
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # OpenAI Embeddings API
            payload = {
                "model": self.model,
                "input": text,
                "encoding_format": "float"
            }

            response = await self.client.post(
                f"{self.base_url}/v1/embeddings",
                headers=headers,
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Embedding API error: {response.status_code} - {response.text}")
                return None

            data = response.json()
            embedding = data["data"][0]["embedding"]

            # Validate dimension
            if len(embedding) != self.dimension:
                logger.warning(f"Embedding dimension mismatch: expected {self.dimension}, got {len(embedding)}")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of texts to generate embeddings for

        Returns:
            List of embeddings (or None for failed items)
        """
        embeddings = []

        # Process in batches to avoid rate limiting
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.model,
                    "input": batch
                }

                response = await self.client.post(
                    f"{self.base_url}/v1/embeddings",
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    logger.error(f"Batch embedding API error: {response.status_code}")
                    # Return None for failed batch items
                    embeddings.extend([None] * len(batch))
                    continue

                data = response.json()
                batch_embeddings = [item["embedding"] for item in data["data"]]
                embeddings.extend(batch_embeddings)

                # Rate limiting delay
                if i + self.batch_size < len(texts):
                    await asyncio.sleep(1.0)  # 1 second delay between batches

            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")
                embeddings.extend([None] * len(batch))

        return embeddings

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Ensure result is between 0 and 1
            return float(max(0.0, min(1.0, similarity)))

        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0

    async def test_connection(self) -> bool:
        """
        Test connection to embeddings API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_text = "Hello, this is a test."
            embedding = await self.generate_embedding(test_text)
            return embedding is not None and len(embedding) > 0

        except Exception as e:
            logger.error(f"Embeddings API connection test failed: {e}")
            return False

    def chunk_text_for_embedding(self, text: str, max_tokens: int = 8191) -> List[str]:
        """
        Chunk text to fit within model's token limit.

        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk

        Returns:
            List of text chunks
        """
        # Simple character-based chunking for now
        # Roughly 1 token = 4 characters for English text
        max_chars = max_tokens * 4

        if len(text) <= max_chars:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + max_chars, len(text))

            # Try to find a good break point
            if end < len(text):
                # Look for sentence break
                sent_break = text.rfind('. ', start, end)
                if sent_break > start:
                    end = sent_break + 1
                else:
                    # Look for word break
                    word_break = text.rfind(' ', start, end)
                    if word_break > start:
                        end = word_break

            chunks.append(text[start:end].strip())
            start = end

        return chunks


class MockEmbeddingsService(EmbeddingsService):
    """
    Mock embeddings service for testing without API calls.
    """

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate a mock embedding."""
        # Generate consistent fake embedding based on text hash
        text_hash = hash(text) % 1000000
        np.random.seed(text_hash)
        embedding = np.random.randn(self.dimension).tolist()
        return embedding

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate mock embeddings for batch."""
        return [await self.generate_embedding(text) for text in texts]

    async def test_connection(self) -> bool:
        """Mock connection test always succeeds."""
        return True
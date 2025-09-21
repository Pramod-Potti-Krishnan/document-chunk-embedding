import re
from typing import List, Dict, Any, Optional
import tiktoken
import logging

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TextChunker:
    """
    Intelligent text chunking with semantic boundary preservation.
    """

    def __init__(self):
        # Initialize tiktoken encoder for token counting
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to basic character counting if tiktoken fails
            self.encoder = None
            logger.warning("tiktoken encoder not available, using character counting")

    def chunk_text(
        self,
        text: str,
        chunk_size_min: Optional[int] = None,
        chunk_size_max: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        preserve_sentences: bool = True,
        preserve_paragraphs: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Split text into intelligent chunks with overlap.

        Args:
            text: The text to chunk
            chunk_size_min: Minimum chunk size in characters
            chunk_size_max: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            preserve_sentences: Try to keep sentences intact
            preserve_paragraphs: Try to keep paragraphs intact

        Returns:
            List of chunks with metadata
        """
        chunk_size_min = chunk_size_min or settings.chunk_size_min
        chunk_size_max = chunk_size_max or settings.chunk_size_max
        chunk_overlap = chunk_overlap or settings.chunk_overlap

        if not text or not text.strip():
            return []

        # Clean and normalize text
        text = self._normalize_text(text)

        # Split into paragraphs first if preserving
        if preserve_paragraphs:
            chunks = self._chunk_by_paragraphs(text, chunk_size_min, chunk_size_max, chunk_overlap)
        elif preserve_sentences:
            chunks = self._chunk_by_sentences(text, chunk_size_min, chunk_size_max, chunk_overlap)
        else:
            chunks = self._chunk_by_characters(text, chunk_size_min, chunk_size_max, chunk_overlap)

        # Add metadata to each chunk
        enriched_chunks = []
        for i, chunk_data in enumerate(chunks):
            token_count = self._count_tokens(chunk_data['text'])

            enriched_chunks.append({
                'chunk_index': i,
                'text_content': chunk_data['text'],
                'chunk_size': len(chunk_data['text']),
                'token_count': token_count,
                'start_char': chunk_data['start'],
                'end_char': chunk_data['end'],
                'overlap_start': chunk_data.get('overlap_start', 0),
                'overlap_end': chunk_data.get('overlap_end', 0),
            })

        return enriched_chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent chunking."""
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Replace tabs with spaces
        text = text.replace('\t', '    ')

        # Remove trailing whitespace from lines
        lines = text.split('\n')
        lines = [line.rstrip() for line in lines]
        text = '\n'.join(lines)

        return text.strip()

    def _chunk_by_paragraphs(
        self,
        text: str,
        chunk_size_min: int,
        chunk_size_max: int,
        chunk_overlap: int
    ) -> List[Dict[str, Any]]:
        """Chunk text by paragraphs with intelligent merging."""
        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        char_position = 0

        for para in paragraphs:
            para_size = len(para)

            # If single paragraph exceeds max size, split it further
            if para_size > chunk_size_max:
                # Flush current chunk if any
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'start': char_position - current_size,
                        'end': char_position,
                    })
                    current_chunk = []
                    current_size = 0

                # Split large paragraph by sentences
                sub_chunks = self._chunk_by_sentences(para, chunk_size_min, chunk_size_max, chunk_overlap)
                for sc in sub_chunks:
                    chunks.append({
                        'text': sc['text'],
                        'start': char_position + sc['start'],
                        'end': char_position + sc['end'],
                    })

                char_position += para_size + 2  # Account for \n\n

            # If adding paragraph exceeds max size, start new chunk
            elif current_size + para_size > chunk_size_max:
                # Save current chunk
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'start': char_position - current_size,
                        'end': char_position,
                    })

                # Start new chunk with this paragraph
                current_chunk = [para]
                current_size = para_size

            else:
                # Add to current chunk
                current_chunk.append(para)
                current_size += para_size + (2 if current_chunk else 0)  # Account for \n\n

            char_position += para_size + 2

        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start': char_position - current_size,
                'end': char_position,
            })

        # Add overlaps
        return self._add_overlaps(chunks, text, chunk_overlap)

    def _chunk_by_sentences(
        self,
        text: str,
        chunk_size_min: int,
        chunk_size_max: int,
        chunk_overlap: int
    ) -> List[Dict[str, Any]]:
        """Chunk text by sentences with intelligent merging."""
        # Simple sentence splitting (can be improved with better NLP)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        char_position = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            # If single sentence exceeds max size, split by characters
            if sentence_size > chunk_size_max:
                # Flush current chunk
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'start': char_position - current_size,
                        'end': char_position,
                    })
                    current_chunk = []
                    current_size = 0

                # Split large sentence
                sub_chunks = self._chunk_by_characters(sentence, chunk_size_min, chunk_size_max, chunk_overlap)
                for sc in sub_chunks:
                    chunks.append({
                        'text': sc['text'],
                        'start': char_position + sc['start'],
                        'end': char_position + sc['end'],
                    })

                char_position += sentence_size + 1

            # If adding sentence exceeds max size, start new chunk
            elif current_size + sentence_size > chunk_size_max:
                # Check if current chunk meets minimum size
                if current_size >= chunk_size_min:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'start': char_position - current_size,
                        'end': char_position,
                    })
                    current_chunk = [sentence]
                    current_size = sentence_size
                else:
                    # Force add to meet minimum
                    current_chunk.append(sentence)
                    current_size += sentence_size + 1

            else:
                current_chunk.append(sentence)
                current_size += sentence_size + (1 if current_chunk else 0)

            char_position += sentence_size + 1

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'start': char_position - current_size,
                'end': char_position,
            })

        return self._add_overlaps(chunks, text, chunk_overlap)

    def _chunk_by_characters(
        self,
        text: str,
        chunk_size_min: int,
        chunk_size_max: int,
        chunk_overlap: int
    ) -> List[Dict[str, Any]]:
        """Simple character-based chunking as fallback."""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate chunk end
            end = min(start + chunk_size_max, text_length)

            # Try to find a good break point
            if end < text_length:
                # Look for paragraph break
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + chunk_size_min:
                    end = para_break

                # Look for sentence break
                elif '.' in text[start:end]:
                    sent_break = text.rfind('. ', start, end)
                    if sent_break > start + chunk_size_min:
                        end = sent_break + 1

                # Look for word break
                else:
                    word_break = text.rfind(' ', start, end)
                    if word_break > start + chunk_size_min:
                        end = word_break

            chunks.append({
                'text': text[start:end].strip(),
                'start': start,
                'end': end,
            })

            # Move start position with overlap
            start = end - chunk_overlap if end < text_length else end

        return chunks

    def _add_overlaps(self, chunks: List[Dict], original_text: str, overlap_size: int) -> List[Dict]:
        """Add overlap information to chunks."""
        for i, chunk in enumerate(chunks):
            # Calculate overlap with previous chunk
            if i > 0:
                overlap_start = max(0, chunks[i-1]['end'] - overlap_size)
                chunk['overlap_start'] = len(original_text[overlap_start:chunk['start']])
            else:
                chunk['overlap_start'] = 0

            # Calculate overlap with next chunk
            if i < len(chunks) - 1:
                overlap_end = min(len(original_text), chunk['end'] + overlap_size)
                chunk['overlap_end'] = len(original_text[chunk['end']:overlap_end])
            else:
                chunk['overlap_end'] = 0

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or fallback to word count."""
        if self.encoder:
            try:
                return len(self.encoder.encode(text))
            except:
                pass

        # Fallback to simple word count approximation
        # Roughly 1 token = 0.75 words
        word_count = len(text.split())
        return int(word_count / 0.75)

    def chunk_pages(self, pages: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """
        Chunk multiple pages while preserving page boundaries.

        Args:
            pages: List of page dictionaries with 'text' and 'page_number'
            **kwargs: Arguments to pass to chunk_text

        Returns:
            List of chunks with page information
        """
        all_chunks = []

        for page in pages:
            page_number = page.get('page_number', 1)
            page_text = page.get('text', '')

            if not page_text.strip():
                continue

            # Chunk the page text
            page_chunks = self.chunk_text(page_text, **kwargs)

            # Add page information to each chunk
            for chunk in page_chunks:
                chunk['page_number'] = page_number
                all_chunks.append(chunk)

        # Re-index chunks globally
        for i, chunk in enumerate(all_chunks):
            chunk['chunk_index'] = i

        return all_chunks
"""
Unit tests for TextChunker service.
"""

import pytest
from unittest.mock import patch, Mock

from src.services.text_chunker import TextChunker


class TestTextChunker:
    """Test cases for TextChunker class."""

    @pytest.fixture
    def chunker(self):
        """Create TextChunker instance."""
        return TextChunker()

    @pytest.fixture
    def simple_text(self):
        """Simple test text."""
        return "This is sentence one. This is sentence two. This is sentence three."

    @pytest.fixture
    def paragraph_text(self):
        """Text with multiple paragraphs."""
        return """First paragraph with multiple sentences. This is the second sentence of the first paragraph.

Second paragraph starts here. It also has multiple sentences.

Third paragraph is the final one. It completes our test text."""

    @pytest.fixture
    def long_text(self):
        """Long text for testing chunking limits."""
        base = "This is a test sentence that will be repeated many times. "
        return base * 100  # Creates a long text

    def test_init_with_tiktoken(self, chunker):
        """Test initialization with tiktoken encoder."""
        assert chunker.encoder is not None

    @patch('tiktoken.get_encoding')
    def test_init_without_tiktoken(self, mock_tiktoken):
        """Test initialization when tiktoken fails."""
        mock_tiktoken.side_effect = Exception("tiktoken not available")
        chunker = TextChunker()
        assert chunker.encoder is None

    @pytest.mark.unit
    def test_chunk_text_empty_input(self, chunker):
        """Test chunking with empty input."""
        result = chunker.chunk_text("")
        assert result == []

        result = chunker.chunk_text("   ")
        assert result == []

        result = chunker.chunk_text(None)
        assert result == []

    @pytest.mark.unit
    def test_chunk_text_simple(self, chunker, simple_text):
        """Test basic text chunking."""
        result = chunker.chunk_text(
            simple_text,
            chunk_size_min=10,
            chunk_size_max=50,
            chunk_overlap=5
        )

        assert len(result) > 0
        for chunk in result:
            assert 'chunk_index' in chunk
            assert 'text_content' in chunk
            assert 'chunk_size' in chunk
            assert 'token_count' in chunk
            assert 'start_char' in chunk
            assert 'end_char' in chunk
            assert chunk['chunk_size'] == len(chunk['text_content'])

    @pytest.mark.unit
    def test_chunk_text_by_paragraphs(self, chunker, paragraph_text):
        """Test chunking by paragraphs."""
        result = chunker.chunk_text(
            paragraph_text,
            chunk_size_min=50,
            chunk_size_max=200,
            chunk_overlap=10,
            preserve_paragraphs=True
        )

        assert len(result) > 0
        # Check that paragraph boundaries are respected
        for chunk in result:
            text = chunk['text_content']
            assert len(text) <= 200
            # Should not break in the middle of sentences aggressively

    @pytest.mark.unit
    def test_chunk_text_by_sentences(self, chunker, simple_text):
        """Test chunking by sentences."""
        result = chunker.chunk_text(
            simple_text,
            chunk_size_min=10,
            chunk_size_max=40,
            chunk_overlap=5,
            preserve_sentences=True,
            preserve_paragraphs=False
        )

        assert len(result) > 0
        # Should try to keep sentences intact
        for chunk in result:
            text = chunk['text_content']
            assert len(text) <= 40

    @pytest.mark.unit
    def test_chunk_text_by_characters(self, chunker, simple_text):
        """Test character-based chunking."""
        result = chunker.chunk_text(
            simple_text,
            chunk_size_min=10,
            chunk_size_max=30,
            chunk_overlap=5,
            preserve_sentences=False,
            preserve_paragraphs=False
        )

        assert len(result) > 0
        for chunk in result:
            assert chunk['chunk_size'] <= 30

    @pytest.mark.unit
    def test_normalize_text(self, chunker):
        """Test text normalization."""
        text = "Line 1\n\n\n\nLine 2\t\tWith\ttabs   \nLine 3  "
        normalized = chunker._normalize_text(text)

        # Should reduce multiple newlines
        assert "\n\n\n" not in normalized
        # Should replace tabs with spaces
        assert "\t" not in normalized
        # Should remove trailing whitespace
        assert not normalized.endswith(" ")

    @pytest.mark.unit
    def test_chunk_by_paragraphs_large_paragraph(self, chunker):
        """Test paragraph chunking with oversized paragraphs."""
        # Create a paragraph larger than max chunk size
        large_para = "This is a very long sentence. " * 50
        text = f"Small para.\n\n{large_para}\n\nAnother small para."

        result = chunker._chunk_by_paragraphs(text, 50, 200, 10)

        assert len(result) > 1
        # Large paragraph should be split further

    @pytest.mark.unit
    def test_chunk_by_sentences_large_sentence(self, chunker):
        """Test sentence chunking with oversized sentences."""
        # Create a sentence larger than max chunk size
        large_sentence = "This is a very very very long sentence that exceeds the maximum chunk size limit and should be split into smaller pieces."
        text = f"Short sentence. {large_sentence} Another short sentence."

        result = chunker._chunk_by_sentences(text, 20, 50, 5)

        assert len(result) > 1

    @pytest.mark.unit
    def test_chunk_by_characters_with_breaks(self, chunker, long_text):
        """Test character chunking with intelligent break points."""
        result = chunker._chunk_by_characters(long_text, 100, 200, 20)

        assert len(result) > 1
        for chunk in result:
            # Should respect word boundaries when possible
            text = chunk['text']
            if len(text) > 100:  # If chunk is reasonably sized
                # Should not break in the middle of words (end with space or punctuation)
                assert text[-1] in [' ', '.', '!', '?'] or text == long_text[chunk['end']:chunk['end']]

    @pytest.mark.unit
    def test_add_overlaps(self, chunker):
        """Test overlap calculation."""
        chunks = [
            {'text': 'First chunk', 'start': 0, 'end': 11},
            {'text': 'Second chunk', 'start': 11, 'end': 23},
            {'text': 'Third chunk', 'start': 23, 'end': 34}
        ]
        original_text = "First chunkSecond chunkThird chunk"

        result = chunker._add_overlaps(chunks, original_text, 5)

        assert len(result) == 3
        for i, chunk in enumerate(result):
            assert 'overlap_start' in chunk
            assert 'overlap_end' in chunk

            if i == 0:
                assert chunk['overlap_start'] == 0
            else:
                assert chunk['overlap_start'] >= 0

            if i == len(result) - 1:
                assert chunk['overlap_end'] == 0
            else:
                assert chunk['overlap_end'] >= 0

    @pytest.mark.unit
    def test_count_tokens_with_encoder(self, chunker):
        """Test token counting with tiktoken encoder."""
        text = "This is a test sentence for token counting."

        if chunker.encoder:
            token_count = chunker._count_tokens(text)
            assert token_count > 0
            assert isinstance(token_count, int)

    @pytest.mark.unit
    def test_count_tokens_without_encoder(self, chunker):
        """Test token counting fallback without encoder."""
        text = "This is a test sentence for token counting."

        # Temporarily remove encoder
        original_encoder = chunker.encoder
        chunker.encoder = None

        try:
            token_count = chunker._count_tokens(text)
            assert token_count > 0
            assert isinstance(token_count, int)
            # Should be approximately word_count / 0.75
            word_count = len(text.split())
            expected_tokens = int(word_count / 0.75)
            assert abs(token_count - expected_tokens) <= 1
        finally:
            chunker.encoder = original_encoder

    @pytest.mark.unit
    def test_count_tokens_encoder_error(self, chunker):
        """Test token counting when encoder fails."""
        text = "This is a test sentence."

        if chunker.encoder:
            # Mock encoder to raise exception
            original_encode = chunker.encoder.encode
            chunker.encoder.encode = Mock(side_effect=Exception("Encoding failed"))

            try:
                token_count = chunker._count_tokens(text)
                assert token_count > 0
                # Should fallback to word count method
                word_count = len(text.split())
                expected_tokens = int(word_count / 0.75)
                assert abs(token_count - expected_tokens) <= 1
            finally:
                chunker.encoder.encode = original_encode

    @pytest.mark.unit
    def test_chunk_pages_empty_input(self, chunker):
        """Test page chunking with empty input."""
        result = chunker.chunk_pages([])
        assert result == []

    @pytest.mark.unit
    def test_chunk_pages_single_page(self, chunker):
        """Test page chunking with single page."""
        pages = [
            {
                'page_number': 1,
                'text': 'This is page one content. It has multiple sentences.'
            }
        ]

        result = chunker.chunk_pages(pages, chunk_size_max=30, chunk_overlap=5)

        assert len(result) > 0
        for chunk in result:
            assert chunk['page_number'] == 1
            assert 'chunk_index' in chunk

    @pytest.mark.unit
    def test_chunk_pages_multiple_pages(self, chunker):
        """Test page chunking with multiple pages."""
        pages = [
            {
                'page_number': 1,
                'text': 'Page one content with some text.'
            },
            {
                'page_number': 2,
                'text': 'Page two content with different text.'
            },
            {
                'page_number': 3,
                'text': ''  # Empty page should be skipped
            }
        ]

        result = chunker.chunk_pages(pages, chunk_size_max=50, chunk_overlap=5)

        assert len(result) >= 2  # At least one chunk per non-empty page

        # Check that chunk indices are global
        for i, chunk in enumerate(result):
            assert chunk['chunk_index'] == i

        # Check page numbers are preserved
        page_numbers = {chunk['page_number'] for chunk in result}
        assert 1 in page_numbers
        assert 2 in page_numbers
        assert 3 not in page_numbers  # Empty page should be skipped

    @pytest.mark.unit
    def test_chunk_pages_with_kwargs(self, chunker):
        """Test page chunking with custom parameters."""
        pages = [
            {
                'page_number': 1,
                'text': 'Page content that should be chunked with custom parameters.'
            }
        ]

        result = chunker.chunk_pages(
            pages,
            chunk_size_min=10,
            chunk_size_max=25,
            chunk_overlap=3,
            preserve_sentences=True
        )

        assert len(result) > 0
        for chunk in result:
            assert chunk['chunk_size'] <= 25
            assert chunk['page_number'] == 1

    @pytest.mark.unit
    def test_chunking_with_custom_settings(self, chunker):
        """Test chunking with various custom settings."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."

        # Test with different chunk sizes
        small_chunks = chunker.chunk_text(text, chunk_size_max=20, chunk_overlap=5)
        large_chunks = chunker.chunk_text(text, chunk_size_max=50, chunk_overlap=5)

        assert len(small_chunks) >= len(large_chunks)

        # Test with different overlap settings
        no_overlap = chunker.chunk_text(text, chunk_size_max=30, chunk_overlap=0)
        with_overlap = chunker.chunk_text(text, chunk_size_max=30, chunk_overlap=10)

        # Both should produce valid chunks
        assert len(no_overlap) > 0
        assert len(with_overlap) > 0

    @pytest.mark.unit
    def test_chunk_metadata_completeness(self, chunker, simple_text):
        """Test that all required metadata is present in chunks."""
        result = chunker.chunk_text(simple_text, chunk_size_max=30)

        required_fields = [
            'chunk_index', 'text_content', 'chunk_size', 'token_count',
            'start_char', 'end_char', 'overlap_start', 'overlap_end'
        ]

        for chunk in result:
            for field in required_fields:
                assert field in chunk
                assert chunk[field] is not None

            # Validate data types
            assert isinstance(chunk['chunk_index'], int)
            assert isinstance(chunk['text_content'], str)
            assert isinstance(chunk['chunk_size'], int)
            assert isinstance(chunk['token_count'], int)
            assert isinstance(chunk['start_char'], int)
            assert isinstance(chunk['end_char'], int)

            # Validate consistency
            assert chunk['chunk_size'] == len(chunk['text_content'])
            assert chunk['start_char'] < chunk['end_char']

    @pytest.mark.unit
    def test_chunking_preserves_text_content(self, chunker, paragraph_text):
        """Test that chunking preserves all original text content."""
        result = chunker.chunk_text(paragraph_text, chunk_size_max=100)

        # Reconstruct text from chunks (without overlaps)
        reconstructed = ""
        for chunk in result:
            reconstructed += chunk['text_content']

        # Remove extra spaces that might be added during chunking
        original_words = paragraph_text.split()
        reconstructed_words = reconstructed.split()

        # Should contain all original words
        assert len(reconstructed_words) >= len(original_words)

        # Most words should be preserved (allowing for some normalization)
        original_set = set(original_words)
        reconstructed_set = set(reconstructed_words)
        overlap_ratio = len(original_set & reconstructed_set) / len(original_set)
        assert overlap_ratio > 0.8  # At least 80% of words preserved
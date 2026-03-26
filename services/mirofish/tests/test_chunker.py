"""Tests for mirofish.graph.chunker."""
from mirofish.graph.chunker import Chunk, chunk_document


class TestChunkDocument:
    def test_empty_input_returns_empty(self):
        assert chunk_document("") == []
        assert chunk_document("   ") == []
        assert chunk_document("\n\n") == []

    def test_short_text_single_chunk(self):
        text = "Hello world."
        chunks = chunk_document(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].index == 0
        assert chunks[0].start_pos == 0

    def test_long_text_multiple_chunks(self):
        # 1000 chars, chunk_size=200, overlap=50 → should produce multiple chunks
        text = "word " * 200  # 1000 chars
        chunks = chunk_document(text, chunk_size=200, overlap=50)
        assert len(chunks) > 1
        # Indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_overlap_between_chunks(self):
        text = "A" * 500
        chunks = chunk_document(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 2
        # Second chunk should start before first chunk ends (overlap)
        assert chunks[1].start_pos < chunks[0].end_pos

    def test_sentence_boundary_splitting(self):
        # Sentence end near chunk boundary should be preferred
        text = "A" * 400 + ". " + "B" * 200
        chunks = chunk_document(text, chunk_size=500, overlap=50)
        # First chunk should end at the sentence boundary
        assert chunks[0].text.endswith(".")

    def test_chunk_positions_cover_text(self):
        text = "The quick brown fox jumps over the lazy dog. " * 20
        chunks = chunk_document(text, chunk_size=100, overlap=20)
        # First chunk starts at 0
        assert chunks[0].start_pos == 0
        # Last chunk reaches near end of text
        assert chunks[-1].end_pos >= len(text) - 50  # allow some slack

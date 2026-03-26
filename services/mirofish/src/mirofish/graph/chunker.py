"""Document chunker — splits text into overlapping chunks for embedding."""
from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk from a document."""
    text: str
    start_pos: int
    end_pos: int
    index: int


def chunk_document(text: str, chunk_size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping chunks by character count.

    Args:
        text: The document text to chunk.
        chunk_size: Target characters per chunk.
        overlap: Characters of overlap between consecutive chunks.

    Returns:
        List of Chunk objects.
    """
    if not text or not text.strip():
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary
        if end < len(text):
            # Look for sentence end within last 20% of chunk
            search_start = start + int(chunk_size * 0.8)
            for boundary in [". ", ".\n", "! ", "? ", "\n\n"]:
                pos = text.find(boundary, search_start, end + 50)
                if pos != -1:
                    end = pos + len(boundary)
                    break

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(Chunk(
                text=chunk_text,
                start_pos=start,
                end_pos=min(end, len(text)),
                index=index,
            ))
            index += 1

        start = end - overlap
        if start >= len(text):
            break

    return chunks

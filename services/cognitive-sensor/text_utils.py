"""Shared text helpers for cognitive-sensor agents.

`chunk_text` previously existed as a byte-identical duplicate in
agent_excavator.py and agent_book_miner.py. Consolidating here removes the
drift risk and delegates the word-window overlap split to
langchain-text-splitters' RecursiveCharacterTextSplitter.

Atlas Law #2 (Assemble First): text chunking is a solved category.
"""
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 300
DEFAULT_CHUNK_OVERLAP = 50


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping word-windows.

    Pre-split short docs short-circuit to a single chunk (preserves the
    original hand-roll's behaviour). Long docs are split by
    RecursiveCharacterTextSplitter with word-counted length, so the
    `chunk_size`/`overlap` parameters retain their word semantics.
    """
    if _word_count(text) <= chunk_size:
        return [text]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=_word_count,
        separators=[" "],
        keep_separator=False,
    )
    return splitter.split_text(text)

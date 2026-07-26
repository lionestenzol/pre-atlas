"""Turn-aware conversation chunker — groups messages by speaker turns, not character count."""
from dataclasses import dataclass


@dataclass
class ConversationChunk:
    convo_id: str
    chunk_index: int
    text: str
    turn_count: int
    start_turn: int
    end_turn: int


def chunk_conversation(
    convo_id: str,
    messages: list[dict],
    turns_per_chunk: int = 5,
    overlap_turns: int = 1,
) -> list[ConversationChunk]:
    """Split a conversation into chunks of N user turns each.

    Groups user messages with their preceding/following assistant responses.
    Returns chunks with speaker-prefixed text for extraction.
    """
    if not messages:
        return []

    # Build turn groups: each "turn" is a user message + surrounding assistant messages
    turns: list[list[dict]] = []
    current_turn: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            continue
        if role == "user" and current_turn:
            turns.append(current_turn)
            current_turn = []
        current_turn.append(msg)

    if current_turn:
        turns.append(current_turn)

    if not turns:
        return []

    # Single chunk for short conversations
    if len(turns) <= turns_per_chunk:
        text = _turns_to_text(turns)
        return [ConversationChunk(
            convo_id=convo_id, chunk_index=0, text=text,
            turn_count=len(turns), start_turn=0, end_turn=len(turns) - 1,
        )]

    # Sliding window with overlap
    chunks = []
    step = max(1, turns_per_chunk - overlap_turns)
    idx = 0
    for start in range(0, len(turns), step):
        end = min(start + turns_per_chunk, len(turns))
        window = turns[start:end]
        text = _turns_to_text(window)
        chunks.append(ConversationChunk(
            convo_id=convo_id, chunk_index=idx, text=text,
            turn_count=len(window), start_turn=start, end_turn=end - 1,
        ))
        idx += 1
        if end >= len(turns):
            break

    return chunks


def get_user_text(messages: list[dict]) -> str:
    """Extract just the user's text from a conversation (for embedding)."""
    parts = []
    for msg in messages:
        if msg.get("role") == "user":
            text = msg.get("text", "").strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _turns_to_text(turns: list[list[dict]]) -> str:
    """Convert turn groups to speaker-prefixed text."""
    lines = []
    for turn in turns:
        for msg in turn:
            role = msg.get("role", "unknown")
            text = msg.get("text", "").strip()
            if text:
                prefix = "[user]" if role == "user" else "[assistant]"
                # Truncate very long assistant messages (keep first 500 chars)
                if role == "assistant" and len(text) > 500:
                    text = text[:500] + "..."
                lines.append(f"{prefix}: {text}")
    return "\n".join(lines)

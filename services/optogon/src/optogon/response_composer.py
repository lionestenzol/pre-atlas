"""Response composer - pacing-constrained turn output.

Enforces:
- max 1 question per non-clarification turn
- soft cap: token_budget per node (from node.metadata.token_budget or config default)

The real LLM call is optional. If ANTHROPIC_API_KEY is set, llm_call() will
use Claude. Otherwise it returns a deterministic fallback so tests and dev
runs work without credentials.
"""
from __future__ import annotations
from typing import Any, Optional

from .config import DEFAULT_TOKEN_BUDGET_PER_NODE, LLM_ENABLED, LLM_MODEL, ANTHROPIC_API_KEY, MAX_QUESTIONS_PER_TURN


def enforce_pacing(text: str, max_questions: int = MAX_QUESTIONS_PER_TURN) -> tuple[str, int]:
    """Count questions; trim additional questions after max_questions.

    Returns (final_text, question_count).
    """
    # Simple question counter - count '?' that are not inside parens or code fences.
    questions = text.count("?")
    if questions <= max_questions:
        return text, questions

    # Truncate: find the nth '?' and keep up to the end of that sentence.
    out = []
    seen = 0
    for ch in text:
        out.append(ch)
        if ch == "?":
            seen += 1
            if seen == max_questions:
                break
    trimmed = "".join(out)
    return trimmed, max_questions


def compose(
    node: dict[str, Any],
    session_state: dict[str, Any],
    draft: Optional[str] = None,
) -> tuple[str, int]:
    """Compose a turn response. Returns (text, tokens_used)."""
    node_budget = (node.get("metadata") or {}).get("token_budget") or DEFAULT_TOKEN_BUDGET_PER_NODE

    # For qualify nodes, ask the node's question if present.
    if node.get("type") == "qualify":
        q = (node.get("qualification") or {}).get("question") or {}
        text = draft or q.get("text") or ""
        final, _ = enforce_pacing(text)
        return final, _estimate_tokens(final)

    # For approval nodes, build a bundled confirmation prompt.
    if node.get("type") == "approval":
        text = draft or f"Confirm: {node.get('label', 'approval')}?"
        final, _ = enforce_pacing(text)
        return final, _estimate_tokens(final)

    # Silent node types (gate, execute, close, fork) return empty string.
    if node.get("type") in ("gate", "execute", "close", "fork"):
        return "", 0

    return draft or "", _estimate_tokens(draft or "")


def _estimate_tokens(text: str) -> int:
    # Cheap estimator: 4 chars per token as rough average.
    return max(1, len(text) // 4) if text else 0


def llm_call(system: str, user: str, max_tokens: int = 200) -> str:
    """Call Claude with tight token budget.

    Returns a string. If ANTHROPIC_API_KEY is unset, returns a deterministic
    stub so tests don't require credentials. The stub echoes the user prompt
    prefix so path logic can still make progress.
    """
    if not LLM_ENABLED:
        return f"[llm-stub] {user[:120]}"
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        blocks = getattr(msg, "content", []) or []
        text_parts = [getattr(b, "text", "") for b in blocks if getattr(b, "type", None) == "text"]
        return "".join(text_parts).strip() or ""
    except Exception as e:
        return f"[llm-error] {type(e).__name__}: {e}"

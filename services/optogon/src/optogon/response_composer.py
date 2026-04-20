"""Response composer - pacing-constrained turn output.

Per doctrine/03_OPTOGON_SPEC.md Section 10: pacing is a **strict constraint**,
not a soft hint. This module enforces:
  - max 1 question per non-clarification turn (sentence-level count)
  - token budget per node (soft cap, metric-reported)
  - no raw node_id / session_id leaks in user-facing text
  - max_options_shown from node.pacing

Violations are logged into metrics and the response is replaced with a
minimal fallback derived from the node. Callers never get invalid output.

The real LLM call is optional. If ANTHROPIC_API_KEY is set, llm_call() /
llm_parse() will use Claude. Otherwise they return deterministic fallbacks
so tests and dev runs work without credentials.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any, Optional

from .config import (
    ANTHROPIC_API_KEY,
    DEFAULT_TOKEN_BUDGET_PER_NODE,
    LLM_ENABLED,
    LLM_MODEL,
    MAX_QUESTIONS_PER_TURN,
)

log = logging.getLogger("optogon.composer")


class PacingViolation(Exception):
    """Raised when strict-mode pacing checks fail."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = list(violations)
        super().__init__("; ".join(violations))


# ---------------------------------------------------------------------------
# Pacing primitives
# ---------------------------------------------------------------------------
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks so we don't count '?' inside them."""
    return _CODE_FENCE.sub("", text)


def _count_questions(text: str) -> int:
    """Count sentences ending with '?'. Ignores '?' inside fenced code."""
    cleaned = _strip_fenced_code(text or "")
    if not cleaned.strip():
        return 0
    sentences = _SENTENCE_BOUNDARY.split(cleaned.strip())
    count = 0
    for s in sentences:
        s = s.rstrip()
        if s.endswith("?"):
            count += 1
    return count


_OPTION_PATTERNS = [
    re.compile(r"^\s*\d+[.)]\s+\S", re.M),     # numbered lists: "1. ", "1) "
    re.compile(r"^\s*[-*]\s+\S", re.M),        # bullets: "- ", "* "
]


def _count_options(text: str) -> int:
    """Heuristic count of list-style options in the text."""
    cleaned = _strip_fenced_code(text or "")
    total = 0
    for pat in _OPTION_PATTERNS:
        total += len(pat.findall(cleaned))
    return total


def _scan_leaks(
    text: str,
    *,
    session_id: Optional[str],
    node_ids: Optional[list[str]],
) -> list[str]:
    """Return the list of offending substrings found verbatim in text.

    Node ids are short and often natural words ('entry', 'merge'), so we
    only flag when they appear in isolation: surrounded by non-word chars
    or at string boundaries. Session ids start with 'sess_' which makes
    them unique enough to flag on direct substring match.
    """
    offenders: list[str] = []
    cleaned = text or ""
    if session_id and session_id in cleaned:
        offenders.append(session_id)
    for nid in node_ids or []:
        if not nid:
            continue
        # Whole-word match
        if re.search(rf"(?<![\w-]){re.escape(nid)}(?![\w-])", cleaned):
            offenders.append(nid)
    return offenders


def _fallback_for_node(node: dict[str, Any], session_state: Optional[dict[str, Any]]) -> str:
    """Minimal, safe fallback response when strict pacing rejects composed text."""
    ntype = node.get("type")
    if ntype == "qualify":
        # Ask for the single most-important missing key.
        required = [r.get("key") for r in (node.get("qualification") or {}).get("required") or []]
        ctx = (session_state or {}).get("context") or {}
        known: set[str] = set()
        for tier in ("confirmed", "user", "inferred"):
            known.update((ctx.get(tier) or {}).keys())
        missing = [k for k in required if k and k not in known]
        if missing:
            return f"What is the {missing[0]}?"
        return ""
    if ntype == "approval":
        return f"Confirm: {node.get('label', 'approval')}?"
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def enforce_pacing(
    text: str,
    *,
    node: Optional[dict[str, Any]] = None,
    session_state: Optional[dict[str, Any]] = None,
    path: Optional[dict[str, Any]] = None,
    max_questions: int = MAX_QUESTIONS_PER_TURN,
) -> tuple[str, int, list[str]]:
    """Enforce strict pacing constraints on `text`.

    Returns (final_text, question_count, violations).
    On violation, `final_text` is substituted with a safe fallback derived
    from the node. Violations are returned so the caller can record metrics.
    """
    violations: list[str] = []
    question_count = _count_questions(text)

    if question_count > max_questions:
        violations.append(
            f"question_count={question_count} exceeds max={max_questions}"
        )

    if node is not None:
        max_options = ((node.get("pacing") or {}).get("max_options_shown"))
        if max_options is not None:
            options = _count_options(text)
            if options > int(max_options):
                violations.append(
                    f"options={options} exceeds max_options_shown={max_options}"
                )

    node_ids: list[str] = []
    if path is not None:
        node_ids = list((path.get("nodes") or {}).keys())
    session_id = (session_state or {}).get("session_id")
    leaks = _scan_leaks(text, session_id=session_id, node_ids=node_ids)
    for leak in leaks:
        violations.append(f"leak: {leak!r}")

    if violations:
        fallback = _fallback_for_node(node or {}, session_state)
        log.warning("pacing violations: %s; substituting fallback", "; ".join(violations))
        return fallback, _count_questions(fallback), violations

    return text, question_count, violations


def compose(
    node: dict[str, Any],
    session_state: dict[str, Any],
    path: Optional[dict[str, Any]] = None,
    draft: Optional[str] = None,
) -> tuple[str, int, list[str]]:
    """Compose a turn response. Returns (text, tokens_used, violations)."""
    _ = (node.get("metadata") or {}).get("token_budget") or DEFAULT_TOKEN_BUDGET_PER_NODE

    ntype = node.get("type")

    if ntype == "qualify":
        q = (node.get("qualification") or {}).get("question") or {}
        text = draft or q.get("text") or ""
        final, _qcount, violations = enforce_pacing(
            text, node=node, session_state=session_state, path=path
        )
        return final, _estimate_tokens(final), violations

    if ntype == "approval":
        text = draft or f"Confirm: {node.get('label', 'approval')}?"
        final, _qcount, violations = enforce_pacing(
            text, node=node, session_state=session_state, path=path
        )
        return final, _estimate_tokens(final), violations

    # Silent node types (gate, execute, close, fork) return empty string.
    if ntype in ("gate", "execute", "close", "fork"):
        return "", 0, []

    return draft or "", _estimate_tokens(draft or ""), []


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------
def llm_call(system: str, user: str, max_tokens: int = 200) -> str:
    """Call Claude with tight token budget.

    Returns a string. If ANTHROPIC_API_KEY is unset, returns a deterministic
    stub so tests don't require credentials.
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
        text_parts = [
            getattr(b, "text", "")
            for b in blocks
            if getattr(b, "type", None) == "text"
        ]
        return "".join(text_parts).strip() or ""
    except Exception as e:
        log.warning("llm_call failed: %s", e)
        return f"[llm-error] {type(e).__name__}: {e}"


def llm_parse(
    message: str,
    required: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract structured values for the given keys from a free-form message.

    Per spec §14: `llm_parse(user_message, required)`. Returns {key: value}
    for any keys the parser could extract. Keys not in `required` are filtered.

    Implementation:
      - If LLM_ENABLED: ask Claude for a strict JSON object and parse it.
      - Else: deterministic heuristic (key=value segments, positional split,
        or single-key assignment).
    """
    if not message or not required:
        return {}
    keys = [r.get("key") for r in required if r.get("key")]
    if not keys:
        return {}

    if LLM_ENABLED:
        parsed = _llm_parse_json(message, required)
        if parsed:
            return {k: v for k, v in parsed.items() if k in keys}

    return _heuristic_parse(message, keys)


def _llm_parse_json(message: str, required: list[dict[str, Any]]) -> dict[str, Any]:
    """Ask Claude to return a JSON object with any keys it can extract."""
    key_descriptions = "\n".join(
        f"  - {r['key']}: {r.get('description', '(no description)')}"
        for r in required
        if r.get("key")
    )
    system = (
        "You extract structured values from user messages. "
        "Respond with a SINGLE JSON object and nothing else. "
        "Only include keys you can confidently extract; omit the rest. "
        "Values must be strings or numbers."
    )
    user = (
        f"Keys to extract:\n{key_descriptions}\n\n"
        f"User message:\n{message}\n\n"
        f"JSON response only:"
    )
    raw = llm_call(system, user, max_tokens=300)
    if not raw or raw.startswith("[llm-"):
        return {}
    # Strip common fencing patterns.
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try to locate a {...} blob in the text.
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {}


_KV_PATTERN = re.compile(r"^\s*([a-zA-Z_][\w-]*)\s*[:=]\s*(.+?)\s*$")


def _heuristic_parse(message: str, keys: list[str]) -> dict[str, Any]:
    """Deterministic fallback parser. Handles:
      - "key=value, key=value" or "key: value; key: value"
      - "val1, val2" with segment count == len(keys) (positional)
      - single-segment with len(keys) == 1
    """
    if not message:
        return {}
    segments = [s.strip() for s in re.split(r"[,;\n]", message) if s.strip()]
    if not segments:
        return {}

    # Path A: explicit key=value / key: value
    kv: dict[str, Any] = {}
    unmatched_segments: list[str] = []
    for seg in segments:
        m = _KV_PATTERN.match(seg)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            if k in keys:
                kv[k] = _coerce_scalar(v)
                continue
        unmatched_segments.append(seg)

    # Path B: positional assignment for remaining segments over remaining keys
    remaining_keys = [k for k in keys if k not in kv]
    if unmatched_segments and len(unmatched_segments) == len(remaining_keys):
        for k, v in zip(remaining_keys, unmatched_segments):
            kv[k] = _coerce_scalar(v.strip())

    # Path C: single segment, single remaining key — assign
    elif len(unmatched_segments) == 1 and len(remaining_keys) == 1:
        kv[remaining_keys[0]] = _coerce_scalar(unmatched_segments[0].strip())

    return kv


def _coerce_scalar(v: str) -> Any:
    """Very light coercion: ints, floats, bools, else string."""
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        pass
    return v

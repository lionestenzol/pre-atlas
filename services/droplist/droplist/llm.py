"""LLM layer + call logging.

Design rule: the system must RUN with zero dependencies and zero API keys.
So the default backend is `heuristic` — deterministic rules that need no model.
If ANTHROPIC_API_KEY is set AND the SDK is importable AND DROPLIST_LLM=anthropic,
the real model is used instead. Either way, every call is logged to
llm_calls.jsonl because cost/token accounting is part of the architecture.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from . import storage

BACKEND = os.environ.get("DROPLIST_LLM", "heuristic")  # heuristic | anthropic
MODEL = os.environ.get("DROPLIST_MODEL", "claude-sonnet-4-20250514")


def _preview(text: str, n: int = 200) -> str:
    text = text or ""
    return text[:n]


def log_call(
    purpose: str,
    model: str,
    input_hash: str,
    prompt_preview: str,
    response_preview: str,
    latency_ms: int,
    status: str,
    estimated_cost: float = 0.0,
) -> str:
    call_id = "call_" + uuid.uuid4().hex[:12]
    storage.append(
        storage.LLM_CALLS,
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "call_id": call_id,
            "purpose": purpose,
            "model": model,
            "input_hash": input_hash,
            "prompt_preview": _preview(prompt_preview),
            "response_preview": _preview(response_preview),
            "latency_ms": latency_ms,
            "estimated_cost": round(estimated_cost, 6),
            "status": status,
        },
    )
    return call_id


def anthropic_available() -> bool:
    if BACKEND != "anthropic":
        return False
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def call_json(purpose: str, system: str, user: str, input_hash: str) -> dict[str, Any] | None:
    """Call the real model and parse a JSON object response.

    Returns None on any failure so callers fall back to heuristics.
    Only used when anthropic_available() is True.
    """
    t0 = time.time()
    try:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        cleaned = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        usage = getattr(resp, "usage", None)
        cost = 0.0
        if usage:
            # rough Sonnet pricing: $3/Mtok in, $15/Mtok out
            cost = usage.input_tokens / 1e6 * 3 + usage.output_tokens / 1e6 * 15
        log_call(purpose, MODEL, input_hash, user, text, int((time.time() - t0) * 1000), "success", cost)
        return data
    except Exception as e:  # noqa: BLE001 - any failure -> heuristic fallback
        log_call(purpose, MODEL, input_hash, user, f"ERROR: {e}", int((time.time() - t0) * 1000), "error")
        return None

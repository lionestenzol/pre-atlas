"""LLM layer + call logging.

Design rule: the system must RUN with zero dependencies and zero API keys.
So the default backend is `heuristic` — deterministic rules that need no model.
If ANTHROPIC_API_KEY is set AND the SDK is importable AND DROPLIST_LLM=anthropic,
the real model is used instead. Either way, every call is logged to
llm_calls.jsonl because cost/token accounting is part of the architecture.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any

from . import storage

BACKEND = os.environ.get("DROPLIST_LLM", "heuristic")  # heuristic | anthropic
MODEL = os.environ.get("DROPLIST_MODEL", "claude-sonnet-4-20250514")

# ---------------------------------------------------------------------------
# Swappable LLM registry (Task B, litellm). One `completion(model=...)` call
# covers Anthropic / OpenAI / Gemini / OpenRouter / Ollama-local, so the user
# can pick a provider from the UI instead of being Anthropic-locked. Keys stay
# server-side (litellm reads them straight from env); `available_models()` only
# advertises providers whose key is present (or local Ollama if configured), so
# the picker never offers a model the server can't actually run.
# See ~/.claude/rules/common/assemble-first.md (litellm, not a 2nd HTTP path).
# ---------------------------------------------------------------------------
PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "key_env": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-20241022"],
    },
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
    },
    "openrouter": {
        "key_env": "OPENROUTER_API_KEY",
        "models": ["openrouter/auto", "deepseek/deepseek-chat"],
    },
    "ollama": {
        # Local — no key. Only offered when OLLAMA_BASE_URL is set so we never
        # advertise models against a daemon that isn't running.
        "key_env": None,
        "base_env": "OLLAMA_BASE_URL",
        "models": ["llama3", "qwen2.5", "mistral"],
    },
}


def _model_id(provider: str, model: str) -> str:
    """Fully-qualified litellm model string the UI sends back (``provider/model``)."""
    return model if "/" in model else f"{provider}/{model}"


def available_models() -> list[dict[str, str]]:
    """Providers the server can actually use right now (key present, or local).

    The picker is built from this, so a user can only choose a model the server
    has credentials for — no silent 401s.
    """
    out: list[dict[str, str]] = []
    for prov, cfg in PROVIDERS.items():
        key_env = cfg.get("key_env")
        if key_env:
            if not os.environ.get(key_env):
                continue
        elif not os.environ.get(cfg.get("base_env", "")):
            continue  # local provider needs its base URL configured
        for m in cfg["models"]:
            out.append({"provider": prov, "model": m, "id": _model_id(prov, m)})
    return out


def default_model() -> str | None:
    """First available model id, honoring DROPLIST_MODEL if it's available."""
    avail = available_models()
    if not avail:
        return None
    want = os.environ.get("DROPLIST_MODEL")
    if want:
        for m in avail:
            if m["id"] == want or m["model"] == want:
                return m["id"]
    return avail[0]["id"]


def complete(
    model: str,
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int = 1024,
    purpose: str = "complete",
) -> dict[str, Any]:
    """Provider-agnostic completion via litellm.

    Returns an **Anthropic-shaped** payload (``{"content":[{"type":"text",...}]}``)
    so the existing UI parse (``data.content[].text``) is unchanged regardless of
    which provider actually answered. Every call is logged to llm_calls.jsonl with
    litellm's per-model cost. Raises on failure (the caller maps it to an HTTP code).
    """
    import litellm

    litellm.drop_params = True  # silently drop kwargs a given provider doesn't support
    t0 = time.time()
    msgs: list[dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    kwargs: dict[str, Any] = {"model": model, "messages": msgs, "max_tokens": max_tokens}
    if model.startswith("ollama/"):
        base = os.environ.get("OLLAMA_BASE_URL")
        if base:
            kwargs["api_base"] = base
    input_hash = hashlib.sha256(json.dumps(msgs, sort_keys=True).encode()).hexdigest()[:16]
    user_preview = json.dumps(messages)[:200]
    try:
        resp = litellm.completion(**kwargs)
        text = resp.choices[0].message.content or ""
        try:
            cost = float(litellm.completion_cost(completion_response=resp) or 0.0)
        except Exception:  # noqa: BLE001 — cost is best-effort, never fatal
            cost = 0.0
        log_call(purpose, model, input_hash, user_preview, text, int((time.time() - t0) * 1000), "success", cost)
        return {"content": [{"type": "text", "text": text}], "model": model, "estimated_cost": round(cost, 6)}
    except Exception as e:  # noqa: BLE001 — surfaced to the route as a 502
        log_call(purpose, model, input_hash, user_preview, f"ERROR: {e}", int((time.time() - t0) * 1000), "error")
        raise


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

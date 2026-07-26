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
import shutil
import subprocess
import time
import urllib.error
import urllib.request
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
        # Local — no key. Auto-detected: if a daemon answers on localhost:11434 the
        # provider lights up with whatever models are ACTUALLY pulled (queried via
        # /api/tags), not a hardcoded list. OLLAMA_BASE_URL still overrides the host.
        "key_env": None,
        "base_env": "OLLAMA_BASE_URL",
        "default_base": "http://localhost:11434",
        "models": [],  # populated dynamically from /api/tags
        "dynamic": "ollama",
    },
    "claude-cli": {
        # Uses the local `claude` binary's existing Max-subscription auth. No API
        # key, no per-token billing. Auto-detected: appears when `claude` is on
        # PATH. Model ids: claude-cli/sonnet | claude-cli/opus | claude-cli/haiku.
        "key_env": None,
        "detect": "claude-cli",
        "models": ["sonnet", "opus", "haiku"],
    },
}


# ---------------------------------------------------------------------------
# Local-provider probes (Ollama + Claude CLI). Cached with a short TTL so
# available_models() stays fast when the picker polls it.
# ---------------------------------------------------------------------------
_PROBE_TTL_S = 15.0
_probe_cache: dict[str, tuple[float, Any]] = {}


def _cached(key: str, ttl: float, fn):
    now = time.time()
    hit = _probe_cache.get(key)
    if hit and (now - hit[0]) < ttl:
        return hit[1]
    val = fn()
    _probe_cache[key] = (now, val)
    return val


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL") or PROVIDERS["ollama"]["default_base"]


def _ollama_models() -> list[str]:
    """Query the local Ollama daemon for actually-pulled models. Empty on any failure."""
    def probe() -> list[str]:
        base = _ollama_base().rstrip("/")
        try:
            req = urllib.request.Request(f"{base}/api/tags", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:  # noqa: S310 — local http only
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return []
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    return _cached("ollama_models", _PROBE_TTL_S, probe)


def _claude_cli_available() -> bool:
    """True if the `claude` binary is on PATH. Doesn't verify login (that surfaces at call time)."""
    def probe() -> bool:
        return shutil.which("claude") is not None
    return _cached("claude_cli_available", _PROBE_TTL_S, probe)


def _model_id(provider: str, model: str) -> str:
    """Fully-qualified litellm model string the UI sends back (``provider/model``)."""
    return model if "/" in model else f"{provider}/{model}"


def available_models() -> list[dict[str, str]]:
    """Providers the server can actually use right now (key present, or local).

    The picker is built from this, so a user can only choose a model the server
    has credentials for — no silent 401s. Local providers are probed:
    Ollama's models come from ``/api/tags`` on the running daemon; Claude CLI
    lights up when the `claude` binary is on PATH.
    """
    out: list[dict[str, str]] = []
    for prov, cfg in PROVIDERS.items():
        dynamic = cfg.get("dynamic")
        detect = cfg.get("detect")
        key_env = cfg.get("key_env")
        models: list[str] = list(cfg.get("models", []))
        if dynamic == "ollama":
            models = _ollama_models()
            if not models:
                continue  # daemon unreachable or nothing pulled
        elif detect == "claude-cli":
            if not _claude_cli_available():
                continue
        elif key_env:
            if not os.environ.get(key_env):
                continue
        elif cfg.get("base_env"):
            if not os.environ.get(cfg["base_env"]):
                continue  # non-ollama local provider needs its base URL
        for m in models:
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


# Cost estimation fallback ----------------------------------------------------
# litellm.completion_cost is the primary source, but it returns 0 for models it
# has no price map for (e.g. openrouter/auto) and the direct-anthropic call_json
# path has no litellm response at all. A spend CEILING must never under-count, so
# unmapped *paid* models fall back to this table (over-counting is the safe
# direction); local ollama/* is genuinely free.
# See ~/.claude/rules/common/code-as-furniture.md — budget bypass fixed inline.
_RATES = {  # $/Mtok (input, output); ordered so longer keys match before prefixes
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-haiku": (0.80, 4.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4": (5.0, 15.0),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini": (0.50, 1.50),
}
_FALLBACK_RATE = (5.0, 15.0)  # conservative default for any unmapped paid model


def _rate_for(model: str) -> tuple[float, float]:
    m = (model or "").lower()
    for key, rate in _RATES.items():
        if key in m:
            return rate
    return _FALLBACK_RATE


def _usage_cost(model: str, in_tok: int, out_tok: int) -> float:
    """Token-usage * per-model rate, in dollars. Used when litellm can't price."""
    rin, rout = _rate_for(model)
    return (in_tok or 0) / 1e6 * rin + (out_tok or 0) / 1e6 * rout


# ---------------------------------------------------------------------------
# Claude CLI subprocess adapter. `claude -p` is non-interactive and uses the
# user's already-authenticated Max session, so no API key changes hands and
# spend is covered by the subscription. We flatten the message list into a
# single prompt and shape the reply into the Anthropic content format the UI
# already parses. Any non-zero exit surfaces as an exception the caller maps
# to a 502. Timeout is generous because first-boot of the CLI can be slow.
# ---------------------------------------------------------------------------
_CLAUDE_CLI_TIMEOUT_S = 120.0


def _flatten_messages(messages: list[dict[str, Any]], system: str | None) -> str:
    """Turn the OpenAI-style message list into a single prompt string for `claude -p`."""
    parts: list[str] = []
    if system:
        parts.append(f"[system]\n{system}\n")
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "".join(
                (b.get("text", "") if isinstance(b, dict) else str(b)) for b in content
            )
        parts.append(f"[{role}]\n{content}\n")
    return "\n".join(parts).strip()


def _complete_claude_cli(
    model: str,
    messages: list[dict[str, Any]],
    system: str | None,
    max_tokens: int,  # noqa: ARG001 — CLI has no --max-tokens equivalent
    purpose: str,
) -> dict[str, Any]:
    t0 = time.time()
    binary = shutil.which("claude")
    prompt = _flatten_messages(messages, system)
    input_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    user_preview = json.dumps(messages)[:200]
    if not binary:
        log_call(purpose, model, input_hash, user_preview, "ERROR: claude binary not on PATH",
                 int((time.time() - t0) * 1000), "error")
        raise RuntimeError("claude binary not found on PATH")
    # model tail (e.g. "claude-cli/sonnet" -> "sonnet"); claude accepts short aliases
    tail = model.split("/", 1)[1] if "/" in model else model
    cmd = [binary, "-p", "--model", tail, prompt]
    try:
        result = subprocess.run(  # noqa: S603 — cmd list, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=_CLAUDE_CLI_TIMEOUT_S,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        log_call(purpose, model, input_hash, user_preview, f"ERROR: timeout after {_CLAUDE_CLI_TIMEOUT_S}s",
                 int((time.time() - t0) * 1000), "error")
        raise RuntimeError(f"claude cli timed out after {_CLAUDE_CLI_TIMEOUT_S}s") from e
    if result.returncode != 0:
        err = (result.stderr or "").strip()[:400] or "non-zero exit"
        log_call(purpose, model, input_hash, user_preview, f"ERROR: {err}",
                 int((time.time() - t0) * 1000), "error")
        raise RuntimeError(f"claude cli failed (exit {result.returncode}): {err}")
    text = (result.stdout or "").strip()
    log_call(purpose, model, input_hash, user_preview, text,
             int((time.time() - t0) * 1000), "success", 0.0)
    return {"content": [{"type": "text", "text": text}], "model": model, "estimated_cost": 0.0}


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
    # ---- claude-cli branch: uses the local `claude` binary's subscription auth.
    # Bypasses litellm entirely; cost is $0 (covered by the Max plan). Latency is
    # higher than an SDK call because a subprocess is spawned per completion.
    if model.startswith("claude-cli/"):
        return _complete_claude_cli(model, messages, system, max_tokens, purpose)

    import litellm

    litellm.drop_params = True  # silently drop kwargs a given provider doesn't support
    t0 = time.time()
    msgs: list[dict[str, Any]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    kwargs: dict[str, Any] = {"model": model, "messages": msgs, "max_tokens": max_tokens}
    if model.startswith("ollama/"):
        # honor OLLAMA_BASE_URL if set, otherwise localhost:11434 (matches the
        # auto-detect in available_models so the picker and the call agree)
        kwargs["api_base"] = _ollama_base()
    input_hash = hashlib.sha256(json.dumps(msgs, sort_keys=True).encode()).hexdigest()[:16]
    user_preview = json.dumps(messages)[:200]
    try:
        resp = litellm.completion(**kwargs)
        text = resp.choices[0].message.content or ""
        try:
            cost = float(litellm.completion_cost(completion_response=resp) or 0.0)
        except Exception:  # noqa: BLE001 — cost is best-effort, never fatal
            cost = 0.0
        if cost <= 0.0 and not model.startswith("ollama/"):
            # litellm has no price map for this paid model (e.g. openrouter/auto).
            # Logging 0 would let it slip past the daily budget ceiling forever, so
            # estimate from token usage. Over-counting is the safe direction.
            u = getattr(resp, "usage", None)
            if u is not None:
                cost = _usage_cost(model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
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


# ---------------------------------------------------------------------------
# Provider-agnostic gate + JSON completion. Wraps `complete()` (which already
# routes claude-cli / anthropic / openai / gemini / openrouter / ollama through
# one call) with the same "return None on failure so caller falls back to the
# heuristic" contract that call_json (Anthropic-only) has always had. This is
# what makes the DAG executor path (agents.run_agent), the chain runner, and
# the classifier honour the same model picker the workshop chat uses, instead
# of only firing when ANTHROPIC_API_KEY + DROPLIST_LLM=anthropic are both set.
#
# The BACKEND env gate is preserved from anthropic_available(): heuristic mode
# stays the default so tests, first-runs, and offline dev do zero I/O and cost
# nothing. Opt in with DROPLIST_LLM in {anthropic, auto, any} — 'anthropic'
# still forces the old Anthropic-only path (backward compat), 'auto' / 'any'
# route through the picker (default_model → complete → claude-cli / litellm).
# See ~/.claude/rules/common/code-as-furniture.md — no half-wired executor.
# ---------------------------------------------------------------------------
_LIVE_BACKENDS = frozenset({"anthropic", "auto", "any"})


def model_available(model: str | None = None) -> bool:
    """True when a provider-agnostic LLM call is wireable right now.

    Gated by DROPLIST_LLM so `claude` merely being on PATH does not silently
    turn every DAG node into a subprocess spawn — the zero-key, zero-surprise
    default is preserved. With no `model` arg, returns True iff a live backend
    is opted in AND default_model() resolves. With a model id, must ALSO match
    available_models().
    """
    if BACKEND not in _LIVE_BACKENDS:
        return False
    if model:
        return any(m["id"] == model for m in available_models())
    return default_model() is not None


def complete_json(
    purpose: str,
    system: str,
    user: str,
    input_hash: str,  # noqa: ARG001 — logged by complete() via its own input_hash
    model: str | None = None,
) -> dict[str, Any] | None:
    """Provider-agnostic JSON call. Same None-on-failure contract as call_json.

    Uses the picker-visible default (honouring DROPLIST_MODEL); pass an explicit
    model id to override. Strips ```json fences before parsing so a chatty model
    that wraps its reply still round-trips.
    """
    m = model or default_model()
    if not m:
        return None
    try:
        resp = complete(
            model=m,
            messages=[{"role": "user", "content": user}],
            system=system,
            max_tokens=1024,
            purpose=purpose,
        )
        text = "".join(
            b.get("text", "") for b in resp.get("content", []) if isinstance(b, dict)
        )
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)
    except Exception:  # noqa: BLE001 — any failure -> caller falls back to heuristic
        return None


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
            # per-MODEL pricing — NOT a hardcoded Sonnet rate (Opus output is 5x).
            cost = _usage_cost(MODEL, usage.input_tokens, usage.output_tokens)
        log_call(purpose, MODEL, input_hash, user, text, int((time.time() - t0) * 1000), "success", cost)
        return data
    except Exception as e:  # noqa: BLE001 - any failure -> heuristic fallback
        log_call(purpose, MODEL, input_hash, user, f"ERROR: {e}", int((time.time() - t0) * 1000), "error")
        return None

"""HTTP client for delta-kernel's UserPreferenceStore.

Per doctrine/04_BUILD_PLAN.md Phase 4. Optogon pulls preferences on session
start and pushes close signals after path close. Falls back to no-op if
delta-kernel is unreachable (dev mode often has delta-kernel off).
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any, Optional

try:
    import httpx
except ImportError:  # httpx is a declared dep; fall back to urllib for safety
    httpx = None

from .config import AUTO_CONFIRM_CONFIDENCE

log = logging.getLogger("optogon.preferences")

# Can be overridden in tests via env var
_DELTA_BASE = os.environ.get("DELTA_KERNEL_BASE", "http://127.0.0.1:3001")
_TIMEOUT_S = 3.0


def _token() -> Optional[str]:
    """Fetch the dev auth token from delta-kernel. Returns None if unavailable."""
    if httpx is None:
        return None
    try:
        r = httpx.get(f"{_DELTA_BASE}/api/auth/token", timeout=_TIMEOUT_S)
        if r.status_code != 200:
            return None
        return (r.json() or {}).get("token")
    except Exception:
        return None


def _auth_headers() -> dict[str, str]:
    tok = _token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def fetch_preferences() -> dict[str, Any]:
    """Return a flat {key: value} dict of preferences. Empty dict on failure.

    Preferences with confidence >= AUTO_CONFIRM_CONFIDENCE get promoted to
    the 'confirmed' tier downstream; below that they go to 'inferred'.
    """
    if httpx is None:
        return {}
    try:
        r = httpx.get(
            f"{_DELTA_BASE}/api/atlas/preferences",
            headers=_auth_headers(),
            timeout=_TIMEOUT_S,
        )
        if r.status_code != 200:
            log.debug("preferences fetch returned %s", r.status_code)
            return {}
        store = (r.json() or {}).get("store") or {}
        out: dict[str, Any] = {}
        for pref in store.get("preferences") or []:
            key = pref.get("key")
            if not key:
                continue
            out[key] = {
                "value": pref.get("value"),
                "confidence": float(pref.get("confidence", 0.0)),
                "source": pref.get("source", "inferred"),
            }
        return out
    except Exception as e:
        log.debug("preferences fetch failed: %s", e)
        return {}


def post_close_signal(close_signal: dict[str, Any]) -> bool:
    """POST a CloseSignal.v1 to delta-kernel. Returns True on 202."""
    if httpx is None:
        return False
    try:
        r = httpx.post(
            f"{_DELTA_BASE}/api/atlas/close-signal",
            headers={**_auth_headers(), "Content-Type": "application/json"},
            content=json.dumps(close_signal),
            timeout=_TIMEOUT_S,
        )
        if r.status_code == 202:
            return True
        log.warning("close-signal POST returned %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.debug("close-signal POST failed: %s", e)
        return False


def inject_preferences_into_context(
    context: dict[str, dict[str, Any]],
    preferences: dict[str, Any],
) -> int:
    """Inject each preference into context at tier based on confidence.

    Respects hierarchy: if a higher-priority tier already has the key, skip.
    Returns count of keys actually injected.
    """
    injected = 0
    for key, entry in (preferences or {}).items():
        value = entry.get("value")
        confidence = entry.get("confidence", 0.0)
        if value is None:
            continue
        # Don't overwrite confirmed values
        if key in context.get("confirmed", {}):
            continue
        tier = "confirmed" if confidence >= AUTO_CONFIRM_CONFIDENCE else "inferred"
        # Don't demote: if already at a higher tier, skip
        if tier == "inferred" and key in context.get("user", {}):
            continue
        context.setdefault(tier, {})[key] = value
        injected += 1
    return injected

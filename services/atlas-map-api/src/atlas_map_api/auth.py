"""Shared-secret guard for atlas-map-api's state-changing endpoints.

The map API now mutates real files (droplist packets) and spawns/kills OS
processes (start/stop/restart). It binds 127.0.0.1 and CORS is restricted to the
known viewer origins, which covers casual local use — but a same-machine rogue
process (no CORS) or a DNS-rebind browser tab could still drive the POSTs. This
module adds a shared secret every POST must present as `X-Atlas-Token`.

Token resolution (first hit wins):
  1. ATLAS_WRITE_TOKEN env var
  2. <repo_root>/.atlas-write-token  (gitignored)
  3. freshly generated (secrets.token_urlsafe) + written to that file

The custom header forces a CORS preflight for cross-origin POSTs, so a
DNS-rebind tab at a foreign origin can't even send the request (preflight fails
against the restricted allow_origins) — and without the secret it gets a 401
regardless. A rogue local process must specifically read the gitignored file to
forge a request, the same bar as reading any other local secret.

See ~/.claude/rules/common/code-as-furniture.md — HIGH security finding fixed
inline (2026-06-20), not documented-and-left.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

TOKEN_ENV = "ATLAS_WRITE_TOKEN"
TOKEN_FILENAME = ".atlas-write-token"

# Resolved once per process and reused. Set by load_or_create_token() (called at
# startup) or lazily by the dependency so tests / bare TestClient still work.
_active_token: str | None = None


def _token_file(repo_root: Path) -> Path:
    return repo_root / TOKEN_FILENAME


def load_or_create_token(repo_root: Path) -> str:
    """Resolve the write token, generating + persisting one if none exists.

    Idempotent: repeated calls return the same value (env or on-disk), and only
    generate when neither is present. Caches the result in-process.
    """
    global _active_token

    env = os.environ.get(TOKEN_ENV)
    if env and env.strip():
        _active_token = env.strip()
        return _active_token

    f = _token_file(repo_root)
    try:
        if f.is_file():
            existing = f.read_text(encoding="utf-8").strip()
            if existing:
                _active_token = existing
                return _active_token
    except OSError:
        pass

    token = secrets.token_urlsafe(32)
    try:
        f.write_text(token + "\n", encoding="utf-8")
        try:
            os.chmod(f, 0o600)  # best-effort; no-op semantics on Windows
        except OSError:
            pass
    except OSError:
        # Can't persist (read-only FS) — still guard the server with an
        # in-memory token rather than failing open.
        pass
    _active_token = token
    return token


def _ensure_token() -> str:
    """Return the active token, resolving it from the loaded snapshot if needed.

    The HTTP dependency calls this so the guard works even when the lifespan
    startup hook didn't run (e.g. bare Starlette TestClient).
    """
    global _active_token
    if _active_token is None:
        from .loader import load_snapshot

        load_or_create_token(load_snapshot().repo_root)
    assert _active_token is not None
    return _active_token


def current_token() -> str:
    """Public accessor — used by the token-handout endpoint and tests."""
    return _ensure_token()


async def require_write_token(x_atlas_token: str | None = Header(default=None)) -> None:
    """FastAPI dependency: 401 unless the request carries the valid X-Atlas-Token.

    Wire it as `dependencies=[Depends(require_write_token)]` on each POST route —
    one line, no handler signature changes.
    """
    expected = _ensure_token()
    if not x_atlas_token or not secrets.compare_digest(x_atlas_token, expected):
        raise HTTPException(401, "missing or invalid X-Atlas-Token")

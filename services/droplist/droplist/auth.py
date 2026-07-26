"""Shared-secret guard for DropList's state-changing endpoints.

Mirrors ``services/atlas-map-api/src/atlas_map_api/auth.py``: every mutating
POST must present the local write secret as ``X-Atlas-Token``. DropList shares
atlas-map-api's secret on purpose — the same ``ATLAS_WRITE_TOKEN`` env var and
the same repo-root ``.atlas-write-token`` file — so the whole 127.0.0.1 trust
domain (the served UI, the atlas ``/call`` gateway, the CLI) speaks ONE token
instead of a per-service zoo of secrets. GET reads stay open; only writes and
the Anthropic proxy are guarded.

Why a custom header and not a query param: the custom header forces a CORS
preflight for cross-origin POSTs, so a DNS-rebind browser tab at a foreign
origin can't even send the write (the preflight fails against the restricted
``allow_origins``) — and without the secret it gets 401 regardless. A rogue
local process must specifically read the gitignored token file to forge a
request, the same bar as reading any other local secret.

Token resolution (first hit wins):
  1. ``ATLAS_WRITE_TOKEN`` env var
  2. ``<repo_root>/.atlas-write-token`` (gitignored)
  3. freshly generated (``secrets.token_urlsafe``) + written to that file

See ~/.claude/rules/common/code-as-furniture.md — the open write API
(HIGH finding in SHIP_READINESS_AND_MARKET_2026-06-25.md / DROPLIST_SHIP_SPEC
Task B) is fixed inline here, not documented-and-left.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

TOKEN_ENV = "ATLAS_WRITE_TOKEN"
TOKEN_FILENAME = ".atlas-write-token"

# Resolved once per process and reused. Set by load_or_create_token() (called at
# lifespan startup) or lazily by the dependency so a bare TestClient still works.
_active_token: str | None = None


def repo_root() -> Path:
    """Walk up from this file to the Pre Atlas repo root.

    The root is the first ancestor holding a repo marker (``.git`` or
    ``atlas-map.json``) — the same directory atlas-map-api resolves to, so both
    services land on the same ``.atlas-write-token``. Falls back to the
    services/droplist parent chain if no marker is found.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / "atlas-map.json").is_file():
            return parent
    # services/droplist/droplist/auth.py -> parents[2] == repo's services/.. fallback
    return here.parents[3] if len(here.parents) > 3 else here.parent


def _token_file(root: Path) -> Path:
    return root / TOKEN_FILENAME


def load_or_create_token(root: Path | None = None) -> str:
    """Resolve the write token, generating + persisting one if none exists.

    Idempotent: repeated calls return the same value (env or on-disk), and only
    generate when neither is present. Caches the result in-process.
    """
    global _active_token

    env = os.environ.get(TOKEN_ENV)
    if env and env.strip():
        _active_token = env.strip()
        return _active_token

    root = root or repo_root()
    f = _token_file(root)
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
    """Return the active token, resolving it lazily if startup didn't run."""
    global _active_token
    if _active_token is None:
        load_or_create_token()
    assert _active_token is not None
    return _active_token


def current_token() -> str:
    """Public accessor — the write token. Used to inject into the served UI so
    same-origin fetches can authenticate, and by tests."""
    return _ensure_token()


async def require_write_token(
    x_atlas_token: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: authorize a state-changing POST.

    Wire it as ``dependencies=[Depends(require_write_token)]`` on each mutating
    route — one line, no handler signature changes. Constant-time compare so a
    wrong token can't be guessed by timing. 401 on missing/invalid.
    """
    if x_atlas_token and secrets.compare_digest(x_atlas_token, _ensure_token()):
        return
    raise HTTPException(status_code=401, detail="missing or invalid X-Atlas-Token")

"""Shared-secret guard for memory-hub's state-changing endpoints.

Mirrors ``services/droplist/droplist/auth.py`` exactly: same env var, same
gitignored ``.atlas-write-token`` file at the repo root, so the whole 127.0.0.1
trust domain speaks ONE token. memory-hub's ``POST /save`` writes directly into
droplist's own data store (``stores.append_to_droplist``), so it must be gated
the same way droplist gates its own ``POST /api/drop`` — otherwise the shared
store has one guarded front door and one unguarded side door onto the same data.

Found unauthenticated in this session's injection sweep (droplist has a write
token, memory-hub's /save into the same store did not). See
~/.claude/rules/common/code-as-furniture.md — fixed inline, not documented-and-left.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

TOKEN_ENV = "ATLAS_WRITE_TOKEN"
TOKEN_FILENAME = ".atlas-write-token"

_active_token: str | None = None


def repo_root() -> Path:
    """Walk up from this file to the Pre Atlas repo root (same marker droplist
    and atlas-map-api use), so all three land on the same token file."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists() or (parent / "atlas-map.json").is_file():
            return parent
    return here.parents[3] if len(here.parents) > 3 else here.parent


def _token_file(root: Path) -> Path:
    return root / TOKEN_FILENAME


def load_or_create_token(root: Path | None = None) -> str:
    """Resolve the write token, generating + persisting one if none exists.

    Idempotent, and shares the file droplist/atlas-map-api already write —
    in normal operation this only ever reads an existing token, never creates one.
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
            os.chmod(f, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    _active_token = token
    return token


def _ensure_token() -> str:
    global _active_token
    if _active_token is None:
        load_or_create_token()
    assert _active_token is not None
    return _active_token


async def require_write_token(
    x_atlas_token: str | None = Header(default=None),
) -> None:
    """FastAPI dependency: authorize a state-changing POST. Constant-time
    compare so a wrong token can't be guessed by timing. 401 on missing/invalid."""
    if x_atlas_token and secrets.compare_digest(x_atlas_token, _ensure_token()):
        return
    raise HTTPException(status_code=401, detail="missing or invalid X-Atlas-Token")

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

import json
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import Header, HTTPException

TOKEN_ENV = "ATLAS_WRITE_TOKEN"
TOKEN_FILENAME = ".atlas-write-token"

# Role-token registry (used by /describe enforcement). Maps additional tokens to a
# role NAME so a caller's role is derived from the token they present, not from a
# self-asserted query param. The privileged write token always resolves to "root".
ROLE_TOKENS_ENV = "ATLAS_ROLE_TOKENS"          # JSON: {"<token>": "<role>", ...}
ROLE_TOKENS_FILENAME = ".atlas-role-tokens.json"  # gitignored, same shape
DEFAULT_CALLER_ROLE = "anon"                   # no token / unknown token => least privilege

_role_tokens: dict[str, str] | None = None

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


# ---------------------------------------------------------------------------
# Role-token registry — derive a caller's ROLE from the token they present.
# This is what turns /describe from a self-asserted demo (?role=root) into an
# enforced surface: the token IS the role; the query param can only narrow.
# ---------------------------------------------------------------------------
def _role_tokens_file(repo_root: Path) -> Path:
    return repo_root / ROLE_TOKENS_FILENAME


def _normalize_entry(raw: Any) -> dict[str, Any]:
    """Coerce a role-token value to {role, write_surfaces}. A bare string is a role
    with no write scoping; a dict may add `write_surfaces: [..]` to restrict which
    surfaces that token may WRITE (reads are unaffected). None => all surfaces."""
    if isinstance(raw, dict):
        # Absent key => no extra restriction (role-based writes). Present but not a
        # list (a typo like "droplist" or an explicit null) => deny-all, fail-closed:
        # a misconfigured scope must never silently widen to all surfaces.
        if "write_surfaces" not in raw:
            scope: list[str] | None = None
        elif isinstance(raw["write_surfaces"], list):
            scope = [str(s) for s in raw["write_surfaces"]]
        else:
            scope = []
        return {"role": str(raw.get("role", DEFAULT_CALLER_ROLE)), "write_surfaces": scope}
    return {"role": str(raw), "write_surfaces": None}


def load_role_tokens(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Resolve the {token: {role, write_surfaces}} map from env + gitignored file.

    Both sources are optional — with neither configured, only the privileged write
    token (=> root) and the implicit anon fallback exist. Values may be a role
    string or a {"role": ..., "write_surfaces": [...]} object. Fail-soft: malformed
    config yields an empty map rather than crashing. Cached in-process.
    """
    global _role_tokens
    if _role_tokens is not None:
        return _role_tokens

    mapping: dict[str, dict[str, Any]] = {}
    for source in (os.environ.get(ROLE_TOKENS_ENV), _read_role_tokens_file(repo_root)):
        if not source:
            continue
        try:
            parsed = json.loads(source)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            mapping.update({str(k): _normalize_entry(v) for k, v in parsed.items()})

    _role_tokens = mapping
    return _role_tokens


def reload_role_tokens() -> None:
    """Drop the cached role-token map so the next resolve re-reads env + file. Wire
    into /admin/reload so an operator can rotate/revoke tokens without a restart."""
    global _role_tokens
    _role_tokens = None


def _read_role_tokens_file(repo_root: Path) -> str | None:
    f = _role_tokens_file(repo_root)
    try:
        return f.read_text(encoding="utf-8") if f.is_file() else None
    except OSError:
        return None


def resolve_caller_role(token: str | None, repo_root: Path) -> str:
    """Map a presented X-Atlas-Token to a role NAME. Fail-safe: anything we can't
    positively authorize resolves to the least-privileged role.

    Precedence: privileged write token => 'root'; else role-token registry; else
    anon. Uses constant-time comparison for the write token to avoid timing leaks.
    """
    if not token:
        return DEFAULT_CALLER_ROLE
    try:
        if secrets.compare_digest(token, _ensure_token()):
            return "root"
    except Exception:
        pass
    entry = load_role_tokens(repo_root).get(token)
    return entry["role"] if entry else DEFAULT_CALLER_ROLE


def caller_write_surfaces(token: str | None, repo_root: Path) -> set[str] | None:
    """Which surfaces may this token WRITE? None = no extra restriction (all). A set
    = the token is scoped to writing only those surfaces. The privileged write token
    (root) is unrestricted; tokens without a `write_surfaces` clause are too."""
    if not token:
        return None
    try:
        if secrets.compare_digest(token, _ensure_token()):
            return None
    except Exception:
        pass
    entry = load_role_tokens(repo_root).get(token)
    if entry and entry.get("write_surfaces") is not None:
        return set(entry["write_surfaces"])
    return None

"""Thin HTTP client + repo-root detection.

The CLI converts absolute paths (whatever cwd you're in) into repo-relative
paths before handing them to the API. To do that we walk up from cwd until
we find a marker the atlas snapshot also recognizes — `audit/system-index.json`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


DEFAULT_BASE = "http://127.0.0.1:3072"
MARKER = Path("audit/system-index.json")

# Shared-secret guard for state-changing POSTs (mirrors atlas_map_api.auth).
TOKEN_ENV = "ATLAS_WRITE_TOKEN"
TOKEN_FILENAME = ".atlas-write-token"


def api_base() -> str:
    return os.environ.get("ATLAS_API_URL", DEFAULT_BASE).rstrip("/")


def write_token(repo_root: Path | None = None) -> str | None:
    """Resolve the X-Atlas-Token POSTs must carry: env var, else the gitignored
    <repo_root>/.atlas-write-token file the server writes at startup. None if
    neither is found (the CLI then gets a clean 401 from the API)."""
    env = os.environ.get(TOKEN_ENV)
    if env and env.strip():
        return env.strip()
    root = repo_root or find_repo_root()
    if root is None:
        return None
    f = root / TOKEN_FILENAME
    try:
        if f.is_file():
            tok = f.read_text(encoding="utf-8").strip()
            return tok or None
    except OSError:
        pass
    return None


def find_repo_root(start: Path | None = None) -> Path | None:
    """Walk up from `start` (default: cwd) until we find audit/system-index.json."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / MARKER).is_file():
            return d
    return None


def to_repo_relative(path: str, repo_root: Path | None = None) -> str:
    """Convert any path form into a repo-relative POSIX path.

    Accepts three input shapes, in priority order:
      1. Absolute path  -> resolve, strip repo prefix if possible.
      2. Repo-relative  -> if (repo_root / path) exists OR (cwd / path) doesn't,
                           treat as already-repo-relative and pass through.
      3. cwd-relative   -> join to cwd, resolve, strip repo prefix.

    Falls back to the POSIX-normalized input when no root is found.
    """
    root = repo_root or find_repo_root()
    p = Path(path)

    if p.is_absolute():
        p = p.resolve()
        if root is None:
            return str(p).replace("\\", "/")
        try:
            return str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")

    # Relative input. Prefer repo-relative interpretation when it points at
    # something real OR when the cwd-joined version doesn't exist on disk —
    # that's the common case for `atlas locate services/foo/bar.py` typed from
    # any cwd (including tools/atlas-cli, the venv, your home dir, etc.).
    norm = str(p).replace("\\", "/")
    if root is not None:
        if (root / p).exists() or not (Path.cwd() / p).exists():
            return norm

    # Fall through: it really is a cwd-relative path that exists locally.
    resolved = (Path.cwd() / p).resolve()
    if root is None:
        return str(resolved).replace("\\", "/")
    try:
        return str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(resolved).replace("\\", "/")


class AtlasClient:
    def __init__(self, base: str | None = None, timeout: float = 5.0):
        self.base = (base or api_base()).rstrip("/")
        self._client = httpx.Client(base_url=self.base, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        # Drop None params so optional query args don't show up as 'None'.
        cleaned = {k: v for k, v in params.items() if v is not None}
        r = self._client.get(path, params=cleaned)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str) -> dict[str, Any]:
        # State-changing endpoints require the shared secret. Resolve lazily so
        # read-only commands never need the token present.
        headers = {}
        tok = write_token()
        if tok:
            headers["X-Atlas-Token"] = tok
        r = self._client.post(path, headers=headers)
        r.raise_for_status()
        return r.json()

    # ---- thin endpoint wrappers ----
    def root(self) -> dict[str, Any]:
        return self._get("/")

    def systems(self, group: str | None = None, running: bool | None = None) -> dict[str, Any]:
        return self._get("/map/systems", group=group, running=running)

    def system(self, name: str) -> dict[str, Any]:
        return self._get(f"/map/systems/{name}")

    def locate(self, file: str) -> dict[str, Any]:
        return self._get("/map/locate", file=file)

    def neighbors(self, name: str, hops: int = 1) -> dict[str, Any]:
        return self._get(f"/map/neighbors/{name}", hops=hops)

    def path(self, src: str, dst: str) -> dict[str, Any]:
        return self._get("/map/path", **{"from": src, "to": dst})

    def search(self, q: str, limit: int = 10) -> dict[str, Any]:
        return self._get("/map/search", q=q, limit=limit)

    def signals(self) -> dict[str, Any]:
        return self._get("/map/signals")

    def reload(self) -> dict[str, Any]:
        return self._post("/admin/reload")

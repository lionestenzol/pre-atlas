"""Layer-3 call gateway — the "OpenRouter front door" over the capability registry.

One endpoint, `POST /call {surface, capability, args}`, lets a caller invoke a
service's capability *by name* without knowing its host/port/route. The gateway:

  1. derives the caller's role from X-Atlas-Token (same seam as /describe),
  2. enforces access by VISIBILITY — you can only invoke a capability your own
     form actually shows (not locked, not redacted). The registry IS the ACL.
  3. resolves surface -> port (launch.json is the runtime truth, snapshot is the
     fallback) and proxies the declared `invoke` route to the live service.

First brick = the SAFE half of the hybrid: read-only (`direction == read`) HTTP
surfaces only. Writes are gated off (501) until a later brick adds write-scoped
tokens; cli/ui/websocket surfaces aren't proxyable here (422). SSRF surface is
bounded: the host+port come from trusted config and the path comes from the
trusted overlay — the caller only picks a surface+capability they're cleared to
see, plus args that fill declared `{path_params}` or the query string.
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from . import auth, launcher
from . import describe as describe_mod
from .loader import MapSnapshot

WRITES_ENABLED = os.environ.get("DESCRIBE_GATEWAY_WRITES", "") == "1"
_PATH_PARAM = re.compile(r"\{([^}]+)\}")


def resolve_base_url(snap: MapSnapshot, surface: str) -> str | None:
    """surface -> http://127.0.0.1:<port>. launch.json (runtime truth) first, then
    the system-index snapshot. None when the surface has no resolvable port."""
    for cfg in launcher.load_launch_configs(snap.repo_root):
        if cfg.get("name") == surface and cfg.get("port"):
            return f"http://127.0.0.1:{int(cfg['port'])}"
    sub = snap.subsystems.get(surface)
    if sub and sub.port:
        return f"http://127.0.0.1:{int(sub.port)}"
    return None


def parse_invoke(invoke: str) -> tuple[str, str]:
    """'POST /api/drop' -> ('POST', '/api/drop'); bare path -> ('GET', path)."""
    parts = invoke.split()
    if len(parts) >= 2:
        return parts[0].upper(), parts[1]
    return "GET", (parts[0] if parts else "/")


def build_target(base_url: str, invoke: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Return (method, url, leftover_args). Path `{params}` are filled from args and
    removed; leftover args become the GET query / POST body."""
    method, path = parse_invoke(invoke)
    used: set[str] = set()

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        used.add(key)
        return str(args.get(key, m.group(0)))

    path = _PATH_PARAM.sub(_sub, path)
    leftover = {k: v for k, v in (args or {}).items() if k not in used}
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    if method == "GET" and leftover:
        url = f"{url}?{urlencode(leftover)}"
        leftover = {}
    return method, url, leftover


async def call_capability(
    snap: MapSnapshot,
    surface: str,
    capability_id: str,
    args: dict[str, Any] | None,
    token: str | None,
) -> dict[str, Any]:
    """Enforce + proxy. Returns {ok, status, ...} or {ok: False, code, error}."""
    overlay = describe_mod.load_overlay(snap.repo_root, surface)
    if overlay is None:
        return {"ok": False, "code": 404, "error": f"surface '{surface}' has no self-description"}

    cap = next((c for c in overlay.capabilities if c.id == capability_id), None)
    if cap is None:
        return {"ok": False, "code": 404, "error": f"capability '{capability_id}' not found on '{surface}'"}

    # Access by visibility: the capability must appear in THIS caller's form.
    role = describe_mod.resolve_role(auth.resolve_caller_role(token, snap.repo_root))
    form = describe_mod.describe_surface(overlay, role)
    if capability_id not in {f["id"] for f in form["fields"]}:
        return {"ok": False, "code": 403, "error": f"'{capability_id}' not available to role '{role.name}'"}

    if overlay.kind != "http":
        return {"ok": False, "code": 422, "error": f"surface kind '{overlay.kind}' is not proxyable yet (http only)"}
    if cap.direction == "write" and not WRITES_ENABLED:
        return {"ok": False, "code": 501, "error": "write capabilities are gated off (set DESCRIBE_GATEWAY_WRITES=1)"}

    base = resolve_base_url(snap, surface)
    if base is None:
        return {"ok": False, "code": 422, "error": f"'{surface}' has no resolvable port — cannot be reached"}

    method, url, body = build_target(base, cap.invoke, args or {})
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.request(method, url, json=body or None)
    except httpx.HTTPError as e:
        return {"ok": False, "code": 502, "error": f"upstream '{surface}' unreachable: {e}"}

    try:
        payload = resp.json()
    except ValueError:
        payload = resp.text
    return {
        "ok": resp.is_success,
        "code": resp.status_code,
        "surface": surface,
        "capability": capability_id,
        "invoke": f"{method} {url}",
        "response": payload,
    }

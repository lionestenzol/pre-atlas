"""Layer-3 call gateway — the "OpenRouter front door" over the capability registry.

One endpoint, `POST /call {surface, capability, args}`, lets a caller invoke a
service's capability *by name* without knowing its host/port/route. The gateway:

  1. derives the caller's role from X-Atlas-Token (same seam as /describe),
  2. enforces access by VISIBILITY — you can only invoke a capability your own
     form actually shows (not locked, not redacted). The registry IS the ACL.
  3. validates args against the capability's DECLARED params (path placeholders +
     `needs`) — a caller can't smuggle undeclared params/flags.
  4. dispatches by surface kind:
       http -> resolve surface->port (launch.json runtime truth, snapshot
               fallback) and proxy the declared route via httpx. Path params are
               percent-encoded so a value can never escape its own route segment.
       cli  -> run the declared command argv-only (never a shell), exe resolved to
               an absolute path, in the tool's dir, with validated args. OFF by
               default (command execution).
     ui/websocket are not invocable here (422).

Safety posture (hardened after adversarial review 2026-06-24):
  - Writes are OPT-IN: a write is refused unless DESCRIBE_GATEWAY_WRITES=1. "Write"
    is determined by the HTTP VERB (POST/PUT/PATCH/DELETE) for http surfaces, not
    just the hand-authored `direction` label — the verb is ground truth, the label
    may only raise restriction.
  - cli is OPT-IN: DESCRIBE_GATEWAY_CLI=1. argv-only, no shell, exe via shutil.which,
    leading-dash values rejected, `--` end-of-options sentinel, arg count/length caps.
  - SSRF/command-injection bounded: host+port+path+command come from trusted config;
    the caller only picks a surface+capability they're cleared to see + declared,
    percent-encoded arg values — never a host, route, or command.

Every reached invocation returns a NORMALIZED envelope; enforcement refusals are
surfaced as HTTP errors by the endpoint instead.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from . import auth, launcher
from . import describe as describe_mod
from .loader import MapSnapshot

WRITES_ENABLED = os.environ.get("DESCRIBE_GATEWAY_WRITES", "") == "1"   # opt-in, fail-closed
CLI_ENABLED = os.environ.get("DESCRIBE_GATEWAY_CLI", "") == "1"          # opt-in, command exec

_PATH_PARAM = re.compile(r"\{([^}]+)\}")
# argv values: safe charset AND must not begin with '-' (no flag injection).
_SAFE_ARG = re.compile(r"^[A-Za-z0-9_.,:/@=+][A-Za-z0-9_.,:/@=+-]*$|^$")
_MUTATING_VERBS = {"POST", "PUT", "PATCH", "DELETE"}
_CLI_TIMEOUT_S = 20.0
_MAX_ARG_COUNT = 32
_MAX_ARG_LEN = 512


# ---------------------------------------------------------------------------
# Result envelopes
# ---------------------------------------------------------------------------
def _refusal(code: int, error: str) -> dict[str, Any]:
    return {"refusal": True, "ok": False, "code": code, "error": error}


def _envelope(
    *, ok: bool, code: int, surface: str, capability: str, kind: str,
    status: Any, data: Any = None, error: str | None = None, meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok, "code": code, "surface": surface, "capability": capability,
        "kind": kind, "status": status, "data": data, "error": error, "meta": meta or {},
    }


# ---------------------------------------------------------------------------
# Resolution + arg helpers
# ---------------------------------------------------------------------------
def resolve_base_url(snap: MapSnapshot, surface: str) -> str | None:
    for cfg in launcher.load_launch_configs(snap.repo_root):
        if cfg.get("name") == surface and cfg.get("port"):
            return f"http://127.0.0.1:{int(cfg['port'])}"
    sub = snap.subsystems.get(surface)
    if sub and sub.port:
        return f"http://127.0.0.1:{int(sub.port)}"
    return None


def parse_invoke(invoke: str) -> tuple[str, str]:
    parts = invoke.split()
    if len(parts) >= 2:
        return parts[0].upper(), parts[1]
    return "GET", (parts[0] if parts else "/")


def declared_params(cap_invoke: str, needs: tuple[str, ...]) -> set[str]:
    """The only arg keys a caller may pass: path placeholders + declared `needs`."""
    _, path = parse_invoke(cap_invoke)
    return set(_PATH_PARAM.findall(path)) | set(needs or ())


def is_write(kind: str, cap) -> bool:
    """Effective write determination — verb is ground truth for http surfaces; the
    `direction` label may only ADD restriction (a write label always counts)."""
    if cap.direction == "write":
        return True
    if kind == "http":
        return parse_invoke(cap.invoke)[0] in _MUTATING_VERBS
    return False


def build_target(base_url: str, invoke: str, args: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """(method, url, leftover_args). Path `{params}` are PERCENT-ENCODED so a value
    can't open a new segment/query (no `../`, `?`, `&`). Leftover args -> GET query."""
    method, path = parse_invoke(invoke)
    used: set[str] = set()

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        used.add(key)
        if key in args:
            return quote(str(args[key]), safe="")  # confine to one path segment
        return m.group(0)

    path = _PATH_PARAM.sub(_sub, path)
    leftover = {k: v for k, v in (args or {}).items() if k not in used}
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    if method == "GET" and leftover:
        url = f"{url}?{urlencode(leftover)}"
        leftover = {}
    return method, url, leftover


def build_argv(invoke: str, args: dict[str, Any]) -> tuple[list[str], str | None]:
    """Safe argv from a cli capability's trusted command + caller args.

    Command comes from the overlay (argv-split). Caller args become `--key value`,
    each validated: safe charset, no leading dash (no flag injection), bounded
    length/count. A `--` end-of-options sentinel separates the command from caller
    args so the target treats them as values, not options. Nothing runs via a shell."""
    base = shlex.split(invoke, posix=True)
    if not base:
        return [], "empty command"
    items = list((args or {}).items())
    if len(items) > _MAX_ARG_COUNT:
        return [], f"too many args (max {_MAX_ARG_COUNT})"
    tail: list[str] = []
    for k, v in items:
        ks, vs = str(k), str(v)
        if len(ks) > _MAX_ARG_LEN or len(vs) > _MAX_ARG_LEN:
            return [], "arg too long"
        if not _SAFE_ARG.match(ks) or not _SAFE_ARG.match(vs):
            return [], f"unsafe cli argument rejected: {k!r}"
        tail += [f"--{ks}", vs]
    argv = base + (["--"] + tail if tail else [])
    return argv, None


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
def _enforce(snap: MapSnapshot, surface: str, capability_id: str, args: dict[str, Any] | None, token: str | None):
    """Return (overlay, capability, role) on success, or a refusal dict."""
    overlay = describe_mod.load_overlay(snap.repo_root, surface)  # surface name validated inside
    if overlay is None:
        return _refusal(404, f"surface '{surface}' has no self-description")
    cap = next((c for c in overlay.capabilities if c.id == capability_id), None)
    if cap is None:
        return _refusal(404, f"capability '{capability_id}' not found on '{surface}'")

    role = describe_mod.resolve_role(auth.resolve_caller_role(token, snap.repo_root))
    form = describe_mod.describe_surface(overlay, role)
    if capability_id not in {f["id"] for f in form["fields"]}:
        return _refusal(403, f"'{capability_id}' not available to role '{role.name}'")

    allowed = declared_params(cap.invoke, cap.needs)
    undeclared = set((args or {}).keys()) - allowed
    if undeclared:
        return _refusal(400, f"undeclared args rejected: {sorted(undeclared)} (allowed: {sorted(allowed)})")

    if is_write(overlay.kind, cap) and not WRITES_ENABLED:
        return _refusal(501, "writes are gated off (set DESCRIBE_GATEWAY_WRITES=1)")
    return overlay, cap, role


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
def _meta(role_obj, **full) -> dict[str, Any]:
    """Internal topology (resolved url / argv / cwd) only for cleared roles
    (clearance >= 2); lower roles get the declared invoke string only."""
    if role_obj.clearance >= 2:
        return full
    return {"invoke": full.get("declared", ""), "role": role_obj.name}


async def _invoke_http(snap, surface, cap, role, args) -> dict[str, Any]:
    base = resolve_base_url(snap, surface)
    if base is None:
        return _refusal(422, f"'{surface}' has no resolvable port — cannot be reached")
    method, url, body = build_target(base, cap.invoke, args or {})
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await (client.get(url) if method == "GET" else client.request(method, url, json=body or None))
    except httpx.HTTPError:
        return _envelope(
            ok=False, code=502, surface=surface, capability=cap.id, kind="http", status=None,
            error="upstream unreachable",
            meta=_meta(role, declared=cap.invoke, invoke=f"{method} {url}", role=role.name),
        )
    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    return _envelope(
        ok=resp.is_success, code=resp.status_code, surface=surface, capability=cap.id,
        kind="http", status=resp.status_code, data=data,
        error=None if resp.is_success else f"upstream returned {resp.status_code}",
        meta=_meta(role, declared=cap.invoke, invoke=f"{method} {url}", role=role.name),
    )


def _invoke_cli(snap, surface, cap, role, args) -> dict[str, Any]:
    if not CLI_ENABLED:
        return _refusal(501, "cli invocation is gated off (set DESCRIBE_GATEWAY_CLI=1)")
    argv, err = build_argv(cap.invoke, args or {})
    if err:
        return _refusal(400, err)
    exe = shutil.which(argv[0])  # absolute path resolution — no cwd argv[0] hijack
    if exe is None:
        return _envelope(
            ok=False, code=502, surface=surface, capability=cap.id, kind="cli", status=None,
            error=f"executable not found: {argv[0]!r}", meta=_meta(role, declared=cap.invoke, argv=argv, role=role.name),
        )
    argv[0] = exe
    sub = snap.subsystems.get(surface)
    cwd = (snap.repo_root / sub.path) if (sub and sub.path) else snap.repo_root
    try:
        proc = subprocess.run(  # noqa: S603 — absolute exe, argv-only, shell=False
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=_CLI_TIMEOUT_S, shell=False,
        )
    except subprocess.TimeoutExpired:
        return _envelope(
            ok=False, code=504, surface=surface, capability=cap.id, kind="cli", status=None,
            error=f"timed out after {_CLI_TIMEOUT_S}s", meta=_meta(role, declared=cap.invoke, role=role.name),
        )
    ok = proc.returncode == 0
    return _envelope(
        ok=ok, code=200 if ok else 500, surface=surface, capability=cap.id, kind="cli",
        status=proc.returncode, data={"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]},
        error=None if ok else f"exit {proc.returncode}",
        meta=_meta(role, declared=cap.invoke, argv=argv, role=role.name),
    )


async def call_capability(
    snap: MapSnapshot, surface: str, capability_id: str,
    args: dict[str, Any] | None, token: str | None,
) -> dict[str, Any]:
    enforced = _enforce(snap, surface, capability_id, args, token)
    if isinstance(enforced, dict):
        return enforced
    overlay, cap, role = enforced
    if overlay.kind == "http":
        return await _invoke_http(snap, surface, cap, role, args)
    if overlay.kind == "cli":
        return _invoke_cli(snap, surface, cap, role, args)
    return _refusal(422, f"surface kind '{overlay.kind}' is not invocable yet (http, cli)")

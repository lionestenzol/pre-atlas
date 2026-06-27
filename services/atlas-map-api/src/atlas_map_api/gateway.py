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


def _cli_timeout_default() -> float:
    """Per-call CLI timeout in seconds. Default 20.0 keeps the common fast path fail-closed;
    an operator can raise it for a genuinely-large repo (e.g. a 1.4G tree repo-inventory cannot
    census in 20s) via DESCRIBE_GATEWAY_TIMEOUT_S. Malformed / non-positive values fall back to
    20.0 so a typo can never brick the gateway import.
    Made env-configurable to match the WRITES/CLI gates above.
    See ~/.claude/rules/common/code-as-furniture.md — fix the cap, don't just document the timeout.
    """
    try:
        val = float(os.environ.get("DESCRIBE_GATEWAY_TIMEOUT_S", ""))
    except (TypeError, ValueError):
        return 20.0
    return val if val > 0 else 20.0


_CLI_TIMEOUT_S = _cli_timeout_default()
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
    """The only arg keys a caller may pass: {placeholders} declared anywhere in the
    invoke (http path params OR cli positionals) + declared `needs`.

    Scanning the WHOLE invoke (not just the parsed path) is what lets a cli
    capability like "sigil info {input}" declare its positional arg. http invokes
    only ever carry `{...}` inside the path, so this stays byte-identical for them.
    See ~/.claude/rules/common/code-as-furniture.md — the cli arg path was declared
    but unreachable for positional tools; fixed inline, not documented-and-left."""
    return set(_PATH_PARAM.findall(cap_invoke)) | set(needs or ())


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

    Command comes from the overlay (argv-split, trusted). Caller args bind two ways,
    both validated identically (safe charset, no leading dash = no flag injection,
    bounded length/count):
      - POSITIONAL: a `{key}` token in the command is replaced IN PLACE by the
        value — mirrors the http path-param convention — so positional-arg tools
        like `sigil info {input}` are reachable. An unsupplied placeholder fails
        loud rather than shelling out a literal `{key}`.
      - FLAG: any leftover key becomes `--key value`, placed AFTER a `--`
        end-of-options sentinel so the target reads it as a value, not an option.
    Literal command tokens (incl. trusted flags like `--out`, and human doc hints
    like `<file>`) pass through untouched; only caller-supplied values are charset-
    restricted. Nothing runs via a shell."""
    base = shlex.split(invoke, posix=True)
    if not base:
        return [], "empty command"
    # Defense-in-depth: the executable (argv[0]) must be a literal from the trusted
    # overlay — never a caller-substituted `{placeholder}`. Overlays are repo-authored
    # (so this is a malformed-overlay guard, not a caller exploit), but it removes any
    # path by which caller args could choose which binary shutil.which resolves.
    if _PATH_PARAM.fullmatch(base[0]):
        return [], "command name must be a literal, not a placeholder"
    items = list((args or {}).items())
    if len(items) > _MAX_ARG_COUNT:
        return [], f"too many args (max {_MAX_ARG_COUNT})"
    clean: dict[str, str] = {}
    for k, v in items:
        ks, vs = str(k), str(v)
        if len(ks) > _MAX_ARG_LEN or len(vs) > _MAX_ARG_LEN:
            return [], "arg too long"
        if not _SAFE_ARG.match(ks) or not _SAFE_ARG.match(vs):
            return [], f"unsafe cli argument rejected: {k!r}"
        clean[ks] = vs
    used: set[str] = set()
    cmd: list[str] = []
    for tok in base:
        m = _PATH_PARAM.fullmatch(tok)
        if m is None:
            cmd.append(tok)
            continue
        key = m.group(1)
        if key not in clean:
            return [], f"unbound placeholder {tok!r} (no {key!r} arg supplied)"
        cmd.append(clean[key])
        used.add(key)
    tail: list[str] = []
    for ks, vs in clean.items():
        if ks in used:
            continue
        tail += [f"--{ks}", vs]
    argv = cmd + (["--"] + tail if tail else [])
    return argv, None


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------
def _enforce(snap: MapSnapshot, surface: str, capability_id: str, args: dict[str, Any] | None,
             token: str | None, role_name: str | None = None):
    """Return (overlay, capability, role) on success, or a refusal dict.

    role_name, when given, is an in-process trust assertion (the MCP path runs in
    the user's local session and has no HTTP token) — it sets the role directly.
    The HTTP path leaves it None and derives the role from the token."""
    overlay = describe_mod.load_overlay(snap.repo_root, surface)  # surface name validated inside
    if overlay is None:
        return _refusal(404, f"surface '{surface}' has no self-description")
    cap = next((c for c in overlay.capabilities if c.id == capability_id), None)
    if cap is None:
        return _refusal(404, f"capability '{capability_id}' not found on '{surface}'")

    role = describe_mod.resolve_role(role_name or auth.resolve_caller_role(token, snap.repo_root))
    form = describe_mod.describe_surface(overlay, role)
    if capability_id not in {f["id"] for f in form["fields"]}:
        return _refusal(403, f"'{capability_id}' not available to role '{role.name}'")

    allowed = declared_params(cap.invoke, cap.needs)
    undeclared = set((args or {}).keys()) - allowed
    if undeclared:
        return _refusal(400, f"undeclared args rejected: {sorted(undeclared)} (allowed: {sorted(allowed)})")

    if is_write(overlay.kind, cap):
        if not WRITES_ENABLED:
            return _refusal(501, "writes are gated off (set DESCRIBE_GATEWAY_WRITES=1)")
        scope = auth.caller_write_surfaces(token, snap.repo_root)
        if scope is not None and surface not in scope:
            return _refusal(403, f"token is not write-scoped to '{surface}'")
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
    # Local trust domain speaks ONE shared secret end-to-end: mutating proxied calls
    # forward the root X-Atlas-Token so downstream surfaces that guard their write
    # routes (e.g. droplist's auth.py, reading the same repo-root .atlas-write-token)
    # accept them instead of 401-ing. Reads carry no token. Without this, any droplist
    # write driven through this gateway 401s once PR #25 lands.
    # See ~/.claude/rules/common/code-as-furniture.md — bug fixed inline, not documented-and-left.
    headers = {"X-Atlas-Token": auth.current_token()} if method in _MUTATING_VERBS else None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await (
                client.get(url)
                if method == "GET"
                else client.request(method, url, json=body or None, headers=headers)
            )
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


async def fetch_state(snap: MapSnapshot, surface: str) -> dict[str, Any]:
    """Probe a surface's own public health/status read to fill the /describe `state`
    slot — the surface reporting its current state ("contextually self-aware"). Uses
    the gateway as anon (public reads only), fail-soft."""
    overlay = describe_mod.load_overlay(snap.repo_root, surface)
    if overlay is None or overlay.kind != "http":
        return {"probed": False, "reason": "not an http surface"}
    # GET verb (not just the read label) so a mislabeled mutating POST can't be probed.
    publics = [
        c for c in overlay.capabilities
        if c.direction == "read" and c.exposure == "public" and parse_invoke(c.invoke)[0] == "GET"
    ]
    health = next(
        (c for c in publics if c.id in ("status", "health", "healthz")
         or "health" in c.invoke.lower()),
        publics[0] if publics else None,
    )
    if health is None:
        return {"probed": False, "reason": "no public read capability"}
    res = await call_capability(snap, surface, health.id, None, token=None)  # anon, public read
    return {"probed": True, "via": health.id, "reachable": bool(res.get("ok")), "report": res.get("data")}


async def call_capability(
    snap: MapSnapshot, surface: str, capability_id: str,
    args: dict[str, Any] | None, token: str | None, role_name: str | None = None,
) -> dict[str, Any]:
    enforced = _enforce(snap, surface, capability_id, args, token, role_name)
    if isinstance(enforced, dict):
        return enforced
    overlay, cap, role = enforced
    if overlay.kind == "http":
        return await _invoke_http(snap, surface, cap, role, args)
    if overlay.kind == "cli":
        return _invoke_cli(snap, surface, cap, role, args)
    return _refusal(422, f"surface kind '{overlay.kind}' is not invocable yet (http, cli)")

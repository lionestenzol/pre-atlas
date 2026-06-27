#!/usr/bin/env python3
"""seam -- a standalone, model-agnostic runner for the perceive->compile->carry stack.

No Claude, no MCP, no server required. It loads the atlas-map capability registry and
drives the SAME gateway the HTTP endpoint uses, normalizing every tool's output into one
content-addressed Receipt. Any caller that can run a command -- a human, a shell script, a
cron job, any LLM/agent -- can use it.

  seam list                                  every surface + capability
  seam call <surface> <capability> k=v ...   call one tool, print its Receipt
  seam perceive <repo> [--writes]            lossy structure: inventory + orient + index
  seam carry <repo>                          lossless content: content-addressed bundle (repomix)
  seam narrate <repo>                        prose: read the cached wiki (deepwiki-open)

Flags:
  --json     machine-readable JSON manifest (default is a human table)
  --writes   allow file-writing capabilities (gw index, sigil pack); off by default,
             so a write capability shows as 'error: writes gated' until you opt in
  --role R   role for the redaction ladder (default: root)

Exit code is 0 when every receipt is ok, 1 otherwise -- so scripts can gate on it.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Self-contained: make atlas_map_api importable without installing it.
_SRC = Path(os.environ.get(
    "ATLAS_MAP_API_SRC", "C:/Users/bruke/Pre Atlas/services/atlas-map-api/src"))
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from atlas_map_api import gateway              # noqa: E402
from atlas_map_api.loader import load_snapshot  # noqa: E402
from atlas_map_api.seam import Receipt         # noqa: E402

# The seam stages: each is a fan-out pipeline of (surface, capability, the-arg-name-
# the-target-binds-to). Lists, not single tools, so more tools can join a stage later
# (a 2nd carrier, a 2nd narrator) without touching the dispatch.
#   PERCEIVE  lossy structure  (skeleton / census / freshness)   -- cheap, default
#   CARRY     lossless content (the actual files, scoped)         -- the zoom lane
#   NARRATE   prose            (the generated wiki, read cached)  -- the narrator lane
PERCEIVE = [
    ("repo-inventory", "inventory", "root"),   # read  -- file/LOC census
    ("code-recon",     "orient",    "root"),   # read  -- recon map freshness + content-address
    ("groundwork-cli", "index",     "root"),   # write -- subsystem index (needs --writes)
]
CARRY = [
    ("repomix",        "pack",      "root"),   # read  -- content-addressed full-content bundle
]
NARRATE = [
    ("deepwiki",       "narrate",   "repo"),   # read  -- cached wiki, content-addressed
]
PIPELINES = {"perceive": PERCEIVE, "carry": CARRY, "narrate": NARRATE}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _call(snap, surface: str, capability: str, args: dict, role: str) -> dict:
    env = asyncio.run(gateway.call_capability(
        snap, surface, capability, args, token=None, role_name=role))
    if isinstance(env, dict) and "surface" not in env:
        env = {**env, "surface": surface}      # refusals omit surface -> stamp it so tool isn't 'unknown'
    r = Receipt.from_envelope(env, produced_at=_now()).model_dump()
    r["_capability"] = capability
    return r


def _summary(receipts: list[dict]) -> dict:
    ok = sum(1 for r in receipts if r["status"] == "ok")
    return {"ok": ok, "error": len(receipts) - ok, "total": len(receipts)}


def _parse_kv(pairs: list[str]) -> dict:
    args: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise SystemExit(f"seam: bad arg {p!r}, expected key=value")
        k, v = p.split("=", 1)
        args[k] = v
    return args


def _list_surfaces(repo_root: Path) -> list[dict]:
    out = []
    for group in ("services", "apps", "tools"):
        base = repo_root / group
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*/atlas.surface.json")):
            try:
                ov = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append({"surface": ov.get("surface", f.parent.name),
                        "kind": ov.get("kind", "?"),
                        "capabilities": [c.get("id") for c in ov.get("capabilities", [])]})
    return out


def _emit(manifest: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(manifest, indent=2))
        return
    print(f"\nseam {manifest['pipeline']}  target={manifest.get('target', '-')}")
    print(f"{'SURFACE':16} {'CAP':11} {'STATUS':7} JOIN KEY (sha256)")
    print("-" * 72)
    for r in manifest["receipts"]:
        print(f"{r['tool']:16} {r.get('_capability', '-'):11} {r['status']:7} {(r['sha256'] or '-')[:24]}")
        if r["status"] != "ok" and r.get("error"):
            print(f"{'':16} {'':11} -> {r['error']}")
    s = manifest["summary"]
    print("-" * 72)
    print(f"{s['ok']} ok / {s['error']} error / {s['total']} total\n")


def main(argv: list[str] | None = None) -> int:
    # Shared flags live on each subparser so they work in the natural position
    # (e.g. `seam perceive <repo> --writes`), not only before the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable JSON manifest")
    common.add_argument("--writes", action="store_true", help="allow file-writing capabilities (gw index, sigil pack)")
    common.add_argument("--role", default="root", help="role for the redaction ladder (default: root)")

    ap = argparse.ArgumentParser(prog="seam", description="model-agnostic runner for the perceive->compile->carry seam")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", parents=[common], help="list every surface + capability")
    pc = sub.add_parser("call", parents=[common], help="call one surface capability")
    pc.add_argument("surface")
    pc.add_argument("capability")
    pc.add_argument("kv", nargs="*", help="key=value args, e.g. root=C:/path or target=<sha256>")
    pp = sub.add_parser("perceive", parents=[common], help="repo structural perceive pass (inventory + orient + index)")
    pp.add_argument("target", help="a repo / directory path (forward slashes)")
    cy = sub.add_parser("carry", parents=[common], help="CARRY stage: content-addressed full-content bundle (repomix)")
    cy.add_argument("target", help="a repo / directory scope (forward slashes)")
    nr = sub.add_parser("narrate", parents=[common], help="NARRATE stage: read the cached wiki (deepwiki-open)")
    nr.add_argument("target", help="a repo URL (github/gitlab) or local path (forward slashes)")

    a = ap.parse_args(argv)
    gateway.CLI_ENABLED = True
    if a.writes:
        gateway.WRITES_ENABLED = True
    snap = load_snapshot()

    if a.cmd == "list":
        surfaces = _list_surfaces(snap.repo_root)
        if a.json:
            print(json.dumps(surfaces, indent=2))
        else:
            print(f"\n{len(surfaces)} registered surfaces:\n")
            for s in surfaces:
                print(f"  {s['surface']:18} {s['kind']:5} {', '.join(s['capabilities'])}")
            print()
        return 0

    if a.cmd == "call":
        r = _call(snap, a.surface, a.capability, _parse_kv(a.kv), a.role)
        manifest = {"pipeline": "call", "target": f"{a.surface}.{a.capability}",
                    "produced_at": _now(), "receipts": [r], "summary": _summary([r])}
        _emit(manifest, a.json)
        return 0 if r["status"] == "ok" else 1

    # perceive / carry / narrate -- a named fan-out pipeline over one target
    stages = PIPELINES[a.cmd]
    receipts = [_call(snap, surface, cap, {arg: a.target}, a.role) for surface, cap, arg in stages]
    manifest = {"pipeline": a.cmd, "target": a.target,
                "produced_at": _now(), "receipts": receipts, "summary": _summary(receipts)}
    _emit(manifest, a.json)
    return 0 if manifest["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

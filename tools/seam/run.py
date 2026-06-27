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


# ── objective combo feed → tool-outcome ledger ────────────────────────────────
# A seam pipeline run IS an objective tool-combination observation: N tools fired
# together, with a hard ok/error manifest. That is a NON-proxy reward signal the
# combo scorer (~/.claude/scripts/ledger/combo.py) can learn from, replacing the
# sentiment proxy for combos that actually ran. We append ONE ledger row per tool,
# all sharing a synthetic turn key (request=seam:<pipeline>:<target>) under a
# per-run synthetic session, so combo.py's EXISTING cofire grouping picks the
# combination up unchanged -- zero combo.py change (option a).
#
# Per-run session (not one global session) so the holdout split in combo.evaluate
# (hash(session)%10) can actually spread recurring cofire pairs across train/holdout;
# one constant session would dump every objective row into a single bucket.
#
# Reward is OBJECTIVE: the COMBINATION succeeded (+1) iff every receipt is ok, else
# -1. Opt-in via SEAM_LEDGER=1 so unit-test / exploratory seam runs never pollute the
# real ledger (gate per the lattice NEXT). SEAM_LEDGER_PATH overrides the target file
# (hermetic tests point it at a temp ledger).
def _ledger_path() -> Path:
    return Path(os.environ.get(
        "SEAM_LEDGER_PATH", str(Path.home() / ".claude" / "logs" / "tool-outcomes.jsonl")))


def _next_invocation_index(path: Path, session: str) -> int:
    """Max existing invocation_index for `session`, +1 (monotonic per session, like backfill)."""
    hi = -1
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("session") == session:
                        idx = r.get("invocation_index")
                        if isinstance(idx, int) and idx > hi:
                            hi = idx
        except OSError:
            pass
    return hi + 1


def _ledger_rows(manifest: dict, session: str, base_index: int) -> list[dict]:
    """One objective row per receipt, matching backfill.py's row schema exactly."""
    receipts = manifest.get("receipts") or []
    all_ok = (manifest.get("summary") or {}).get("error", 1) == 0
    reward = 1.0 if all_ok else -1.0
    request = f"seam:{manifest.get('pipeline')}:{manifest.get('target')}"[:160].replace("\n", " ")
    rows = []
    for off, r in enumerate(receipts):
        rows.append({
            "session": session,
            "cwd": str(manifest.get("target")),
            "skill": r.get("tool"),                # surface name = the combo member
            "source": "seam",                      # objective row; distinguishes from transcript-mined
            "invocation_index": base_index + off,
            "request": request,                    # shared turn key -> combo.py groups these as one cofire
            "n_tools_in_turn": len(receipts),
            "reward": "objective_ok" if all_ok else "objective_error",
            "score": reward,
            "shipped": False,
            "retried": False,
            "reward_score": reward,                # router/_row_reward reads this first
            "next_user": None,
            "has_feedback": True,                  # objective evidence present (not sentiment, but real)
        })
    return rows


def _append_ledger(manifest: dict) -> int:
    """Append objective combo rows for a pipeline manifest. No-op unless SEAM_LEDGER=1.

    Best-effort telemetry: the whole body is fail-safe so a ledger write error can
    never crash the seam run or change its exit code (scripts gate on receipt-ok, not
    on this side-channel). Same posture as append_outcome.py's Stop-hook failsafe.
    Returns the number of rows written (0 when gated off, no receipts, or on error).
    """
    if os.environ.get("SEAM_LEDGER") != "1":
        return 0
    try:
        if not manifest.get("receipts"):
            return 0
        path = _ledger_path()
        session = f"seam:{manifest.get('pipeline')}:{manifest.get('target')}"
        rows = _ledger_rows(manifest, session, _next_invocation_index(path, session))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)
    except Exception as e:  # noqa: BLE001 — telemetry must never break the seam run
        print(f"seam: ledger feed skipped (non-fatal): {e!r}", file=sys.stderr)
        return 0


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
    _append_ledger(manifest)   # objective combo feed (no-op unless SEAM_LEDGER=1)
    return 0 if manifest["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

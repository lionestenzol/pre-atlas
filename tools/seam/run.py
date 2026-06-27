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
  seam zoom <repo> [--top K]                 heterogeneous fidelity: read skeleton over the
                                             whole repo + repomix CARRY on the top-K hot subdirs

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
# FULL  one combined pass that CO-FIRES structural + carry + narrate over a single target,
# so the objective feed actually emits multi-tool combos that INCLUDE the narrator -- the
# only way a deepwiki cofire ever forms (perceive/carry/narrate alone never co-fire it with
# the structural tools). Every stage binds to the same local path: the structural + carry
# tools read it as `root`, deepwiki derives the repo identity from it as `repo`. The
# writes-gated gw index is excluded so the reward is driven by real content delivery, not
# the writes gate; a NARRATE miss (no cached wiki -> ok-but-no-sha) is exactly the
# heterogeneous outcome the per-receipt reward needs to separate one combination from
# another. See ~/.claude/rules/common/code-as-furniture.md.
FULL = [
    ("repo-inventory", "inventory", "root"),
    ("code-recon",     "orient",    "root"),
    ("repomix",        "pack",      "root"),
    ("deepwiki",       "narrate",   "repo"),
]
PIPELINES = {"perceive": PERCEIVE, "carry": CARRY, "narrate": NARRATE, "full": FULL}

# zoom's whole-repo READ skeleton: the cheap, lossy, EVERYWHERE pass. Read tools ONLY
# (no groundwork-cli index -- that is a WRITE, gated off, which would make zoom error by
# default). Keeping it the read pair keeps zoom read-only + all-ok without --writes.
ZOOM_SKELETON = [
    ("repo-inventory", "inventory", "root"),   # read -- file/LOC census + per-subdir regions
    ("code-recon",     "orient",    "root"),   # read -- recon map freshness + content-address
]


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


# ── zoom: heterogeneous-fidelity region selection ─────────────────────────────
# A 'zoom' manifest carries skeleton-everywhere (the cheap read skeleton over the
# whole repo) PLUS lossless content on the HOT regions only. Choosing the hot regions
# is a PURE, deterministic, unit-testable function so the dynamic dispatch branch stays
# thin and the ranking can be tested without a gateway. Two signal sources, in order:
#   1. PRIMARY -- a FRESH repo-inventory receipt already exposes per-immediate-subdir
#      regions (receipt.data.systems[<dir>] = {files, code_lines, primary_language});
#      rank by code_lines desc (truer 'carry weight' than raw file count), then files
#      desc, then directory-name asc (total order -> deterministic). Free when present.
#   2. FALLBACK -- no fresh inventory receipt: walk the tree with stdlib only, ranking
#      immediate subdirs by file count, name tie-break. Reuses the inventory engine's
#      EXCLUDE_DIRS for parity so both paths skip the same noise.
# Both paths are charset-safe: they operate on literal directory-name segments, never
# globs, so the chosen scopes pass the gateway arg charset (which rejects '*').
_SYNTHETIC_ROOT_KEY = "<root>"      # inv.py's loose-files bucket -- never a real subdir


def _engine_exclude_dirs() -> set[str]:
    """The inventory engine's EXCLUDE_DIRS, so the fallback walk skips the same noise.

    Best-effort: if the engine can't be imported (path drift), fall back to a small
    built-in set. Fail-soft -- a missing engine must not break region selection.
    """
    try:
        import importlib.util
        engine = Path(os.environ.get(
            "REPO_INVENTORY_ENGINE",
            "C:/Users/bruke/.claude/skills/repo-inventory/scripts/inventory.py"))
        spec = importlib.util.spec_from_file_location("repo_inventory_engine_excl", engine)
        if spec is not None and spec.loader is not None:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            excl = getattr(mod, "EXCLUDE_DIRS", None)
            if isinstance(excl, set):
                return set(excl)
    except Exception:  # noqa: BLE001 -- engine drift must not break selection
        pass
    return {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
            "build", "target", ".next", "out", "coverage", ".cache", ".claude"}


def _regions_from_inventory(receipts: list[dict]) -> list[str]:
    """Full hot-region ranking from a FRESH repo-inventory receipt, or [] if none.

    Ranks systems by (code_lines desc, files desc, name asc) -- a total order, so the
    result is deterministic. Drops inv.py's synthetic '<root>' loose-files bucket.
    Returns the FULL ranked list; the caller filters carry-eligibility and slices top-K.
    """
    inv = next((r for r in receipts
                if r.get("tool") == "repo-inventory" and r.get("status") == "ok"), None)
    if inv is None:
        return []
    systems = ((inv.get("data") or {}).get("systems")) or {}
    candidates = [(name, meta) for name, meta in systems.items()
                  if name != _SYNTHETIC_ROOT_KEY and isinstance(meta, dict)]
    if not candidates:
        return []
    ranked = sorted(
        candidates,
        key=lambda kv: (-(kv[1].get("code_lines") or 0), -(kv[1].get("files") or 0), kv[0]),
    )
    return [name for name, _meta in ranked]


def _regions_from_walk(repo: str) -> list[str]:
    """Fallback full ranking: immediate subdirs of `repo` by file count (name tie-break).

    Stdlib only, globless. (-count, name) is a total order -> deterministic; no ties
    left to OS iteration order. Returns the FULL ranked list ([] if no measurable
    subdirs); the caller filters carry-eligibility and slices top-K.
    """
    excl = _engine_exclude_dirs()
    counts: dict[str, int] = {}
    try:
        entries = sorted(os.listdir(repo))
    except OSError:
        return []
    for entry in entries:
        full = os.path.join(repo, entry)
        if not os.path.isdir(full) or entry in excl:
            continue
        n = 0
        for _dirpath, dirnames, filenames in os.walk(full):
            dirnames[:] = [d for d in dirnames if d not in excl]
            n += len(filenames)
        counts[entry] = n
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [name for name, _n in ranked]


def _carry_eligible(repo: str, regions: list[str]) -> list[str]:
    """Drop regions whose directory is WHOLLY git-ignored.

    repomix (the CARRY tool) honors .gitignore, so a fully-ignored region packs zero
    files -> an EMPTY carry and a VACUOUS 'lossless' guarantee; the ranking signal
    (on-disk LOC / file count) and the carry (git-tracked files) would disagree. This
    aligns them: a region git cannot track is not carry-eligible, so it is not a hot
    region. One `git check-ignore` call, repo-relative names. Fail-soft: if git is
    unavailable or `repo` is not a work tree (returncode not in {0,1}), do NOT filter --
    we cannot determine ignore status, so we must not silently drop real regions.
    """
    if not regions:
        return regions
    try:
        import subprocess
        # paths as args (not --stdin: that form returns no matches under subprocess on
        # Windows git). check-ignore echoes each ignored pathspec verbatim.
        proc = subprocess.run(
            ["git", "-C", repo, "check-ignore", "--", *regions],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:  # noqa: BLE001 -- best-effort; selection must not break on git issues
        return regions
    if proc.returncode not in (0, 1):       # 0 = some ignored, 1 = none; else not a worktree/error
        return regions
    ignored = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    return [r for r in regions if r not in ignored]


def _hot_regions(repo: str, top: int, receipts: list[dict] | None = None) -> list[str]:
    """The deterministic hot-region selector for `seam zoom`.

    Returns up to `top` immediate-subdir names of `repo` (NOT full paths -- the caller
    joins them repo-relative). Prefers a fresh repo-inventory receipt's per-subdir
    code_lines signal; falls back to an os.walk file-count ranking. Then drops wholly
    git-ignored regions (carry-ineligible -> would yield an empty repomix carry) and
    slices the top-K. Deterministic and charset-safe (directory names only, never globs).
    """
    if top <= 0:
        return []
    ranked = _regions_from_inventory(receipts) if receipts else []
    if not ranked:
        ranked = _regions_from_walk(repo)
    return _carry_eligible(repo, ranked)[:top]


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


def _receipt_ok(r: dict) -> bool:
    """A receipt is a real success only if the tool RAN (status ok) AND produced a join
    key (sha256). A tool that ran but content-addressed nothing -- e.g. NARRATE on a repo
    with no cached wiki (found:false, exit 0) -- contributed nothing to the combination,
    so it must NOT count as success for the objective reward. This is what lets the combo
    feed distinguish a member that delivered content from one that merely didn't crash.
    See ~/.claude/rules/common/code-as-furniture.md.
    """
    return r.get("status") == "ok" and bool(r.get("sha256"))


def _ledger_rows(manifest: dict, session: str, base_index: int) -> list[dict]:
    """One objective row per receipt, matching backfill.py's row schema exactly.

    Reward is PER-RECEIPT (was manifest-shared all-or-nothing): each tool is credited for
    ITS OWN outcome, so in one mixed run a tool that delivered a join key scores +1 while
    one that produced nothing scores -1. Combined with combo.py's per-pair (weakest-member)
    cofire reward, this makes a combination's score reflect which members actually delivered
    -- the prerequisite for combination-specific value to surface instead of every co-fired
    tool sharing one verdict.
    """
    receipts = manifest.get("receipts") or []
    request = f"seam:{manifest.get('pipeline')}:{manifest.get('target')}"[:160].replace("\n", " ")
    rows = []
    for off, r in enumerate(receipts):
        ok_r = _receipt_ok(r)
        reward = 1.0 if ok_r else -1.0
        rows.append({
            "session": session,
            "cwd": str(manifest.get("target")),
            "skill": r.get("tool"),                # surface name = the combo member
            "source": "seam",                      # objective row; distinguishes from transcript-mined
            "invocation_index": base_index + off,
            "request": request,                    # shared turn key -> combo.py groups these as one cofire
            "n_tools_in_turn": len(receipts),
            "reward": "objective_ok" if ok_r else "objective_error",
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
    zm = sub.add_parser("zoom", parents=[common],
                        help="heterogeneous fidelity: read skeleton over the whole repo + repomix CARRY on the hot subdirs")
    zm.add_argument("target", help="a repo / directory path (forward slashes)")
    zm.add_argument("--top", type=int, default=3, help="number of hot subdirs to carry at full fidelity (default 3)")
    fu = sub.add_parser("full", parents=[common],
                        help="FULL combined pass (inventory + orient + carry + narrate) -- co-fires tools so combos including the narrator form")
    fu.add_argument("target", help="a local repo / directory path (forward slashes)")

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

    if a.cmd == "zoom":
        # heterogeneous fidelity in ONE manifest: skeleton EVERYWHERE (read pair over the
        # whole repo) + lossless CARRY on only the HOT regions. zoom is region-dependent
        # (dynamic), so it is its own branch, not a PIPELINES entry. Reuses _call / _emit
        # / _append_ledger / _summary -- no fork.
        if not Path(a.target).is_dir():
            raise SystemExit(f"seam: zoom needs an existing repo directory, got {a.target!r}")
        skeleton = [_call(snap, surface, cap, {arg: a.target}, a.role)
                    for surface, cap, arg in ZOOM_SKELETON]
        regions = _hot_regions(a.target, a.top, receipts=skeleton)
        carry = [_call(snap, "repomix", "pack",
                       {"root": f"{a.target.rstrip('/')}/{region}"}, a.role)
                 for region in regions]
        receipts = skeleton + carry
        manifest = {"pipeline": "zoom", "target": a.target, "produced_at": _now(),
                    "receipts": receipts, "summary": _summary(receipts), "regions": regions}
        _emit(manifest, a.json)
        _append_ledger(manifest)   # objective combo feed (no-op unless SEAM_LEDGER=1)
        return 0 if manifest["summary"]["error"] == 0 else 1

    # perceive / carry / narrate / full -- a named fan-out pipeline over one target
    stages = PIPELINES[a.cmd]
    receipts = [_call(snap, surface, cap, {arg: a.target}, a.role) for surface, cap, arg in stages]
    manifest = {"pipeline": a.cmd, "target": a.target,
                "produced_at": _now(), "receipts": receipts, "summary": _summary(receipts)}
    _emit(manifest, a.json)
    _append_ledger(manifest)   # objective combo feed (no-op unless SEAM_LEDGER=1)
    return 0 if manifest["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

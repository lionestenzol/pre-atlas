#!/usr/bin/env python3
"""code-recon seam adapter -- the orient verdict + the map's content-address as stdout JSON.

Wraps the code-recon orient gate (~/.claude/skills/code-recon/scripts/orient.mjs), which
decides whether a repo's cached delta-scp symbolic map is FRESH / STALE / MISSING. Runs
orient READ-ONLY (never --regen -> no map regeneration, no writes), then content-addresses
the map it gates on (sha256 of the map minus its generated_at stamp -> a stable join key).
assemble-first: a thin read over the existing orient gate; bridges ~/.claude by absolute
path (overridable via CODE_RECON_ORIENT).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ORIENT = os.environ.get(
    "CODE_RECON_ORIENT",
    "C:/Users/bruke/.claude/skills/code-recon/scripts/orient.mjs",
)


def _stable_map_sha(map_path: Path) -> str | None:
    try:
        m = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    canon = {k: v for k, v in m.items() if k != "generated_at"}   # drop the wall-clock stamp
    return hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = args[0] if args else "."
    if not Path(root).is_dir():
        print(json.dumps({"tool": "code-recon", "op": "orient", "found": False,
                          "error": f"not a directory: {root!r}"}))
        return 2
    try:
        proc = subprocess.run(["node", ORIENT, "--repo", root, "--json"],   # READ-ONLY: no --regen
                              capture_output=True, text=True, timeout=18, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"tool": "code-recon", "op": "orient", "found": False,
                          "error": f"orient failed: {exc}"}))
        return 1
    try:
        orient = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(json.dumps({"tool": "code-recon", "op": "orient", "found": False,
                          "error": "orient produced no JSON", "stderr": proc.stderr[-300:]}))
        return 1

    map_path = Path(orient.get("map", ""))
    sha = _stable_map_sha(map_path) if map_path.is_file() else None
    print(json.dumps({
        "tool": "code-recon", "op": "orient",
        "sha256": sha,                                    # content-address of the perceive map (join key)
        "verdict": orient.get("verdict"),
        "action": orient.get("action"),
        "map": str(map_path).replace("\\", "/"),
        "age_hours": orient.get("age_hours"),
        "tokens": orient.get("tokens"),
        "found": sha is not None,
    }))
    return 0 if sha is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""lolbas-enrich seam adapter -- LOLBAS catalog enrichment as a seam surface.

Wraps ~/.claude/skills/code-recon/scripts/lolbas-enrich.mjs (the code-recon
OS-binary rung), invokes it in strict mode on a repo, and content-addresses
the result. The sha256 is stable across runs on the same repo state: it hashes
the finding set (binary + hit file:line list) plus the pack's upstream commit,
dropping all wall-clock stamps (produced_at, generated_utc).

assemble-first: a thin read over the existing lolbas-enrich script; bridges
~/.claude by absolute path (overridable via LOLBAS_ENRICH_SCRIPT). Read-only:
never passes --ledger, so no ledger writes when called through the seam.

Contract: same shape as tools/code-recon/orient_seam.py -- one stdout JSON
line with {tool, op, sha256, found, ...}. Exit 0 on any successful scan
(zero findings is a valid answer, not a failure). Exit >0 on wrapper errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = os.environ.get(
    "LOLBAS_ENRICH_SCRIPT",
    "C:/Users/bruke/.claude/skills/code-recon/scripts/lolbas-enrich.mjs",
)


def _canonical_sha(payload: dict) -> str:
    """Content-address the finding set. Drop wall-clock; keep everything a
    consumer would join on. Same repo state -> same sha, run-to-run."""
    canon = {
        "pack_commit": payload.get("pack", {}).get("upstream_commit"),
        "mode": payload.get("mode"),
        "finding_count": payload.get("finding_count"),
        "total_hits": payload.get("total_hits"),
        # Aggregate binary + sorted hit locations. Context strings are noisy
        # (whitespace, edits move columns) so we key on file:line only.
        "findings": sorted(
            (
                {
                    "binary": f.get("binary"),
                    "hit_count": len(f.get("hits", [])),
                    "hits": sorted(
                        f"{h.get('file')}:{h.get('line')}"
                        for h in f.get("hits", [])
                    ),
                }
                for f in payload.get("findings", [])
            ),
            key=lambda x: x["binary"] or "",
        ),
    }
    return hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = args[0] if args else "."
    if not Path(root).is_dir():
        print(json.dumps({
            "tool": "lolbas-enrich", "op": "scan", "found": False,
            "error": f"not a directory: {root!r}",
        }))
        return 2

    try:
        proc = subprocess.run(
            ["node", SCRIPT, "--repo", root, "--json"],  # READ-ONLY: no --ledger
            capture_output=True, text=True, timeout=18, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({
            "tool": "lolbas-enrich", "op": "scan", "found": False,
            "error": f"lolbas-enrich failed: {exc}",
        }))
        return 1

    if proc.returncode not in (0,):
        print(json.dumps({
            "tool": "lolbas-enrich", "op": "scan", "found": False,
            "error": f"lolbas-enrich exit {proc.returncode}",
            "stderr": (proc.stderr or "")[-300:],
        }))
        return 1

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(json.dumps({
            "tool": "lolbas-enrich", "op": "scan", "found": False,
            "error": "lolbas-enrich produced no JSON",
            "stderr": (proc.stderr or "")[-300:],
        }))
        return 1

    sha = _canonical_sha(payload)
    pack_meta = payload.get("pack") or {}
    print(json.dumps({
        "tool": "lolbas-enrich",
        "op": "scan",
        "sha256": sha,                                # join key for the seam
        "found": True,                                # scan succeeded; empty findings is valid
        "pack_commit": pack_meta.get("upstream_commit"),
        "pack_entries": pack_meta.get("entry_count"),
        "mode": payload.get("mode"),
        "finding_count": payload.get("finding_count", 0),
        "total_hits": payload.get("total_hits", 0),
        "binaries": [f.get("binary") for f in payload.get("findings", [])],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

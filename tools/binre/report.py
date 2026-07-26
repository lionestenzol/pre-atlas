#!/usr/bin/env python3
"""binre seam adapter -- surface a cached report's content-address as stdout JSON.

The binre pipeline (binre.scripts.orchestrate) is ~67s of Ghidra/Frida and writes its
merged artifact to  C:/Users/bruke/binre/out/<sha256-of-binary>/report.json , where the
DIRECTORY NAME is the content-address. The atlas-map seam needs a FAST, read-only command
that surfaces that join key as stdout JSON -- the gateway has a 20s timeout and both
orchestrate and query re-run Ghidra (too heavy). This thin adapter resolves the sha256
(from a bare hash or a binary path), reads the cached report with NO Ghidra and NO writes,
and prints a one-line JSON receipt whose "sha256" is what the seam Receipt lifts as the
join key.

assemble-first: a thin read over binre's OWN artifact, not a reimplementation. It lives in
the Pre Atlas overlay dir (the gateway runs it with cwd = this dir) and bridges to the
separate binre repo by absolute path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

# binre is a separate repo; bridge by absolute path. Overridable for CI / another machine.
BINRE_ROOT = Path(os.environ.get("BINRE_ROOT", "C:/Users/bruke/binre"))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def resolve_sha256(target: str) -> str | None:
    """A bare sha256 hex, or a path to a binary we hash. Mirrors binre query._resolve_sha256."""
    t = target.strip()
    if _SHA256.match(t.lower()):
        return t.lower()
    p = Path(t)
    if p.is_file():
        h = hashlib.sha256()
        with p.open("rb") as fh:                       # stream: never load a big binary whole
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print(json.dumps({"tool": "binre", "op": "report", "found": False,
                          "error": "usage: report.py <sha256|binary-path>"}))
        return 2
    sha = resolve_sha256(args[0])
    if sha is None:
        print(json.dumps({"tool": "binre", "op": "report", "found": False,
                          "error": f"target is neither a sha256 nor an existing file: {args[0]!r}"}))
        return 2

    report_path = BINRE_ROOT / "out" / sha / "report.json"
    if not report_path.is_file():
        print(json.dumps({"tool": "binre", "op": "report", "sha256": sha,
                          "report_path": str(report_path).replace("\\", "/"),
                          "found": False, "error": "no cached report -- run binre.scripts.orchestrate first"}))
        return 1

    try:
        r = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:      # truncated/interrupted Ghidra run, TOCTOU
        print(json.dumps({"tool": "binre", "op": "report", "sha256": sha,
                          "report_path": str(report_path).replace("\\", "/"),
                          "found": False, "error": f"report.json unreadable or invalid JSON: {exc}"}))
        return 1
    print(json.dumps({
        "tool": "binre", "op": "report",
        "sha256": r.get("sha256", sha),                  # the join key (== out-dir name)
        "report_path": str(report_path).replace("\\", "/"),
        "sample": r.get("sample"),
        "duration_ms": r.get("duration_ms"),
        "stages": {name: bool(s.get("ok")) for name, s in (r.get("stages") or {}).items()},
        "found": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""repo-inventory seam adapter -- a content-addressed repo census as stdout JSON.

Wraps the deterministic inventory engine (~/.claude/skills/repo-inventory/scripts/
inventory.py): same repo in -> same inventory out, stdlib only. Prints a seam receipt
whose sha256 is over the canonical inventory MINUS the absolute root, so the join key is
content-stable across clones/paths (same convention as gw). assemble-first: a thin read
over the existing engine, no reimplementation; bridges the skill dir by absolute path
(overridable via REPO_INVENTORY_ENGINE).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

ENGINE = Path(os.environ.get(
    "REPO_INVENTORY_ENGINE",
    "C:/Users/bruke/.claude/skills/repo-inventory/scripts/inventory.py",
))


def _load_engine():
    spec = importlib.util.spec_from_file_location("repo_inventory_engine", ENGINE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load inventory engine at {ENGINE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)              # body only defines fns/consts; main() is __main__-gated
    return mod


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = args[0] if args else "."
    if not Path(root).is_dir():
        print(json.dumps({"tool": "repo-inventory", "op": "inventory", "found": False,
                          "error": f"not a directory: {root!r}"}))
        return 2
    try:
        result = _load_engine().analyze(root)
    except Exception as exc:                  # engine import/walk failure -> JSON, never a bare traceback
        print(json.dumps({"tool": "repo-inventory", "op": "inventory", "found": False,
                          "error": f"inventory engine failed: {exc}"}))
        return 1

    # content-address: hash the canonical inventory WITHOUT the absolute root, so the same
    # tree yields the same join key wherever it is checked out.
    canon = {k: v for k, v in result.items() if k != "root"}
    digest = hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    systems = result.get("systems", {})
    print(json.dumps({
        "tool": "repo-inventory", "op": "inventory", "sha256": digest,
        "system_count": len(systems),
        "total_files": sum(s.get("files", 0) for s in systems.values()),
        "total_code_lines": sum(s.get("code_lines", 0) for s in systems.values()),
        "systems": {n: {"files": s.get("files"), "code_lines": s.get("code_lines"),
                        "primary_language": s.get("primary_language")}
                    for n, s in systems.items()},
        "found": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

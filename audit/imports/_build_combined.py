#!/usr/bin/env python3
"""Build audit/imports/_combined.json — per-subsystem file graphs for EVERY
entry in system-index.json (not just the hand-picked services that had import
graphs). This is what powers the map's file-level drill-down + source previews.

For each subsystem path:
  - nodes  = every code/doc file (relative path)
  - edges  = best-effort import graph
               · Python   -> ast (exact)
               · TS/JS     -> regex on `import ... from '...'` / require('...')
               · other     -> no edges (still a previewable node)

Output shape mirrors madge --json: { "rel/path.ext": ["import", ...] }, keyed
by subsystem name, so _build_map.py consumes it unchanged.

Usage: python _build_combined.py [--root <repo>]
"""
import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".rs", ".go", ".java"}
DOC_EXT = {".md", ".json", ".yaml", ".yml", ".toml"}
NODE_EXT = CODE_EXT | DOC_EXT
EXCLUDE = {"node_modules", ".git", ".venv", "venv", "__pycache__",
           "dist", "build", ".pytest_cache", ".mypy_cache", "target", ".next",
           "_retired"}

TS_IMPORT = re.compile(r"""(?:import|export)[^'"]*?from\s*['"]([^'"]+)['"]""")
TS_REQUIRE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
TS_BARE_IMPORT = re.compile(r"""(?:^|\n)\s*import\s+['"]([^'"]+)['"]""")


def py_imports(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=str(path))
    except (SyntaxError, ValueError, UnicodeDecodeError, OSError):
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = "." * (node.level or 0)
            base = f"{level}{mod}" if mod else level
            for alias in node.names:
                out.append(f"{base}.{alias.name}" if base else alias.name)
    return sorted(set(out))


def ts_imports(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except OSError:
        return []
    found = set()
    for rx in (TS_IMPORT, TS_REQUIRE, TS_BARE_IMPORT):
        for m in rx.finditer(txt):
            spec = m.group(1)
            # keep relative imports (resolvable within the subsystem); drop bare pkgs
            if spec.startswith("."):
                spec = spec.lstrip("./")
                found.add(spec)
    return sorted(found)


def build_graph(sub_dir, top_level_only=False):
    graph = {}
    if top_level_only:
        items = [(str(sub_dir), [], os.listdir(sub_dir))]
    else:
        items = os.walk(sub_dir)
    for dp, dn, fns in items:
        if not top_level_only:
            dn[:] = [d for d in dn if d not in EXCLUDE and not d.startswith(".")]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in NODE_EXT:
                continue
            abs_path = os.path.join(dp, fn)
            if top_level_only and not os.path.isfile(abs_path):
                continue
            rel = os.path.relpath(abs_path, sub_dir).replace("\\", "/")
            if ext == ".py":
                graph[rel] = py_imports(abs_path)
            elif ext in (".ts", ".tsx", ".js", ".jsx"):
                graph[rel] = ts_imports(abs_path)
            else:
                graph[rel] = []
    return graph


def main():
    p = argparse.ArgumentParser(prog="_build_combined")
    p.add_argument("--root", type=Path, default=None)
    args = p.parse_args()
    root = (args.root or Path(__file__).resolve().parents[2]).resolve()

    idx_path = root / "audit" / "system-index.json"
    if not idx_path.is_file():
        print(f"[error] missing {idx_path} — run _refresh_system_index.py first", file=sys.stderr)
        return 2
    idx = json.loads(idx_path.read_text(encoding="utf-8"))

    combined = {}
    for e in idx["entries"]:
        rel = e["path"]
        sub_dir = root / rel
        if not sub_dir.is_dir():
            continue
        top_only = (rel == ".")  # the "_root" node: loose files only, no recursion
        graph = build_graph(sub_dir, top_level_only=top_only)
        if graph:
            combined[e["name"]] = graph

    out = root / "audit" / "imports" / "_combined.json"
    out.write_text(json.dumps(combined, indent=2, sort_keys=True), encoding="utf-8")
    total_nodes = sum(len(g) for g in combined.values())
    print(f"Wrote {out}")
    print(f"  - {len(combined)} subsystems with file graphs")
    print(f"  - {total_nodes} file nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

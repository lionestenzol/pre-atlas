#!/usr/bin/env python3
"""Extract python import graph for a service. Stdlib only.

Usage: python py_imports.py <service_root> [out.json]

Output: { "relative/path/file.py": ["imported.module.x", ...] }
Mirrors madge --json shape so the two can merge.
"""
import ast
import json
import os
import sys

EXCLUDE = {"__pycache__", "venv", ".venv", "env", ".env", "node_modules",
           "dist", "build", ".pytest_cache", ".mypy_cache", "target"}


def imports_in_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=path)
    except (SyntaxError, ValueError, UnicodeDecodeError):
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
                if base:
                    out.append(f"{base}.{alias.name}")
                else:
                    out.append(alias.name)
    return sorted(set(out))


def walk_service(root):
    graph = {}
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE]
        for fn in fns:
            if fn.endswith(".py"):
                abs_path = os.path.join(dp, fn)
                rel = os.path.relpath(abs_path, root).replace("\\", "/")
                graph[rel] = imports_in_file(abs_path)
    return graph


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: py_imports.py <service_root> [out.json]")
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    g = walk_service(root)
    j = json.dumps(g, indent=2, sort_keys=True)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(j)
        print(f"{len(g)} files -> {out}")
    else:
        print(j)

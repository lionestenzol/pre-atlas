#!/usr/bin/env python3
"""Refresh audit/system-index.json with current filesystem reality.

Walks services/, apps/, tools/ at depth 1. For each subdir:
  - language: detect from file extensions
  - framework: best-effort from package.json/pyproject.toml
  - deps: from package.json or requirements.txt or pyproject.toml
  - entry_points: server.ts / main.py / index.* / serve.py
  - file_count: count of code/doc files
  - total_loc: count lines in code files
  - port: scrape source for 'PORT = 30XX' / '--port 30XX' / 'listen(30XX'
  - in_autostart: presence in scripts/start_atlas.ps1
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_parser = argparse.ArgumentParser(
    prog="_refresh_system_index",
    description="Refresh audit/system-index.json with current filesystem reality.",
)
_parser.add_argument("root", nargs="?", default=None,
                     help="repo root (positional, optional — also accepts --root)")
_parser.add_argument("--root", dest="root_flag", default=None,
                     help="repo root (default: script's grandparent)")
_args = _parser.parse_args()

_root_value = _args.root_flag or _args.root
ROOT = Path(_root_value).resolve() if _root_value else Path(__file__).resolve().parents[2]
if not ROOT.is_dir():
    print(f"[error] --root does not exist: {ROOT}", file=sys.stderr)
    sys.exit(2)
OUT = ROOT / "audit" / "system-index.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

LANG_EXT = {".py":"py", ".ts":"ts", ".tsx":"ts", ".js":"js", ".jsx":"js",
            ".html":"html", ".css":"css", ".rs":"rs", ".go":"go", ".java":"java"}
CODE_EXT = set(LANG_EXT)
DOC_EXT = {".md", ".json", ".yaml", ".yml", ".toml"}
# "_retired" quarantined per atlas-consolidation task 2.4 (see ~/.claude/rules/common/code-as-furniture.md - excluded, not deleted; decision #4 pending)
EXCLUDE = {"node_modules", ".git", ".venv", "venv", "__pycache__",
           "dist", "build", ".pytest_cache", ".mypy_cache", "target", ".next",
           "_retired"}

# Wave 2.1 (atlas-consolidation AC0002): vendored/retired blobs must not inflate
# the canonical count. anatomy-research alone was 571,924 LOC = 62% of the old total.
# See ~/.claude/rules/common/code-as-furniture.md — no broken code left in place.
EXCLUDE_SUBSYSTEMS = {"tools/anatomy-research", "services/_retired", "apps/_retired"}

# Extra top-level dirs surfaced as single nodes so the WHOLE repo is on the map
# (not just services/apps/tools). Each dir becomes one node under a synthetic
# group bucket. Junk dirs (backups, tmp, logs, dist) are intentionally omitted.
SINGLETON_DIRS = {
    "contracts": "spec", "doctrine": "spec",
    "research": "research", "_research": "research", "experiments": "research",
    "audit": "ops", "scripts": "ops", "data": "ops", "public": "ops",
    "anatomy": "ops", "workflows": "ops", "scorecards": "ops",
    "migrations": "ops", "docs": "ops",
}

PORT_RE = re.compile(r"(?:port\s*[:=]\s*|--port[= ]|listen\(|:300\d|:301\d|:308\d|:888\d)(\d{4})", re.IGNORECASE)


def walk(root):
    code = 0
    loc = 0
    docs = 0
    langs = {}
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE and not d.startswith(".")]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in CODE_EXT:
                code += 1
                langs[LANG_EXT[ext]] = langs.get(LANG_EXT[ext], 0) + 1
                try:
                    with open(os.path.join(dp, fn), "rb") as f:
                        loc += sum(1 for _ in f)
                except OSError:
                    pass
            elif ext in DOC_EXT:
                docs += 1
    return code, docs, loc, langs


def primary_lang(langs):
    if not langs:
        return "unknown"
    return max(langs.items(), key=lambda kv: kv[1])[0]


def detect_framework(root, lang):
    pkg = root / "package.json"
    if pkg.exists():
        try:
            j = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**j.get("dependencies", {}), **j.get("devDependencies", {})}
            for fw in ("next", "express", "fastify", "vite", "react", "vue"):
                if fw in deps:
                    return fw
        except Exception:
            pass
    pyp = root / "pyproject.toml"
    req = root / "requirements.txt"
    for f in (pyp, req):
        if f.exists():
            try:
                txt = f.read_text(encoding="utf-8")
                for fw in ("fastapi", "django", "flask", "uvicorn", "starlette"):
                    if fw in txt.lower():
                        return fw
            except Exception:
                pass
    return "unknown"


def extract_deps(root):
    deps = []
    pkg = root / "package.json"
    if pkg.exists():
        try:
            j = json.loads(pkg.read_text(encoding="utf-8"))
            deps += list(j.get("dependencies", {}).keys())
            deps += list(j.get("devDependencies", {}).keys())
        except Exception:
            pass
    req = root / "requirements.txt"
    if req.exists():
        try:
            for line in req.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    deps.append(re.split(r"[<>=!~ ]", line)[0])
        except Exception:
            pass
    return sorted(set(deps))


def find_entry_points(root):
    candidates = ["src/api/server.ts", "src/server.ts", "src/main.ts",
                  "src/index.ts", "main.py", "server.py", "app.py",
                  "src/index.js", "index.js", "index.html"]
    found = []
    for c in candidates:
        if (root / c).exists():
            found.append(c)
    return found


def find_port(root):
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE and not d.startswith(".")]
        for fn in fns:
            if not (fn.endswith((".py", ".ts", ".js", ".json"))):
                continue
            try:
                with open(os.path.join(dp, fn), "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read(8000)
            except OSError:
                continue
            for m in PORT_RE.finditer(txt):
                p = int(m.group(1))
                if 3000 <= p <= 3999 or p in (8000, 8080, 8887, 8888):
                    return p
    return None


def get_start_script_ports():
    """Authoritative name/cwd -> port map from scripts/start_atlas.ps1.
    Fixes the port bug where find_port()'s first-match source scrape assigned
    aegis-fabric port 3010 (optogon's port); start_atlas.ps1 declares 3002."""
    auto = ROOT / "scripts" / "start_atlas.ps1"
    out = {}
    if not auto.exists():
        return out
    txt = auto.read_text(encoding="utf-8", errors="ignore")
    pat = re.compile(r'@\{\s*Name\s*=\s*"([^"]+)";\s*Port\s*=\s*(\d+);\s*Cwd\s*=\s*"([^"]+)"', re.IGNORECASE)
    for name, port, cwd in pat.findall(txt):
        out[name.lower()] = int(port)
        cwd_tail = cwd.replace("$RepoRoot\\", "").replace("$RepoRoot/", "").replace("\\", "/").lower()
        out[cwd_tail] = int(port)
    return out


def get_autostart_set():
    auto = ROOT / "scripts" / "start_atlas.ps1"
    if not auto.exists():
        return set()
    txt = auto.read_text(encoding="utf-8", errors="ignore")
    # extract anything that looks like services/<name> or apps/<name>
    names = set(re.findall(r"(?:services|apps|tools)[/\\]([a-z0-9_-]+)", txt, re.IGNORECASE))
    return names


def analyze_dir(parent_name, sub):
    path = ROOT / parent_name / sub
    if not path.is_dir():
        return None
    code, docs, loc, langs = walk(path)
    lang = primary_lang(langs)
    return {
        "path": f"{parent_name}/{sub}",
        "name": sub,
        "group": parent_name,
        "language": lang if not (len(langs) >= 2 and langs.get("py", 0) > 5 and langs.get("ts", 0) > 5) else "mixed",
        "framework": detect_framework(path, lang),
        "deps": extract_deps(path),
        "entry_points": find_entry_points(path),
        "file_count": code + docs,
        "total_loc": loc,
        "port": START_PORTS.get(sub.lower(),
                START_PORTS.get(f"{parent_name}/{sub}".lower(),
                find_port(path))),
        "in_autostart": sub in autostart_names,
    }


def analyze_singleton(dirname, bucket):
    """A whole top-level dir treated as a single node (files are mostly flat)."""
    path = ROOT / dirname
    if not path.is_dir():
        return None
    code, docs, loc, langs = walk(path)
    if code + docs == 0:
        return None
    return {
        "path": dirname,
        "name": dirname,
        "group": bucket,
        "language": primary_lang(langs),
        "framework": "unknown",
        "deps": [],
        "entry_points": [],
        "file_count": code + docs,
        "total_loc": loc,
        "port": None,
        "in_autostart": False,
    }


def analyze_root_files():
    """Loose code/doc files living directly at the repo root (depth 0)."""
    code = docs = loc = 0
    langs = {}
    for fn in os.listdir(ROOT):
        fp = ROOT / fn
        if not fp.is_file():
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext in CODE_EXT:
            code += 1
            langs[LANG_EXT[ext]] = langs.get(LANG_EXT[ext], 0) + 1
            try:
                with open(fp, "rb") as f:
                    loc += sum(1 for _ in f)
            except OSError:
                pass
        elif ext in DOC_EXT:
            docs += 1
    if code + docs == 0:
        return None
    return {
        "path": ".",
        "name": "_root",
        "group": "root",
        "language": primary_lang(langs),
        "framework": "unknown",
        "deps": [],
        "entry_points": [],
        "file_count": code + docs,
        "total_loc": loc,
        "port": None,
        "in_autostart": False,
    }


autostart_names = get_autostart_set()
START_PORTS = get_start_script_ports()

entries = []
for parent in ("services", "apps", "tools"):
    pdir = ROOT / parent
    if not pdir.is_dir():
        continue
    for sub in sorted(os.listdir(pdir)):
        if sub.startswith(".") or sub in EXCLUDE:
            continue
        if not (pdir / sub).is_dir():
            continue
        if f"{parent}/{sub}" in EXCLUDE_SUBSYSTEMS:
            continue
        e = analyze_dir(parent, sub)
        if e:
            entries.append(e)

# Wide coverage: surface extra top-level dirs + loose root files as nodes.
for dirname, bucket in sorted(SINGLETON_DIRS.items()):
    e = analyze_singleton(dirname, bucket)
    if e:
        entries.append(e)
root_entry = analyze_root_files()
if root_entry:
    entries.append(root_entry)

result = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "repo_root": str(ROOT),
    "subsystem_count": len(entries),
    "autostart_count": sum(1 for e in entries if e["in_autostart"]),
    "entries": entries,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

print(f"Wrote {OUT}")
print(f"  - {len(entries)} subsystems")
print(f"  - {result['autostart_count']} in autostart")
print(f"  - new vs prior: ", end="")
prior_names = set()
prior_path = ROOT / "audit" / "system-index.json.prior"
# nothing to compare against; just list everything
print(", ".join(e["name"] for e in entries))

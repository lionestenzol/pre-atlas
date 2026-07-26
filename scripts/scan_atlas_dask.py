"""
scan_atlas_dask.py — parallel orient-phase recon over every Atlas subsystem,
routed through the zoekt shard where zoekt has an advantage.

Runs the deterministic (no-LLM) rungs of the code-recon ladder in parallel
via Dask. Per subsystem: tokei LOC, walk file counts, TODO/FIXME sweep,
secret-pattern sniff, symbol counts, git churn. Rolls up to JSON + Markdown.

Where zoekt is used (memory-mapped shard, no filesystem walk):
    - TODOs / FIXMEs / HACK / XXX / BUG    (all languages)
    - Secret-pattern sniff                 (all languages)
    - Symbol counts                        (TS/JS/TSX/JSX only)

Where zoekt does NOT help (falls back to native tools):
    - Python symbol counts   → ctags (scip-ctags in the index doesn't index py)
    - tokei LOC              → tokei (zoekt doesn't count LOC)
    - Git churn              → git log (zoekt doesn't touch git)
    - File walk by extension → os.walk (per-subdir counts, not a shard question)

Design note: the original "one bulk preload query" plan didn't survive contact
with zoekt's internal ShardMaxMatchCount cap (~6k symbols repo-wide for sym:.);
the CLI has no flag to raise it. Per-subsystem scoped queries stay under the
cap and are still parallelizable via Dask, so the win is architectural: fewer
subprocess spawns per rung + shard reads instead of filesystem walks.

Slicing:  audit/system-index.json (60 subsystems). Falls back to globbing
          services/*, apps/*, tools/* if the manifest is stale/missing.

Usage:
    python scripts/scan_atlas_dask.py                    # full scan, 8 workers
    python scripts/scan_atlas_dask.py --workers 12
    python scripts/scan_atlas_dask.py --only delta-kernel,cortex
    python scripts/scan_atlas_dask.py --no-git           # skip churn (fast)
    python scripts/scan_atlas_dask.py --no-zoekt         # force rg/ctags path
    python scripts/scan_atlas_dask.py --dashboard        # keep :8787 open

Outputs (audit/):
    scan_atlas_dask_<UTC-date>.json   full structured report
    scan_atlas_dask_<UTC-date>.md     summary table
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SYSTEM_INDEX = REPO_ROOT / "audit" / "system-index.json"
OUT_DIR = REPO_ROOT / "audit"

ZOEKT_BIN = Path(os.environ.get("ZOEKT_BIN", r"C:\Users\bruke\go\bin\zoekt.exe"))
ZOEKT_INDEX_DIR = Path(os.environ.get("ZOEKT_INDEX_DIR", r"C:\Users\bruke\zoekt-win\index"))

# Exclude this scan's own output files so a rerun doesn't re-detect the
# previous run's secret-pattern lines as "new" hits (self-eating recursion).
SELF_EXCLUDE_ZOEKT = "-file:scan_atlas_dask_"
SELF_EXCLUDE_RG_GLOBS = ["--glob", "!scan_atlas_dask_*.md", "--glob", "!scan_atlas_dask_*.json"]

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "bower_components",
    "dist", "build", "out", ".next", ".nuxt", ".turbo",
    ".wasp", ".worktrees", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "coverage", ".nyc_output",
    "target",
}

SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private_key_header"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "github_token"),
    (r"sk-[A-Za-z0-9]{20,}", "openai_style_secret"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "slack_token"),
]

TODO_TAGS = ["TODO", "FIXME", "HACK", "XXX", "BUG"]

ZOEKT_TS_LANGS = {"ts", "tsx", "js", "jsx", "typescript", "javascript"}

# Languages tokei reports but that are data/prose, not source code.
# Kept in by_lang for visibility; excluded from code_loc so a single fixture
# dump can't dominate the totals.
TOKEI_DATA_LANGS = {
    "JSON", "JSON5", "YAML", "TOML", "XML", "SVG", "CSV", "TSV",
    "Markdown", "reStructuredText", "AsciiDoc", "Org", "Plain Text",
    "Jupyter Notebooks", "HTML",
}


# ------------- infra helpers -------------


def run(cmd: list[str], cwd: Path | None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a subprocess, capture output, never raise on nonzero exit."""
    try:
        p = subprocess.run(
            cmd, cwd=(str(cwd) if cwd else None),
            capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def zoekt_available() -> bool:
    return ZOEKT_BIN.exists() and ZOEKT_INDEX_DIR.is_dir() and any(ZOEKT_INDEX_DIR.glob("*.zoekt"))


def repo_regex() -> str:
    """Zoekt r:^...$ pattern for this repo. Spaces become `.` (zoekt uses RE2
    on the repo name, which stores 'Pre Atlas' literally)."""
    name = REPO_ROOT.name
    return "^" + re.escape(name).replace(r"\ ", ".") + "$"


def zoekt_scope(sub_path: str) -> str:
    """`file:` filter for a subsystem. Path separators become `.` because
    zoekt stores Windows paths with `\\` and we want RE2 to match either.
    Example: services/aegis-fabric → 'services.aegis-fabric'."""
    return sub_path.replace("/", ".").replace("\\", ".")


def zoekt_query(query: str, timeout: int = 20) -> list[dict[str, Any]]:
    """Run one zoekt JSONL query, return list of parsed FileMatch dicts."""
    if not zoekt_available():
        return []
    code, out, err = run(
        [str(ZOEKT_BIN), "-jsonl", "-index_dir", str(ZOEKT_INDEX_DIR), query],
        cwd=None, timeout=timeout,
    )
    if code != 0 or not out:
        return []
    hits: list[dict[str, Any]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            hits.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return hits


def load_subsystems(only: set[str] | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if SYSTEM_INDEX.exists():
        with SYSTEM_INDEX.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("entries", []):
            entries.append({
                "name": e.get("name"),
                "path": e.get("path"),
                "group": e.get("group"),
                "language": (e.get("language") or "").lower(),
                "framework": e.get("framework"),
                "port": e.get("port"),
                "manifest_files": e.get("file_count"),
                "manifest_loc": e.get("total_loc"),
                "entry_points": e.get("entry_points", []),
                "deps": e.get("deps", []),
            })
    else:
        for group in ("services", "apps", "tools"):
            gdir = REPO_ROOT / group
            if not gdir.is_dir():
                continue
            for child in sorted(gdir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    entries.append({
                        "name": child.name,
                        "path": f"{group}/{child.name}",
                        "group": group, "language": "",
                    })
    if only:
        entries = [e for e in entries if e["name"] in only]
    return entries


# ------------- per-subsystem rungs -------------


def rung_tokei(abs_path: Path) -> dict[str, Any]:
    if not abs_path.exists():
        return {"ok": False, "reason": "missing path"}
    excludes = sum((["--exclude", d] for d in SKIP_DIRS), [])
    code, out, err = run(
        ["tokei", "--output", "json", *excludes, str(abs_path)], REPO_ROOT, 60
    )
    if code != 0 or not out.strip():
        return {"ok": False, "reason": (err or "tokei failed")[:120], "code": code}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "bad json"}
    langs: dict[str, dict[str, int]] = {}
    total_code = 0
    total_data = 0
    for lang, v in data.items():
        if lang == "Total":
            continue
        c = int(v.get("code", 0))
        langs[lang] = {"code": c}
        if lang in TOKEI_DATA_LANGS:
            total_data += c
        else:
            total_code += c
    return {
        "ok": True,
        "code_loc": total_code,
        "data_loc": total_data,
        "by_lang": langs,
    }


def rung_walk(abs_path: Path) -> dict[str, Any]:
    if not abs_path.exists():
        return {"files": 0, "by_ext": {}}
    counts: dict[str, int] = {}
    total = 0
    for root, dirs, files in os.walk(abs_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            ext = Path(fn).suffix.lower() or "<none>"
            counts[ext] = counts.get(ext, 0) + 1
            total += 1
    return {"files": total, "by_ext": dict(sorted(counts.items(), key=lambda kv: -kv[1])[:15])}


def rung_todos_zoekt(sub: dict[str, Any]) -> dict[str, Any]:
    """TODO/FIXME sweep via zoekt scoped file: query."""
    pat = "|".join(TODO_TAGS)
    hits = zoekt_query(f"r:{repo_regex()} file:{zoekt_scope(sub['path'])} {SELF_EXCLUDE_ZOEKT} ({pat})", timeout=20)
    counts: dict[str, int] = {t: 0 for t in TODO_TAGS}
    sample: list[str] = []
    for fm in hits:
        for lm in fm.get("LineMatches", []) or []:
            try:
                text = base64.b64decode(lm.get("Line", "")).decode("utf-8", errors="replace")
            except Exception:
                text = ""
            for t in TODO_TAGS:
                if re.search(rf"\b{t}\b", text):
                    counts[t] += 1
                    if len(sample) < 5:
                        rel = fm.get("FileName", "").replace(str(REPO_ROOT) + os.sep, "")
                        sample.append(f"{rel}:{lm.get('LineNumber')}: {text.strip()[:140]}")
                    break
    return {"via": "zoekt", "total": sum(counts.values()), "by_tag": counts, "sample": sample}


def rung_todos_rg(abs_path: Path) -> dict[str, Any]:
    if not abs_path.exists():
        return {"via": "rg", "total": 0, "by_tag": {}}
    pat = r"\b(" + "|".join(TODO_TAGS) + r")\b"
    ignore = sum((["--glob", f"!{d}"] for d in SKIP_DIRS), []) + SELF_EXCLUDE_RG_GLOBS
    code, out, _ = run(["rg", "--no-heading", "--line-number", "-e", pat, *ignore, "."], abs_path, 60)
    counts: dict[str, int] = {t: 0 for t in TODO_TAGS}
    sample: list[str] = []
    if out:
        for line in out.splitlines():
            for t in TODO_TAGS:
                if re.search(rf"\b{t}\b", line):
                    counts[t] += 1
                    if len(sample) < 5:
                        sample.append(line[:180])
                    break
    return {"via": "rg", "total": sum(counts.values()), "by_tag": counts, "sample": sample}


def rung_secrets_zoekt(sub: dict[str, Any]) -> dict[str, Any]:
    hits_out: list[dict[str, Any]] = []
    scope = zoekt_scope(sub["path"])
    for pat, label in SECRET_PATTERNS:
        fms = zoekt_query(f"r:{repo_regex()} file:{scope} {SELF_EXCLUDE_ZOEKT} {pat}", timeout=20)
        for fm in fms:
            for lm in fm.get("LineMatches", []) or []:
                try:
                    text = base64.b64decode(lm.get("Line", "")).decode("utf-8", errors="replace")
                except Exception:
                    text = ""
                if len(hits_out) < 20:
                    rel = fm.get("FileName", "").replace(str(REPO_ROOT) + os.sep, "")
                    hits_out.append({"label": label, "hit": f"{rel}:{lm.get('LineNumber')}: {text.strip()[:200]}"})
    return {"via": "zoekt", "hits": hits_out, "count": len(hits_out)}


def rung_secrets_rg(abs_path: Path) -> dict[str, Any]:
    if not abs_path.exists():
        return {"via": "rg", "hits": [], "count": 0}
    hits: list[dict[str, Any]] = []
    ignore = sum((["--glob", f"!{d}"] for d in SKIP_DIRS), []) + SELF_EXCLUDE_RG_GLOBS
    for pat, label in SECRET_PATTERNS:
        code, out, _ = run(["rg", "--no-heading", "--line-number", "-e", pat, *ignore, "."], abs_path, 45)
        if out:
            for line in out.splitlines()[:5]:
                hits.append({"label": label, "hit": line[:200]})
    return {"via": "rg", "hits": hits, "count": len(hits)}


def rung_symbols_zoekt(sub: dict[str, Any]) -> dict[str, Any]:
    """Symbol counts via zoekt sym:. — TS/JS only (scip-ctags in the index
    doesn't cover Python/Go/etc)."""
    hits = zoekt_query(f"r:{repo_regex()} file:{zoekt_scope(sub['path'])} {SELF_EXCLUDE_ZOEKT} sym:.", timeout=20)
    kinds: dict[str, int] = {}
    total = 0
    top: list[str] = []
    for fm in hits:
        for lm in fm.get("LineMatches", []) or []:
            for lf in lm.get("LineFragments", []) or []:
                si = lf.get("SymbolInfo")
                if not si:
                    continue
                kind = si.get("Kind", "unknown")
                kinds[kind] = kinds.get(kind, 0) + 1
                total += 1
                if len(top) < 10:
                    top.append(f"{si.get('Kind','?')} {si.get('Sym','?')}")
    return {"via": "zoekt", "symbols": total, "by_kind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:10]), "sample": top}


def rung_symbols_ctags(abs_path: Path) -> dict[str, Any]:
    if not abs_path.exists():
        return {"via": "ctags", "symbols": 0, "by_kind": {}}
    exclude = sum((["--exclude=" + d] for d in SKIP_DIRS), [])
    code, out, err = run(["ctags", "-R", "-f", "-", "--fields=+K", *exclude, "."], abs_path, 90)
    if code != 0 or not out:
        return {"via": "ctags", "symbols": 0, "by_kind": {}, "reason": err.strip()[:120]}
    kinds: dict[str, int] = {}
    total = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            k = parts[3].strip()
            kinds[k] = kinds.get(k, 0) + 1
            total += 1
    return {"via": "ctags", "symbols": total, "by_kind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:10])}


def rung_git_churn(abs_path: Path, days: int = 30) -> dict[str, Any]:
    rel = abs_path.relative_to(REPO_ROOT) if abs_path.is_relative_to(REPO_ROOT) else abs_path
    code, out, err = run(
        ["git", "log", f"--since={days}.days", "--pretty=format:%h", "--", str(rel)],
        REPO_ROOT, 30,
    )
    if code != 0:
        return {"ok": False, "reason": err.strip()[:120]}
    commits = [c for c in out.splitlines() if c.strip()]
    _, out2, _ = run(
        ["git", "log", f"--since={days}.days", "--pretty=format:%an", "--", str(rel)],
        REPO_ROOT, 30,
    )
    authors = sorted(set(a for a in (out2 or "").splitlines() if a.strip()))
    return {"ok": True, "commits_30d": len(commits), "authors_30d": authors[:5]}


def scan_one(sub: dict[str, Any], want_git: bool, use_zoekt: bool) -> dict[str, Any]:
    t0 = time.time()
    abs_path = REPO_ROOT / sub["path"] if sub.get("path") else None
    result: dict[str, Any] = {
        "name": sub["name"], "path": sub.get("path"), "group": sub.get("group"),
        "language": sub.get("language"), "framework": sub.get("framework"),
        "port": sub.get("port"), "entry_points": sub.get("entry_points", []),
        "dep_count": len(sub.get("deps", []) or []),
    }
    if not abs_path or not abs_path.exists():
        result["error"] = f"path missing: {abs_path}"
        result["duration_s"] = round(time.time() - t0, 2)
        return result

    # Rungs that always run the same way
    result["tokei"] = rung_tokei(abs_path)
    result["walk"] = rung_walk(abs_path)
    if want_git:
        result["git"] = rung_git_churn(abs_path)

    # Rungs that route based on zoekt availability + subsystem language
    if use_zoekt:
        result["todos"] = rung_todos_zoekt(sub)
        result["secrets"] = rung_secrets_zoekt(sub)
        lang = (sub.get("language") or "").lower()
        if lang in ZOEKT_TS_LANGS:
            result["symbols"] = rung_symbols_zoekt(sub)
        else:
            result["symbols"] = rung_symbols_ctags(abs_path)
    else:
        result["todos"] = rung_todos_rg(abs_path)
        result["secrets"] = rung_secrets_rg(abs_path)
        result["symbols"] = rung_symbols_ctags(abs_path)

    result["duration_s"] = round(time.time() - t0, 2)
    return result


# ------------- rollup -------------


def render_markdown(report: dict[str, Any]) -> str:
    m = report["meta"]
    lines: list[str] = []
    lines.append(f"# Atlas recon scan · {m['generated_at']}")
    lines.append("")
    lines.append(f"- Subsystems scanned: **{m['subsystem_count']}**")
    lines.append(f"- Total wall time: **{m['wall_s']}s** across **{m['workers']}** Dask workers")
    lines.append(f"- Zoekt path used: **{m['zoekt_used']}** (index: `{ZOEKT_INDEX_DIR}`)")
    lines.append(f"- Total code LOC (tokei): **{m['total_code_loc']:,}**")
    lines.append(f"- Total data LOC (JSON/YAML/XML/MD/HTML, excluded from code): **{m.get('total_data_loc', 0):,}**")
    lines.append(f"- Total files (walk): **{m['total_files']:,}**")
    lines.append(f"- Total TODOs/FIXMEs: **{m['total_todos']:,}**")
    lines.append(f"- Total symbols: **{m['total_symbols']:,}** (zoekt for TS/JS, ctags for the rest)")
    lines.append(f"- Secret-pattern hits: **{m['total_secret_hits']}** (review before ignoring)")
    lines.append("")
    lines.append("## Per-subsystem summary")
    lines.append("")
    lines.append("| Subsystem | Lang | LOC | Files | Symbols (via) | TODOs | Secrets | 30d commits | Port |")
    lines.append("|---|---|---:|---:|---|---:|---:|---:|---:|")
    for r in sorted(report["subsystems"], key=lambda x: -(x.get("tokei", {}).get("code_loc") or 0)):
        if "error" in r:
            lines.append(f"| {r['name']} | ? | ? | ? | ? | ? | ? | ? | ? | <!-- {r['error']} -->")
            continue
        loc = r.get("tokei", {}).get("code_loc") or 0
        files = r.get("walk", {}).get("files") or 0
        syms_rung = r.get("symbols", {})
        syms = syms_rung.get("symbols") or 0
        via = syms_rung.get("via", "?")
        todos = r.get("todos", {}).get("total") or 0
        secs = r.get("secrets", {}).get("count") or 0
        commits = (r.get("git") or {}).get("commits_30d", "-")
        port = r.get("port") or "-"
        lang = r.get("language") or "-"
        lines.append(f"| {r['name']} | {lang} | {loc:,} | {files:,} | {syms:,} ({via}) | {todos} | {secs} | {commits} | {port} |")
    lines.append("")
    if m["total_secret_hits"] > 0:
        lines.append("## Secret-pattern hits")
        for r in report["subsystems"]:
            hits = (r.get("secrets") or {}).get("hits") or []
            if not hits:
                continue
            lines.append(f"### {r['name']}")
            for h in hits:
                lines.append(f"- `{h['label']}` : `{h['hit']}`")
            lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--threads-per-worker", type=int, default=2)
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--no-zoekt", action="store_true", help="force rg/ctags path even if zoekt is available")
    ap.add_argument("--dashboard", action="store_true")
    ap.add_argument("--out-name", type=str, default="")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    subs = load_subsystems(only)
    if not subs:
        print("no subsystems found", file=sys.stderr)
        return 1

    use_zoekt = (not args.no_zoekt) and zoekt_available()
    if args.no_zoekt:
        print("[scan] --no-zoekt set, forcing rg/ctags path")
    elif not use_zoekt:
        print(f"[scan] zoekt not available (bin={ZOEKT_BIN.exists()}, index={ZOEKT_INDEX_DIR.is_dir()}); falling back to rg/ctags")
    else:
        print(f"[scan] using zoekt shard: {ZOEKT_INDEX_DIR}")

    print(f"[scan] repo_root = {REPO_ROOT}")
    print(f"[scan] subsystems = {len(subs)}")
    print(f"[scan] workers = {args.workers} x {args.threads_per_worker} threads")

    from dask.distributed import Client, LocalCluster
    from dask import delayed, compute

    cluster = LocalCluster(
        n_workers=args.workers, threads_per_worker=args.threads_per_worker,
        processes=True, dashboard_address=":8787",
    )
    client = Client(cluster)
    print(f"[scan] dask dashboard: {client.dashboard_link}")

    t0 = time.time()
    tasks = [delayed(scan_one)(s, not args.no_git, use_zoekt) for s in subs]
    results = list(compute(*tasks))
    wall = round(time.time() - t0, 2)

    total_loc = sum((r.get("tokei", {}).get("code_loc") or 0) for r in results)
    total_data_loc = sum((r.get("tokei", {}).get("data_loc") or 0) for r in results)
    total_files = sum((r.get("walk", {}).get("files") or 0) for r in results)
    total_todos = sum((r.get("todos", {}).get("total") or 0) for r in results)
    total_syms = sum((r.get("symbols", {}).get("symbols") or 0) for r in results)
    total_secs = sum((r.get("secrets", {}).get("count") or 0) for r in results)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = args.out_name or f"scan_atlas_dask_{stamp}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / f"{base}.json"
    out_md = OUT_DIR / f"{base}.md"

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "repo_root": str(REPO_ROOT), "subsystem_count": len(subs),
            "workers": args.workers, "threads_per_worker": args.threads_per_worker,
            "wall_s": wall, "zoekt_used": use_zoekt,
            "zoekt_index_dir": str(ZOEKT_INDEX_DIR) if use_zoekt else None,
            "total_code_loc": total_loc, "total_data_loc": total_data_loc,
            "total_files": total_files,
            "total_todos": total_todos, "total_symbols": total_syms,
            "total_secret_hits": total_secs, "git_churn_included": not args.no_git,
        },
        "subsystems": results,
    }

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    out_md.write_text(render_markdown(report), encoding="utf-8")

    print(f"[scan] wrote {out_json}")
    print(f"[scan] wrote {out_md}")
    print(f"[scan] done in {wall}s · {len(subs)} subs · {total_loc:,} LOC · {total_syms:,} syms · {total_secs} secret hits")

    if args.dashboard:
        input("dashboard still open at :8787 - press Enter to shut down: ")
    client.close()
    cluster.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

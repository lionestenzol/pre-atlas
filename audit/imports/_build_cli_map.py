#!/usr/bin/env python3
"""Build a complete CLI map for the repo — for agents, not humans.

Discovers every command-line entry point, statically extracts its real
surface (no confabulation — AST/parse only), merges in the hand-curated
cli_manifest.json where it exists, and emits:
  - audit/cli-map.json   (machine source of truth — what an agent reads)
  - audit/CLI_MAP.md      (rendered table + per-CLI command surfaces)

Extraction is static: Python via AST (argparse add_parser / add_argument,
typer/click @command), TS/PS1 by lightweight regex. A file that fails to
parse is reported with surface=[] rather than guessed.

Re-run after adding or changing a CLI. Deterministic.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "audit" / "cli-map.json"
OUT_MD = ROOT / "audit" / "CLI_MAP.md"
CURATED = ROOT / "services" / "cognitive-sensor" / "cli_manifest.json"

EXCLUDE_PARTS = {"node_modules", ".git", ".venv", "venv", "__pycache__",
                 "dist", "build", ".pytest_cache", "target", ".next",
                 "_archive", "tests", "research", "_research", "backups", "tmp",
                 "anatomy-research", "anatomy-rewrite", "experiments",
                 "scorecards", "logs", "public", "migrations", "fuzz",
                 ".claude", "worktrees", ".cache"}

# A file is a CLI only if it actually CONSTRUCTS a parser, not merely imports one.
CLI_MARKERS = re.compile(
    r"argparse\.ArgumentParser\s*\(|typer\.Typer\s*\(|"
    r"@\w+\.command\b|@command\b|click\.(group|command)\s*\(")


def excluded(p: Path) -> bool:
    return any(part in EXCLUDE_PARTS for part in p.parts)


# ---------- Python extraction (AST) ----------

def py_surface(src: str) -> tuple[str, list[dict], str]:
    """Return (docstring, commands, kind) for a python CLI source."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return ("", [], "unparseable")
    doc = (ast.get_docstring(tree) or "").strip().split("\n\n")[0].replace("\n", " ").strip()

    commands: list[dict] = []
    kind = "flags"

    # typer / click: @app.command(...) or @cli.command(...) decorators
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                name = _decorator_name(dec)
                if name and re.search(r"\.command$", name):
                    cdoc = (ast.get_docstring(node) or "").strip().split("\n")[0]
                    cmd_name = node.name.replace("_", "-")
                    commands.append({"name": cmd_name, "help": cdoc})
                    kind = "subcommands"

    # argparse: subparsers.add_parser('name', help='...')
    if not commands:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _attr_name(node.func) == "add_parser":
                if node.args and isinstance(node.args[0], ast.Constant):
                    cmd_name = str(node.args[0].value)
                    chelp = _kw(node, "help") or _kw(node, "description") or ""
                    commands.append({"name": cmd_name, "help": chelp})
                    kind = "subcommands"

    # argparse top-level flags (only if no subcommands found)
    if not commands:
        flags: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _attr_name(node.func) == "add_argument":
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        if a.value.startswith("-") or not a.value.startswith("_"):
                            flags.append(a.value)
                            break
        if flags:
            commands = [{"name": f, "help": ""} for f in flags]
            kind = "flags"

    return (doc, commands, kind)


def _decorator_name(dec: ast.expr) -> str | None:
    target = dec.func if isinstance(dec, ast.Call) else dec
    return _attr_chain(target)


def _attr_chain(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute):
        base = _attr_chain(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _attr_name(node: ast.expr) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) else (node.id if isinstance(node, ast.Name) else None)


def _kw(call: ast.Call, key: str) -> str:
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return ""


# ---------- TS extraction (regex, light) ----------

def ts_surface(src: str) -> tuple[str, list[dict]]:
    doc = ""
    m = re.search(r"/\*\*(.*?)\*/", src, re.DOTALL)
    if m:
        doc = re.sub(r"\s*\*\s*", " ", m.group(1)).strip()[:200]
    # case 'cmd':  switch-style command dispatch
    cmds = sorted(set(re.findall(r"case\s+['\"]([a-z][a-z0-9_-]*)['\"]\s*:", src)))
    return (doc, [{"name": c, "help": ""} for c in cmds])


# ---------- discovery ----------

def discover_python() -> list[Path]:
    found = []
    for p in ROOT.rglob("*.py"):
        if excluded(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "__main__" not in txt:
            continue
        if CLI_MARKERS.search(txt):
            found.append(p)
    return sorted(found)


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def runtime_for(p: Path) -> str:
    return {".py": "python", ".ts": "tsx", ".js": "node", ".ps1": "powershell"}.get(p.suffix, "?")


def categorize(rel_path: str, kind: str) -> str:
    if "/cli" in rel_path or rel_path.endswith("cli.py") or kind == "subcommands":
        return "command-cli"
    if rel_path.startswith(("audit/", "contracts/", "doctrine/", "scripts/")):
        return "infra-tool"
    return "one-shot-script"


def main() -> None:
    curated = {}
    if CURATED.exists():
        cm = json.loads(CURATED.read_text(encoding="utf-8"))
        for name, entry in cm.get("clis", {}).items():
            curated[entry.get("path", name)] = (name, entry)

    entries: list[dict] = []
    seen_paths: set[str] = set()

    # 1. python CLIs
    for p in discover_python():
        rp = rel(p)
        seen_paths.add(rp)
        doc, cmds, kind = py_surface(p.read_text(encoding="utf-8", errors="ignore"))
        # generic stems (cli/main/__main__) carry no meaning — name by package dir
        name = p.stem
        if name in {"cli", "main", "__main__", "server", "app", "__init__"}:
            parts = [x for x in p.parts if x not in {"src"}]
            name = parts[-2] if len(parts) >= 2 else p.parent.name
        cur = curated.get(rp)
        entry = {
            "name": cur[0] if cur else name,
            "path": rp,
            "runtime": "python",
            "category": categorize(rp, kind),
            "curated": bool(cur),
            "description": (cur[1]["description"] if cur else doc) or "(no module docstring)",
            "invoke": (cur[1]["help_invocation"] if cur else f"python {rp} --help"),
            "command_count": len(cur[1]["commands"]) if cur else len(cmds),
            "commands": (
                [{"name": k, "help": v.get("description", "")} for k, v in cur[1]["commands"].items()]
                if cur else cmds
            ),
        }
        entries.append(entry)

    # 2. curated TS CLIs (+ any curated path not yet seen)
    for rp, (name, cur) in curated.items():
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        entries.append({
            "name": name,
            "path": rp,
            "runtime": cur.get("runtime", "?"),
            "category": "command-cli",
            "curated": True,
            "description": cur["description"],
            "invoke": cur["help_invocation"],
            "command_count": len(cur["commands"]),
            "commands": [{"name": k, "help": v.get("description", "")} for k, v in cur["commands"].items()],
        })

    # 3. declared TS bin entries (delta-kernel package.json)
    pkg = ROOT / "services" / "delta-kernel" / "package.json"
    if pkg.exists():
        j = json.loads(pkg.read_text(encoding="utf-8"))
        for bin_name, bin_path in j.get("bin", {}).items():
            rp = f"services/delta-kernel/{bin_path.lstrip('./')}"
            if rp in seen_paths:
                continue
            seen_paths.add(rp)
            tp = ROOT / rp
            doc, cmds = ("", [])
            if tp.exists():
                doc, cmds = ts_surface(tp.read_text(encoding="utf-8", errors="ignore"))
            entries.append({
                "name": bin_name, "path": rp, "runtime": "tsx", "category": "command-cli",
                "curated": False, "description": doc or "(TS CLI bin entry)",
                "invoke": f"npx tsx {rp} help", "command_count": len(cmds), "commands": cmds,
            })

    entries.sort(key=lambda e: (e["category"], e["name"]))

    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "repo_root": str(ROOT),
        "note": "For agents. Static-extracted CLI surfaces; 'curated' entries enriched from cli_manifest.json.",
        "cli_count": len(entries),
        "by_category": _counts(entries),
        "clis": entries,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_md(result), encoding="utf-8")
    print(f"Wrote {rel(OUT_JSON)} and {rel(OUT_MD)}")
    print(f"  - {len(entries)} CLIs  ({result['by_category']})")


def _counts(entries: list[dict]) -> dict:
    out: dict[str, int] = {}
    for e in entries:
        out[e["category"]] = out.get(e["category"], 0) + 1
    return out


def render_md(r: dict) -> str:
    L = ["# Pre Atlas CLI Map", "",
         f"_Auto-generated {r['generated_at']} by `audit/imports/_build_cli_map.py`. "
         "For agents — what each CLI is and exactly how to invoke it._  ",
         f"_{r['cli_count']} CLIs · {r['by_category']}_", "",
         "Static-extracted. Entries marked ✓ are enriched from the hand-curated "
         "`services/cognitive-sensor/cli_manifest.json`; the rest are AST-extracted "
         "(command lists are real, descriptions come from module docstrings).", ""]

    by_cat: dict[str, list[dict]] = {}
    for e in r["clis"]:
        by_cat.setdefault(e["category"], []).append(e)

    cat_titles = {
        "command-cli": "Command CLIs (subcommand dispatch — the ones to actually drive)",
        "infra-tool": "Infra / generator tools",
        "one-shot-script": "One-shot pipeline / build scripts",
    }
    for cat in ("command-cli", "infra-tool"):
        if cat not in by_cat:
            continue
        L += [f"## {cat_titles.get(cat, cat)}", "",
              "| CLI | Invoke | Cmds | What it does |", "|---|---|---|---|"]
        for e in sorted(by_cat[cat], key=lambda x: x["name"]):
            mark = "✓ " if e["curated"] else ""
            desc = e["description"].replace("|", "\\|")[:140]
            L.append(f"| {mark}**`{e['name']}`** | `{e['invoke']}` | {e['command_count']} | {desc} |")
        L.append("")

    # one-shot scripts: collapse to a per-directory count (don't enumerate hundreds)
    one_shots = by_cat.get("one-shot-script", [])
    if one_shots:
        from collections import Counter
        dirs = Counter(str(Path(e["path"]).parent).replace("\\", "/") for e in one_shots)
        L += [f"## One-shot scripts ({len(one_shots)}) — flag-only, run individually",
              "", "_Not subcommand CLIs. Each takes flags; `<script> --help` for its surface. "
              "Listed in `cli-map.json` with extracted flags._", "",
              "| Directory | Count |", "|---|---|"]
        for d, n in dirs.most_common():
            L.append(f"| `{d}/` | {n} |")
        L.append("")

    # per-CLI command surfaces for command-clis only (keep the doc bounded)
    L += ["---", "", "## Command surfaces (command-CLIs)", ""]
    for e in sorted(by_cat.get("command-cli", []), key=lambda x: x["name"]):
        L += [f"### `{e['name']}` — {e['path']}",
              f"Invoke: `{e['invoke']}`  ", ""]
        if e["commands"]:
            for c in e["commands"][:40]:
                h = (" — " + c["help"]) if c.get("help") else ""
                L.append(f"- `{c['name']}`{h}")
        else:
            L.append("_(no subcommands extracted — flag-only or parse-failed)_")
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()

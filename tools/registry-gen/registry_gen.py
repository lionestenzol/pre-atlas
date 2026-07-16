"""
registry_gen.py — deterministic static analysis for vanilla-JS SPAs.

Reads a JS app directory and emits COMPONENT_REGISTRY.md.
Pure stdlib: re, ast (unused for JS — we stay in regex), pathlib, argparse.

Usage:
    python tools/registry-gen/registry_gen.py <app-dir>
    python tools/registry-gen/registry_gen.py apps/inpact --dry-run
"""

import re
import argparse
import sys
import io
from pathlib import Path

# Force UTF-8 stdout on Windows (avoids cp1252 encoding errors)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# DOM IDs — four forms:
#   getElementById("foo")
#   el.id = "foo"
#   id="foo"  or  id: "foo"   (template literals / object literals)
#   var/const NAME = 'dom-like-id'  (variable holding an ID, e.g. BANNER_ID)
_RE_GET_ELEMENT = re.compile(r"""getElementById\(\s*['"]([^'"]+)['"]\s*\)""")
_RE_ID_ASSIGN   = re.compile(r"""\.id\s*=\s*['"]([^'"]+)['"]""")
_RE_ID_ATTR     = re.compile(r"""(?:id\s*=\s*['"]|id:\s*['"])([A-Za-z][\w-]*)['"]""")
# Variable holding a DOM id: var/const/let NAME = 'some-id'
# We accept values that contain at least one hyphen (kebab-case DOM IDs) or
# start with a known prefix (ip-, wp-, az-, etc.)
_RE_ID_VAR      = re.compile(r"""(?:var|const|let)\s+\w+\s*=\s*['"]([a-z][\w]*(?:-[\w]+)+)['"]""")

# State key reads/writes — state.SomeKey or state.SomeKey.nested
# We capture the first capitalised segment as the top-level key.
_RE_STATE       = re.compile(r"""\bstate\.([A-Z]\w+(?:\.[A-Za-z_]\w*)*)""")
# Writes: stateManager.update({...}) or state.X = ...
_RE_STATE_WRITE = re.compile(r"""stateManager\.update\(|state\.[A-Z]\w+\s*=""")

# API routes inside _fetch() or fetch()
# Captures the first string argument: '/api/foo' or '/api/bar/' + id
_RE_FETCH_CALL  = re.compile(r"""_fetch\(\s*['"]([^'"]+)['"]|fetch\(\s*['"]([^'"]+)['"]""")
# Also catch string concatenation like _fetch('/api/tasks/' + ...)
_RE_FETCH_TMPL  = re.compile(r"""_fetch\(\s*['"]([/][^'"]+)['"]""")

# Event handlers — top-level function declarations
_RE_FUNC_DECL   = re.compile(r"""^(?:function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\()""", re.MULTILINE)
# onclick= in template literals
_RE_ONCLICK     = re.compile(r"""onclick\s*=\s*['"](\w+)\(""")

# Screen renderers
_RE_SCREEN_RENDERER = re.compile(r"""ScreenRenderers\.(\w+)\s*=|(\w+)\s*\(\s*\)\s*\{[^}]*ScreenRenderers|ScreenRenderers\s*=\s*\{""")
# Object key inside ScreenRenderers = { Key() { ... } }
_RE_SR_KEY      = re.compile(r"""^\s{2,4}(\w+)\s*\(""", re.MULTILINE)

# Cache variables: _someCache
_RE_CACHE       = re.compile(r"""(_{1,2}\w+Cache)\b""")
# TTL comment on same or adjacent line
_RE_TTL         = re.compile(r"""(\d+)\s*[*\s]?\s*(?:s\b|sec|seconds?|ms)""", re.IGNORECASE)

# HTTP method hints in fetch options
_RE_METHOD      = re.compile(r"""method\s*:\s*['"](\w+)['"]""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_js_files(app_dir: Path) -> list[tuple[Path, str]]:
    """Return list of (path, content) for all .js files under app_dir."""
    files = []
    for p in sorted(app_dir.rglob("*.js")):
        try:
            files.append((p, p.read_text(encoding="utf-8", errors="replace")))
        except Exception as e:
            print(f"  WARN: cannot read {p}: {e}", file=sys.stderr)
    return files


def _relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base.parent))
    except ValueError:
        return str(path)


def _find_line(content: str, match_start: int) -> int:
    return content[:match_start].count("\n") + 1


def _context_snippet(content: str, match_start: int, width: int = 60) -> str:
    line_start = content.rfind("\n", 0, match_start) + 1
    line_end   = content.find("\n", match_start)
    if line_end == -1:
        line_end = len(content)
    snippet = content[line_start:line_end].strip()
    if len(snippet) > width:
        snippet = snippet[:width] + "..."
    return snippet


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_dom_ids(files: list, base: Path) -> list[dict]:
    seen = {}  # id -> first occurrence
    rows = []
    for path, content in files:
        rel = _relative(path, base)
        # First pass: build variable→literal map for IDs stored in vars
        var_to_id: dict[str, str] = {}
        _RE_VAR_DECL = re.compile(r"""(?:var|const|let)\s+(\w+)\s*=\s*['"]([a-z][\w]*(?:-[\w]+)+)['"]""")
        for m in _RE_VAR_DECL.finditer(content):
            var_to_id[m.group(1)] = m.group(2)

        # Second pass: match all ID patterns
        for pat in (_RE_GET_ELEMENT, _RE_ID_ASSIGN, _RE_ID_ATTR, _RE_ID_VAR):
            for m in pat.finditer(content):
                dom_id = m.group(1)
                if not dom_id or len(dom_id) < 2:
                    continue
                if dom_id in seen:
                    continue
                seen[dom_id] = True
                line = _find_line(content, m.start())
                snippet = _context_snippet(content, m.start())
                rows.append({"id": dom_id, "file": rel, "line": line, "snippet": snippet})

        # Third pass: resolve variable-indirect assignments (.id = VARNAME)
        _RE_ID_VAR_ASSIGN = re.compile(r"""\.id\s*=\s*([A-Za-z_]\w+)\b""")
        for m in _RE_ID_VAR_ASSIGN.finditer(content):
            var_name = m.group(1)
            dom_id = var_to_id.get(var_name)
            if not dom_id or dom_id in seen:
                continue
            seen[dom_id] = True
            line = _find_line(content, m.start())
            snippet = _context_snippet(content, m.start())
            rows.append({"id": dom_id, "file": rel, "line": line, "snippet": snippet})

    rows.sort(key=lambda r: r["id"])
    return rows


def extract_state_keys(files: list, base: Path) -> list[dict]:
    keys: dict[str, dict] = {}
    for path, content in files:
        rel = _relative(path, base)
        # Determine if the file has any write patterns
        write_positions = set()
        for m in _RE_STATE_WRITE.finditer(content):
            # Mark lines that have writes
            write_positions.add(_find_line(content, m.start()))

        for m in _RE_STATE.finditer(content):
            key_path = m.group(1)
            top_key  = key_path.split(".")[0]
            line     = _find_line(content, m.start())
            mode     = "write" if line in write_positions else "read"
            entry_key = f"{key_path}|{rel}"
            if entry_key not in keys:
                keys[entry_key] = {"key": key_path, "file": rel, "line": line, "mode": mode}
            elif mode == "write":
                keys[entry_key]["mode"] = "write"

    rows = sorted(keys.values(), key=lambda r: (r["key"], r["file"]))
    # Deduplicate by (key, file) keeping one row per key+file
    seen = {}
    deduped = []
    for r in rows:
        k = (r["key"], r["file"])
        if k not in seen:
            seen[k] = True
            deduped.append(r)
    return deduped


def extract_api_routes(files: list, base: Path) -> list[dict]:
    seen = {}
    rows = []
    for path, content in files:
        rel = _relative(path, base)
        for m in _RE_FETCH_CALL.finditer(content):
            route = m.group(1) or m.group(2)
            if not route:
                continue
            # Guess HTTP method from nearby context (within 200 chars after)
            ctx_after = content[m.start():m.start()+200]
            method_m  = _RE_METHOD.search(ctx_after)
            method    = method_m.group(1).upper() if method_m else "GET"
            # Caller: look back for enclosing function name
            ctx_before = content[max(0, m.start()-300):m.start()]
            caller_m   = re.search(r"""(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{[^}]*$""", ctx_before)
            caller     = caller_m.group(1) if caller_m else "—"
            line       = _find_line(content, m.start())
            key = f"{method}|{route}"
            if key not in seen:
                seen[key] = True
                rows.append({"method": method, "route": route, "caller": caller,
                             "file": rel, "line": line})
    rows.sort(key=lambda r: r["route"])
    return rows


def extract_event_handlers(files: list, base: Path) -> list[dict]:
    seen = {}
    rows = []
    # Collect onclick= patterns for cross-referencing
    onclick_funcs: set[str] = set()
    for _, content in files:
        for m in _RE_ONCLICK.finditer(content):
            onclick_funcs.add(m.group(1))

    for path, content in files:
        rel = _relative(path, base)
        for m in _RE_FUNC_DECL.finditer(content):
            fname = m.group(1) or m.group(2)
            if not fname or fname in seen:
                continue
            # Only include handlers that appear as onclick targets or match common patterns
            trigger = "onclick" if fname in onclick_funcs else "direct call"
            line = _find_line(content, m.start())
            seen[fname] = True
            rows.append({"function": fname, "trigger": trigger, "file": rel, "line": line})
    rows.sort(key=lambda r: r["function"])
    return rows


def extract_screen_map(files: list, base: Path) -> list[dict]:
    rows = []
    seen = set()
    for path, content in files:
        rel = _relative(path, base)
        # Find the ScreenRenderers object block
        block_m = re.search(r"""const\s+ScreenRenderers\s*=\s*\{([\s\S]*?)\n\}""", content)
        if block_m:
            block = block_m.group(1)
            block_start = block_m.start()
            for km in _RE_SR_KEY.finditer(block):
                name = km.group(1)
                if name in seen:
                    continue
                seen.add(name)
                line = _find_line(content, block_start + km.start())
                rows.append({"screen": name, "renderer": f"ScreenRenderers.{name}()", "file": rel, "line": line})

        # Also pick up aliases at module level like  AtoZ() { return ScreenRenderers.Tasks(); }
        for am in re.finditer(r"""^\s{2,4}(\w+)\s*\(\)\s*\{\s*return\s+ScreenRenderers\.(\w+)\(\)""", content, re.MULTILINE):
            alias, target = am.group(1), am.group(2)
            if alias in seen:
                continue
            seen.add(alias)
            line = _find_line(content, am.start())
            rows.append({"screen": alias, "renderer": f"alias → ScreenRenderers.{target}()", "file": rel, "line": line})

    rows.sort(key=lambda r: r["screen"])
    return rows


def extract_caches(files: list, base: Path) -> list[dict]:
    seen = {}
    rows = []
    for path, content in files:
        rel = _relative(path, base)
        for m in _RE_CACHE.finditer(content):
            name = m.group(1)
            if name in seen:
                continue
            # Look for TTL comment or number near the declaration
            line_start = content.rfind("\n", 0, m.start()) + 1
            # Scan up to 3 lines around for TTL
            window_start = max(0, m.start() - 200)
            window_end   = min(len(content), m.start() + 200)
            window       = content[window_start:window_end]
            ttl_m        = _RE_TTL.search(window)
            ttl          = f"{ttl_m.group(1)} s" if ttl_m else "—"
            line         = _find_line(content, m.start())
            seen[name]   = True
            rows.append({"var": name, "ttl": ttl, "file": rel, "line": line})
    rows.sort(key=lambda r: r["var"])
    return rows


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render_registry(app_dir: Path, files: list, base: Path) -> str:
    rel_app = _relative(app_dir, base)

    dom_ids   = extract_dom_ids(files, base)
    state_keys= extract_state_keys(files, base)
    api_routes= extract_api_routes(files, base)
    handlers  = extract_event_handlers(files, base)
    screens   = extract_screen_map(files, base)
    caches    = extract_caches(files, base)

    file_list = "\n".join(
        f"  └─ {_relative(p, base)}" for p, _ in files
    )

    lines = []

    # Header
    lines += [
        f"# Component Registry — {app_dir.name}",
        "",
        f"> Machine-generated by `tools/registry-gen/registry_gen.py` from `{rel_app}/`",
        "> Do not hand-edit — re-run the script to regenerate.",
        "",
        "---",
        "",
        "## Architecture overview",
        "",
        "```",
        f"{rel_app}/",
        file_list,
        "```",
        "",
        "---",
        "",
    ]

    # DOM ID table
    lines += [
        "## DOM ID table",
        "",
        "| DOM ID | File | Line | Context |",
        "|--------|------|------|---------|",
    ]
    for r in dom_ids:
        lines.append(f"| `#{r['id']}` | `{r['file']}` | {r['line']} | `{r['snippet']}` |")
    lines += ["", "---", ""]

    # State key table
    lines += [
        "## State key table",
        "",
        "| Key path | File | Line | Mode |",
        "|----------|------|------|------|",
    ]
    for r in state_keys:
        lines.append(f"| `state.{r['key']}` | `{r['file']}` | {r['line']} | {r['mode']} |")
    lines += ["", "---", ""]

    # API route table
    lines += [
        "## API route table",
        "",
        "| Method | Route | Caller | File | Line |",
        "|--------|-------|--------|------|------|",
    ]
    for r in api_routes:
        lines.append(f"| `{r['method']}` | `{r['route']}` | `{r['caller']}` | `{r['file']}` | {r['line']} |")
    lines += ["", "---", ""]

    # Event handler index
    lines += [
        "## Event handler index",
        "",
        "| Function | Trigger | File | Line |",
        "|----------|---------|------|------|",
    ]
    for r in handlers:
        lines.append(f"| `{r['function']}` | {r['trigger']} | `{r['file']}` | {r['line']} |")
    lines += ["", "---", ""]

    # Screen map
    lines += [
        "## Screen map",
        "",
        "| Screen | Renderer | File | Line |",
        "|--------|----------|------|------|",
    ]
    for r in screens:
        lines.append(f"| `{r['screen']}` | `{r['renderer']}` | `{r['file']}` | {r['line']} |")
    lines += ["", "---", ""]

    # Cache map
    lines += [
        "## Cache map",
        "",
        "| Variable | TTL | File | Line |",
        "|----------|-----|------|------|",
    ]
    for r in caches:
        lines.append(f"| `{r['var']}` | {r['ttl']} | `{r['file']}` | {r['line']} |")
    lines += ["", "---", ""]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate COMPONENT_REGISTRY.md from a vanilla-JS SPA directory."
    )
    parser.add_argument("app_dir", help="Path to the app directory (e.g. apps/inpact)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print to stdout instead of writing the file")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).resolve()
    if not app_dir.is_dir():
        print(f"ERROR: not a directory: {app_dir}", file=sys.stderr)
        sys.exit(1)

    # base = parent of the repo root (used for relative path display)
    base = app_dir

    files = _load_js_files(app_dir)
    if not files:
        print(f"WARN: no .js files found under {app_dir}", file=sys.stderr)

    output = render_registry(app_dir, files, base)

    if args.dry_run:
        sys.stdout.write(output)
    else:
        out_path = app_dir / "COMPONENT_REGISTRY.md"
        out_path.write_text(output, encoding="utf-8")
        print(f"Written: {out_path}")
        print(f"  {len(files)} JS files scanned")


if __name__ == "__main__":
    main()

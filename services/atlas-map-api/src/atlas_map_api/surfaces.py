"""Enumerate every visual surface (HTML UI) in the repo, mapped to a served URL.

The monitor wall reads this so it shows ALL screens, not a hand-curated list.
Each real HTML file is matched to the http-server launch.json entry whose served
directory is the longest prefix of the file — so a file gets its most-specific
server (atlas-shell serving '.' only wins for top-level files no one else serves).
Generated/vendored trees are pruned.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_PRUNE = {
    "node_modules", ".venv", ".git", "dist", "anatomy-research", "backups",
    "site-packages", ".ruff_cache", ".pytest_cache", "_research", ".claude",
    "public", "tmp", ".next", "out", "fuzz-corpus", ".canvas-sessions",
    "_archive", "sandbox-template", ".weapon", ".claire", ".delta-fabric",
}


def _http_server_dir(cfg: dict[str, Any]) -> str | None:
    """Return the directory an http-server launch entry serves, or None."""
    args = [str(a) for a in (cfg.get("runtimeArgs") or [])]
    if not any("http-server" in a for a in args):
        return None
    for a in args:
        if "http-server" in a or a.startswith("-"):
            continue
        return a  # first non-flag arg = served dir (e.g. "services/foo" or ".")
    return None


def _iter_html(base: Path) -> list[Path]:
    out: list[Path] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _PRUNE]
        for f in files:
            if f.endswith(".html"):
                out.append(Path(root) / f)
    return out


def all_surfaces(repo_root: Path) -> dict[str, Any]:
    from . import launcher

    root = repo_root.resolve()
    servers: list[tuple[Path, int, str]] = []
    for cfg in launcher.load_launch_configs(repo_root):
        d = _http_server_dir(cfg)
        if d is None or not cfg.get("port"):
            continue
        sp = (root if d == "." else (root / d)).resolve()
        if sp.is_dir():
            servers.append((sp, int(cfg["port"]), str(cfg.get("name", ""))))

    out: list[dict[str, Any]] = []
    for html in _iter_html(root):
        hp = html.resolve()
        best: tuple[Path, int, str, Path] | None = None
        for sp, port, name in servers:
            try:
                rel = hp.relative_to(sp)
            except ValueError:
                continue
            if best is None or len(str(sp)) > len(str(best[0])):
                best = (sp, port, name, rel)
        if best is None:
            continue
        sp, port, name, rel = best
        repo_rel = hp.relative_to(root)
        out.append({
            "name": html.stem.replace("_", " ").replace("-", " "),
            "url": f"http://localhost:{port}/{rel.as_posix()}",
            "port": port,
            "launch": name,
            "group": repo_rel.parts[0] if len(repo_rel.parts) > 1 else "root",
            "file": repo_rel.as_posix(),
            "mtime": int(html.stat().st_mtime),
        })
    out.sort(key=lambda s: s["file"])
    return {"count": len(out), "surfaces": out}

"""atlas — CLI front-end over atlas-map-api (:3072).

Subcommands map 1:1 to /map/* endpoints. By default output is a rich table;
pass `--json` for machine output (pipe-friendly).

Examples:
  atlas where                        # which subsystem owns cwd?
  atlas locate path/to/file.py       # resolve any path to its subsystem
  atlas neighbors delta-kernel -n 2  # 2-hop neighborhood
  atlas path lattice delta-kernel    # shortest directed path
  atlas search "preview"             # fuzzy match
  atlas status                       # ports + autostart + retired
  atlas list --group services        # list filtered by group
  atlas show cognitive-sensor        # detail for one subsystem
  atlas reload                       # re-read snapshot files
  atlas open                         # open system-map.html in browser
  atlas open delta-kernel            # open viewer focused on a node
"""

from __future__ import annotations

import json as _json
import sys
import webbrowser
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .client import AtlasClient, find_repo_root, to_repo_relative

# On Windows, sys.stdout defaults to cp1252 which crashes on Unicode arrows /
# bullets / box-drawing chars. Reconfigure to UTF-8 with `replace` fallback so
# we never blow up on output. (Python 3.7+; no-op if reconfigure is unavailable.)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="atlas",
    help="GPS for Pre Atlas — query the system map from any cwd.",
    no_args_is_help=True,
    add_completion=False,
)

# legacy_windows=False forces Rich to use ANSI escape sequences instead of the
# Win32 console API, which routes through cp1252 and chokes on chars like → ● ▸.
# Modern Windows 10+ terminals (incl. Windows Terminal, conhost in Win11) handle
# ANSI natively; falls back gracefully on older shells too.
console = Console(legacy_windows=False)
err_console = Console(stderr=True, style="red", legacy_windows=False)

# Module-level flags filled by the top-level callback so every subcommand
# can read them without threading ctx through manually.
_OPTS: dict = {"json": False, "api": None}


# ---------- helpers ----------
def _print(obj: dict | list) -> None:
    """Always-JSON output for `--json`."""
    console.print_json(data=obj)


def _bail(msg: str, code: int = 1) -> None:
    err_console.print(msg)
    raise typer.Exit(code)


@contextmanager
def _client() -> Iterator[AtlasClient]:
    """Yield a connected API client; convert connect/HTTP errors into clean exits.

    Using a context manager (rather than a decorator on each typer command) keeps
    typer's signature introspection intact — decorators that use *args/**kwargs
    break --help and option parsing.
    """
    try:
        with AtlasClient(base=_OPTS.get("api")) as c:
            yield c
    except httpx.ConnectError:
        _bail(
            f"Cannot reach atlas-map-api at {_OPTS.get('api') or 'http://127.0.0.1:3072'}.\n"
            "Start it: preview_start atlas-map-api  (or run `atlas-map-api` in services/atlas-map-api)"
        )
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = e.response.text
        _bail(f"API error {e.response.status_code}: {detail}")


# ---------- top-level callback ----------
@app.callback()
def main(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty output."),
    api: Optional[str] = typer.Option(None, "--api", help="Override API base URL (default $ATLAS_API_URL or http://127.0.0.1:3072)."),
) -> None:
    _OPTS["json"] = json_out
    _OPTS["api"] = api


# ---------- where: identify cwd's subsystem ----------
@app.command()
def where() -> None:
    """Which subsystem owns the current working directory?"""
    repo = find_repo_root()
    if repo is None:
        _bail("Not inside a Pre Atlas checkout (no audit/system-index.json found upward).")
    cwd = Path.cwd().resolve()
    try:
        rel = str(cwd.relative_to(repo)).replace("\\", "/")
    except ValueError:
        _bail(f"cwd ({cwd}) is not inside repo root ({repo}).")
    # API does prefix match `<file>.startswith(<subsystem_path> + "/")` — so we
    # append "/." to make a bare directory match (esp. when cwd IS a service root).
    probe = (rel.rstrip("/") + "/.") if rel and rel != "." else "."
    with _client() as c:
        result = c.locate(probe)
    if _OPTS["json"]:
        _print({"cwd": str(cwd), "repo_root": str(repo), "rel": rel, **result})
        return
    if result["system"]:
        console.print(f"[bold green]{result['system']}[/]  ({rel})")
    else:
        console.print(f"[dim]no subsystem owns[/] {rel}")


# ---------- locate: any path → subsystem ----------
@app.command()
def locate(
    file: str = typer.Argument(..., help="Absolute path, cwd-relative path, or repo-relative path."),
) -> None:
    """Which subsystem owns the given file?"""
    repo = find_repo_root()
    rel = to_repo_relative(file, repo)
    with _client() as c:
        result = c.locate(rel)
    if _OPTS["json"]:
        _print(result)
        return
    if result["system"]:
        console.print(f"[bold green]{result['system']}[/]  <- {result['file']}")
    else:
        console.print(f"[yellow]no subsystem owns[/] {result['file']}")


# ---------- neighbors: N-hop ----------
@app.command()
def neighbors(
    name: str = typer.Argument(..., help="Subsystem name."),
    hops: int = typer.Option(1, "--hops", "-n", min=1, max=5),
) -> None:
    """List N-hop dependency neighbors."""
    with _client() as c:
        result = c.neighbors(name, hops=hops)
    if _OPTS["json"]:
        _print(result)
        return
    console.print(f"[bold]{name}[/]  ({hops}-hop neighborhood)\n")
    if result["out"]:
        console.print(f"[cyan]→ depends on:[/]      {', '.join(result['out'])}")
    if result["in"]:
        console.print(f"[magenta]← depended on by:[/]  {', '.join(result['in'])}")
    by_dist = result.get("by_distance") or {}
    if hops > 1:
        for d in sorted(by_dist.keys(), key=int):
            if d == "0":
                continue
            console.print(f"[dim]distance {d}:[/] {', '.join(by_dist[d])}")


# ---------- path: BFS both ways ----------
@app.command()
def path(
    src: str = typer.Argument(..., metavar="FROM"),
    dst: str = typer.Argument(..., metavar="TO"),
) -> None:
    """Shortest directed dependency path between two subsystems (both ways)."""
    with _client() as c:
        result = c.path(src, dst)
    if _OPTS["json"]:
        _print(result)
        return
    f = result["forward"]
    r = result["reverse"]
    if f:
        console.print(f"[green]→ {' → '.join(f)}[/]")
    else:
        console.print(f"[dim]no forward path[/] {src} → {dst}")
    if r:
        console.print(f"[blue]← {' ← '.join(r)}[/]")
    else:
        console.print(f"[dim]no reverse path[/] {dst} → {src}")


# ---------- search: fuzzy ----------
@app.command()
def search(
    query: str = typer.Argument(..., metavar="QUERY"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=50),
) -> None:
    """Fuzzy match across name + purpose + language + framework."""
    with _client() as c:
        result = c.search(query, limit=limit)
    if _OPTS["json"]:
        _print(result)
        return
    items = result["items"]
    if not items:
        console.print(f"[dim]no matches for[/] {query}")
        return
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("score", justify="right", style="dim")
    t.add_column("name", style="bold")
    t.add_column("group", style="green")
    t.add_column("port", justify="right", style="yellow")
    t.add_column("purpose")
    for it in items:
        t.add_row(
            str(it["score"]),
            it["name"],
            it.get("group") or "",
            str(it.get("port") or ""),
            (it.get("purpose") or "")[:60],
        )
    console.print(t)


# ---------- status: signals snapshot ----------
@app.command()
def status() -> None:
    """Live signals: autostart + ported + retired."""
    with _client() as c:
        result = c.signals()
    if _OPTS["json"]:
        _print(result)
        return
    console.print(f"[bold]{result['subsystem_count']}[/] subsystems · "
                  f"loaded_at={int(result.get('loaded_at') or 0)}\n")
    t = Table(title="ported (live)", show_header=True, header_style="bold cyan")
    t.add_column("port", justify="right", style="yellow")
    t.add_column("name", style="bold")
    for p in result.get("ported", []):
        t.add_row(str(p["port"]), p["name"])
    console.print(t)
    console.print(f"\n[green]autostart:[/] {', '.join(result.get('autostart', []))}")
    if result.get("retired"):
        console.print(f"[dim red]retired:[/]   {', '.join(result['retired'])}")


# ---------- list: filtered systems ----------
@app.command(name="list")
def list_systems(
    group: Optional[str] = typer.Option(None, "--group", "-g", help="services|apps|tools"),
    running: Optional[bool] = typer.Option(None, "--running/--not-running", help="Filter by autostart membership."),
) -> None:
    """List subsystems (filter by group or autostart membership)."""
    with _client() as c:
        result = c.systems(group=group, running=running)
    if _OPTS["json"]:
        _print(result)
        return
    t = Table(show_header=True, header_style="bold cyan")
    t.add_column("name", style="bold")
    t.add_column("group", style="green")
    t.add_column("lang", style="magenta")
    t.add_column("port", justify="right", style="yellow")
    t.add_column("loc", justify="right", style="dim")
    t.add_column("autostart", justify="center")
    for s in result["items"]:
        t.add_row(
            s["name"],
            s.get("group") or "",
            s.get("language") or "",
            str(s.get("port") or ""),
            str(s.get("loc") or ""),
            "●" if s.get("in_autostart") else "",
        )
    console.print(t)
    console.print(f"\n[dim]{result['count']} subsystems[/]")


# ---------- show: detail for one ----------
@app.command()
def show(name: str = typer.Argument(...)) -> None:
    """Detail for one subsystem (+ depends_on / depended_on_by)."""
    with _client() as c:
        result = c.system(name)
    if _OPTS["json"]:
        _print(result)
        return
    console.print(f"[bold green]{result['name']}[/]  ({result.get('group')})")
    for k in ("purpose", "path", "language", "framework", "port", "loc", "file_count", "in_autostart"):
        v = result.get(k)
        if v not in (None, "", 0, False):
            console.print(f"  [dim]{k}:[/] {v}")
    if result.get("depends_on"):
        console.print(f"\n[cyan]→ depends on:[/]      {', '.join(result['depends_on'])}")
    if result.get("depended_on_by"):
        console.print(f"[magenta]← depended on by:[/]  {', '.join(result['depended_on_by'])}")
    if result.get("retired"):
        console.print("[red]retired[/]")


# ---------- reload: re-read snapshot ----------
@app.command()
def reload() -> None:
    """Re-read system-index.json + atlas-map.json from disk."""
    with _client() as c:
        result = c.reload()
    if _OPTS["json"]:
        _print(result)
        return
    console.print(f"[green]reloaded[/]  {result['subsystem_count']} subsystems")


# ---------- open: launch viewer ----------
@app.command()
def open(
    name: Optional[str] = typer.Argument(None, help="Optional subsystem to focus."),
    port: int = typer.Option(8897, "--port", "-p", help="Port serving audit/system-map.html"),
) -> None:
    """Open system-map.html in your default browser (optionally focused on a node)."""
    url = f"http://127.0.0.1:{port}/system-map.html"
    if name:
        url += f"#focus={name}"
    if _OPTS["json"]:
        _print({"url": url, "opened": True})
    else:
        console.print(f"[green]opening[/] {url}")
    webbrowser.open(url)


if __name__ == "__main__":  # pragma: no cover
    app()

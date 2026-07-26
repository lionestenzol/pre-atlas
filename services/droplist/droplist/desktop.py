"""DropList as a standalone desktop window (Task E — completes Bar 3).

`python -m droplist.desktop` (or the packaged DropList.exe) starts the FastAPI
server on a daemon thread bound to a DYNAMIC free port — so two instances never
collide — waits for it to answer, then opens a native window (EdgeWebView2 on
Windows) pointed at it. The exact same process is therefore BOTH a desktop app
and a localhost web app, reusing 100% of server.py + both HTMLs.

Assemble-first: pywebview (native webview, no bundled Chromium) + PyInstaller for
the binary — not a hand-rolled Electron-style shell. See assemble-first.md.

Package to a single file (run from services/droplist):
    pyinstaller --onefile --windowed --name DropList \
        --add-data "ui;ui" --icon ui/icons/icon-512.png \
        -p . droplist/desktop.py
"""
from __future__ import annotations

import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path


def _stable_data_dir() -> Path:
    """Per-user data location. Same path across every launch, so a double-click of the
    exe from any folder — Desktop shortcut, dist/, wherever — always sees the same DAGs,
    packets, keys, and llm_calls log. Windows: %LOCALAPPDATA%\\DropList\\data.
    POSIX: $XDG_DATA_HOME/DropList/data (default ~/.local/share/DropList/data)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "DropList" / "data"


def _seed_from(src: Path, dst: Path) -> None:
    """One-time migration: if the stable data dir is empty but a source dir has state,
    copy it over. Idempotent — never overwrites an already-populated stable dir."""
    if not src.is_dir():
        return
    if dst.exists() and any(dst.iterdir()):
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        try:
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                shutil.copy2(child, target)
        except OSError:
            pass  # best-effort; the server will still boot on a partial copy


def _prepare_data_dir() -> Path:
    """Resolve, create, and seed the data dir; export DROPLIST_DATA so storage.py sees it.
    Must run BEFORE ``from droplist import server`` — storage.DATA_DIR reads the env at import."""
    if os.environ.get("DROPLIST_DATA"):
        return Path(os.environ["DROPLIST_DATA"])
    dst = _stable_data_dir()
    dst.mkdir(parents=True, exist_ok=True)
    # Candidate source dirs for the one-time seed: the packaged exe next to a legacy
    # data/ folder, or a source checkout at ../services/droplist/data.
    for candidate in (
        Path(getattr(sys, "_MEIPASS", "")) / "data" if getattr(sys, "frozen", False) else None,
        Path(os.getcwd()) / "data",
        Path(__file__).resolve().parent.parent / "data",
    ):
        if candidate and candidate.is_dir():
            _seed_from(candidate, dst)
            break
    os.environ["DROPLIST_DATA"] = str(dst)
    return dst


def _free_port() -> int:
    """Ask the OS for an unused port (bind :0, read it back, release)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """Poll the health of the local server until it answers or we time out."""
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/now"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status < 500:
                    return True
        except Exception:  # noqa: BLE001 — not up yet, keep polling
            time.sleep(0.15)
    return False


def main() -> None:
    import webview  # imported here so CLI users without the [desktop] extra still import the module

    # Resolve + seed the per-user data dir BEFORE importing server (which imports
    # storage, which snapshots DROPLIST_DATA into a module constant at import time).
    _prepare_data_dir()

    # Absolute, NOT `from . import server`: as a PyInstaller --onefile entry script
    # this module runs as __main__ with no package parent, so a relative import
    # raises "attempted relative import with no known parent package". Absolute
    # resolves both as the bundled exe and as `python -m droplist.desktop`.
    # See ~/.claude/rules/common/code-as-furniture.md — bug found in the first
    # exe build, fixed inline rather than documented.
    from droplist import server

    port = _free_port()
    t = threading.Thread(target=server.run, kwargs={"port": port}, daemon=True)
    t.start()
    if not _wait_for_server(port):
        raise SystemExit(f"DropList server did not come up on port {port}")
    webview.create_window("DropList", f"http://127.0.0.1:{port}/", width=1100, height=820)
    webview.start()


if __name__ == "__main__":
    main()

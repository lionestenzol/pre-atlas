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

import socket
import threading
import time
import urllib.request


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

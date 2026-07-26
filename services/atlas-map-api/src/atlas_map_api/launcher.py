"""Action layer for the system map: start / stop / restart services.

SECURITY MODEL — read before changing anything here.

This is the only write-capable surface in atlas-map-api. It can spawn and kill
OS processes, so it is deliberately constrained:

1. ALLOWLIST ONLY. The set of things that can be started is fixed by
   `.claude/launch.json`. A start request names a *subsystem*; we resolve it to
   its port (from the snapshot), then to the launch.json config with that port,
   and spawn EXACTLY that config's `runtimeExecutable` + `runtimeArgs`. Nothing
   from the HTTP request is ever interpolated into the command.
2. NO SHELL. Processes are spawned with an argv list and `shell=False`, so there
   is no shell-injection surface even if launch.json were tampered with.
3. SELF-PROTECTION. We refuse to stop our own port (SELF_PORT).
4. IDEMPOTENT START. If the port is already answering, we do not double-spawn.

The server binds 127.0.0.1 only; this layer assumes loopback trust.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

LAUNCH_REL = Path(".claude") / "launch.json"
SELF_PORT = 3072  # atlas-map-api's own port — never stop it


def load_launch_configs(repo_root: Path) -> list[dict[str, Any]]:
    """Read the launch.json allowlist. Returns [] on any problem (fail-closed)."""
    path = repo_root / LAUNCH_REL
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    cfgs = data.get("configurations") or data.get("servers") or []
    return [c for c in cfgs if isinstance(c, dict) and c.get("name")]


def config_for_port(repo_root: Path, port: int | None) -> dict[str, Any] | None:
    """Find the launch.json config that owns this port."""
    if not port:
        return None
    for cfg in load_launch_configs(repo_root):
        if cfg.get("port") == port:
            return cfg
    return None


def port_alive(port: int | None, timeout: float = 0.25) -> bool:
    if not port:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def _resolve_exe(exe: str) -> str | None:
    """Resolve an executable name to a runnable path (Windows .cmd-aware)."""
    found = shutil.which(exe)
    if found:
        return found
    # Windows: npx/npm/etc. live as .cmd shims that `which` may miss by bare name
    if sys.platform == "win32":
        for ext in (".cmd", ".exe", ".bat"):
            found = shutil.which(exe + ext)
            if found:
                return found
    p = Path(exe)
    return str(p) if p.is_file() else None


def start_from_config(cfg: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Spawn the process defined by a launch.json config, detached. Idempotent."""
    name = cfg.get("name", "?")
    port = cfg.get("port")
    if port_alive(port):
        return {"ok": True, "started": False, "name": name, "port": port, "reason": "already running"}

    exe = cfg.get("runtimeExecutable")
    if not exe:
        return {"ok": False, "started": False, "name": name, "error": "config has no runtimeExecutable"}
    resolved = _resolve_exe(str(exe))
    if not resolved:
        return {"ok": False, "started": False, "name": name, "error": f"executable not found: {exe}"}

    cmd = [resolved, *[str(a) for a in (cfg.get("runtimeArgs") or [])]]
    cwd = (repo_root / str(cfg.get("cwd") or ".")).resolve()
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in (cfg.get("env") or {}).items()})

    log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = str(name).replace("/", "_").replace("\\", "_").replace("..", "_")
    log_path = log_dir / f"map-start-{safe_name}.log"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with open(log_path, "ab") as logf:
        subprocess.Popen(  # noqa: S603 — argv list, shell=False, allowlisted cmd
            cmd,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=logf,
            stderr=logf,
            close_fds=True,
            shell=False,
            creationflags=creationflags,
            start_new_session=(sys.platform != "win32"),
        )
    return {"ok": True, "started": True, "name": name, "port": port, "cmd": cmd, "cwd": str(cwd), "log": str(log_path)}


def pids_on_port(port: int) -> list[int]:
    """PIDs listening on 127.0.0.1:port (best-effort; needs psutil)."""
    try:
        import psutil
    except ImportError:
        return []
    pids: set[int] = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN and conn.pid:
                pids.add(conn.pid)
    except (psutil.AccessDenied, OSError):
        return []
    return sorted(pids)


def stop_on_port(port: int | None) -> dict[str, Any]:
    """Terminate the process(es) listening on a port. Refuses SELF_PORT."""
    if not port:
        return {"ok": False, "stopped": False, "error": "no port for this service"}
    if int(port) == SELF_PORT:
        return {"ok": False, "stopped": False, "error": "refusing to stop atlas-map-api itself"}
    if not port_alive(port):
        return {"ok": True, "stopped": False, "port": port, "reason": "not running"}
    try:
        import psutil
    except ImportError:
        return {"ok": False, "stopped": False, "port": port, "error": "psutil not installed"}
    killed: list[int] = []
    for pid in pids_on_port(port):
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            killed.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"ok": bool(killed), "stopped": bool(killed), "port": port, "pids": killed,
            **({} if killed else {"error": "no killable PID found on port"})}

"""Unified status collectors (Wave 1.3, atlas-consolidation-AC0002).

One surface that answers "what is running right now": services up/down,
Atlas Scheduled Tasks + triggers, governance daemon heartbeat, orphan
listeners. Every collector is fail-soft: it returns an {"error": ...}
payload rather than raising, so one dead subsystem never blanks the view.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

from . import launcher

DELTA_KERNEL = "http://127.0.0.1:3001"
_PS_TASK_FILTER = (
    "$_.TaskName -match '^(Atlas|PreAtlas)' -or $_.TaskName -eq 'Optogon Audit'"
)


def collect_services(snap) -> list[dict[str, Any]]:
    """Every ported subsystem: live TCP probe + owning PIDs."""
    out: list[dict[str, Any]] = []
    for s in snap.subsystems.values():
        if not s.port:
            continue
        up = launcher.port_alive(s.port)
        out.append({
            "name": s.name,
            "port": s.port,
            "up": up,
            "pids": launcher.pids_on_port(s.port) if up else [],
        })
    out.sort(key=lambda x: x["port"])
    return out


def collect_scheduled_tasks() -> dict[str, Any]:
    """The Atlas Windows Scheduled Tasks + their triggers, via PowerShell."""
    ps = (
        "Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { "
        + _PS_TASK_FILTER
        + " } | ForEach-Object { [pscustomobject]@{ name = $_.TaskName; "
        "state = \"$($_.State)\"; triggers = @($_.Triggers | ForEach-Object { "
        "$k = $_.CimClass.CimClassName -replace '^MSFT_Task','' -replace 'Trigger$',''; "
        "if ($_.StartBoundary) { \"$k@$($_.StartBoundary)\" } else { $k } }) } } "
        # -AsArray needs PowerShell 6+; this runs under Windows PowerShell 5.1
        # (invoked as `powershell`, not `pwsh`), where it errors out. Omit it —
        # the single-item-result case is already normalized below (dict -> [dict]).
        # Path hardened: see ~/.claude/rules/common/code-as-furniture.md.
        "| ConvertTo-Json -Depth 4"
    )
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, shell=False
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20, shell=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"scheduled-task probe failed: {e}", "tasks": []}
    if proc.returncode != 0:
        return {"error": f"powershell exit {proc.returncode}: {proc.stderr[-500:]}", "tasks": []}
    try:
        tasks = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return {"error": "unparseable Get-ScheduledTask output", "tasks": []}
    if isinstance(tasks, dict):  # single-item ConvertTo-Json fallback
        tasks = [tasks]
    return {"error": None, "tasks": tasks}


async def collect_daemon() -> dict[str, Any]:
    """Governance daemon heartbeat from delta-kernel :3001 (Bearer via open token route)."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            tok_res = await client.get(f"{DELTA_KERNEL}/api/auth/token")
            token = (tok_res.json() or {}).get("token")
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            res = await client.get(f"{DELTA_KERNEL}/api/daemon/status", headers=headers)
            body = res.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"reachable": False, "error": f"delta-kernel :3001 unreachable: {e}"}
    return {
        "reachable": True,
        "running": body.get("running"),
        "last_heartbeat": body.get("last_heartbeat"),  # epoch ms (delta.ts now())
        "current_job": body.get("current_job"),
    }


def collect_orphans(repo_root: Path) -> dict[str, Any]:
    """Report-only orphan scan: scripts/reap_orphans.ps1 -DryRun (Wave 0.3 logic)."""
    script = repo_root / "scripts" / "reap_orphans.ps1"
    if not script.is_file():
        return {"error": f"missing {script}", "count": None, "candidates": []}
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, shell=False
            ["powershell", "-NoProfile", "-NonInteractive", "-File", str(script), "-DryRun"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": f"orphan scan failed: {e}", "count": None, "candidates": []}
    out = proc.stdout or ""
    if "No orphans found" in out:
        return {"error": None, "count": 0, "candidates": []}
    m = re.search(r"Orphan candidates \((\d+)\):", out)
    candidates = re.findall(r"PID\s+(\d+)\s+(\S+)\s+(.+)", out)
    return {
        "error": None if m else f"unexpected reap_orphans output (exit {proc.returncode})",
        "count": int(m.group(1)) if m else None,
        "candidates": [
            {"pid": int(p), "port": port, "reason": reason.strip()}
            for p, port, reason in candidates
        ],
    }


async def unified_status(snap) -> dict[str, Any]:
    """The single view: services + scheduled tasks + daemon heartbeat + orphans."""
    services = collect_services(snap)
    daemon_task = asyncio.create_task(collect_daemon())
    sched = await asyncio.to_thread(collect_scheduled_tasks)
    orphans = await asyncio.to_thread(collect_orphans, snap.repo_root)
    daemon = await daemon_task
    return {
        "services": services,
        "services_up": sum(1 for s in services if s["up"]),
        "scheduled_tasks": sched,
        "daemon": daemon,
        "orphans": orphans,
    }

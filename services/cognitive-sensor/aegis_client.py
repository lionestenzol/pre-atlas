"""
Aegis observe-mode client for Pre Atlas autonomous scripts.

Fire-and-forget logging to http://localhost:3002/api/v1/agent/action.
Never blocks the caller — on any failure (Aegis down, network, bad config),
returns None and the script continues.

Usage:
    from aegis_client import log_action
    log_action("auto_actor", "route_decision", {"phase": "loops_analyzed", "count": 12})
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_KEY_PATH = _REPO_ROOT / ".aegis-tenant-key"
_AGENTS_PATH = _REPO_ROOT / ".aegis-agents.json"
_AEGIS_URL = "http://localhost:3002/api/v1/agent/action"
_TIMEOUT_SEC = 1.5

_tenant_key: str | None = None
_agents: dict[str, str] | None = None


def _load_config() -> tuple[str | None, dict[str, str]]:
    global _tenant_key, _agents
    if _tenant_key is None and _KEY_PATH.exists():
        _tenant_key = _KEY_PATH.read_text(encoding="utf-8").strip()
    if _agents is None and _AGENTS_PATH.exists():
        raw = json.loads(_AGENTS_PATH.read_text(encoding="utf-8"))
        _agents = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _tenant_key, _agents or {}


def log_action(agent_name: str, action: str, params: dict[str, Any]) -> str | None:
    """Fire-and-forget log to Aegis. Returns action_id on success, None on any failure."""
    key, agents = _load_config()
    if not key or agent_name not in agents:
        return None

    body = json.dumps({
        "agent_id": agents[agent_name],
        "action": action,
        "params": params,
    }).encode("utf-8")

    req = urllib.request.Request(
        _AEGIS_URL,
        data=body,
        headers={"Content-Type": "application/json", "X-API-Key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("action_id")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return None

"""Delta-kernel work-queue client for lattice runs (Seq 7 -- Supervisor).

LangGraph itself has no auto-resume (Honest Cost #2 in
docs/LANGGRAPH_SKILL_LATTICE_PLAN.md): something external must call
`graph.ainvoke(None, config)` after a crash. delta-kernel's work queue is that
external supervisor -- it already does claim/heartbeat/timeout/retry
(services/delta-kernel/src/core/work-controller.ts). This module is the thin
REST client that lets a lattice run register itself as a `system`-type job
before it starts, so a killed run shows up as a timed-out `active` job that
`WorkController.checkTimeouts()` retries in place. The daemon side
(governance_daemon.ts's `runWorkQueue` -> `resumeLatticeJob`) re-invokes
`run_chain.py --resume` for any retried job tagged
`metadata.kind == "lattice_resume"`, closing the loop without a human
touching it.

Not a new capability or ActionType (TRUST_BOUNDARY.md) -- `type: "system"` and
`/api/work/*` already exist; this only registers ordinary jobs against them.

Fail-soft throughout, matching the rest of the stack's graceful-degradation
convention (aegis in server.ts, ledger_feed.py's SEAM_LEDGER gate): a lattice
run must still complete correctly even if delta-kernel is offline.
Supervision is additive, not load-bearing for the graph's own crash-resume
mechanism (that's Seq 3, proven independently in test_lattice_graph.py).

Uses stdlib `urllib` deliberately -- two fire-and-forget JSON POSTs don't
justify pulling in an HTTP client library (assemble-first's "worse, or just
later" test: a full client here would be later-but-not-better).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:3001"
_TIMEOUT_S = 5.0


def _fetch_token(base_url: str) -> str | None:
    """GET /api/auth/token is deliberately the one open route (CLAUDE.md): every
    other /api/* route requires `Authorization: Bearer <token>` once
    `.aegis-tenant-key` exists on disk. In dev mode with no key file, the route
    itself returns {"token": null} and every route skips auth -- either way this
    always returns the right thing to send (a real token, or None to send none)."""
    req = urllib.request.Request(base_url.rstrip("/") + "/api/auth/token", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310 -- local trusted service
            return json.loads(resp.read().decode("utf-8")).get("token")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def _post(base_url: str, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
    token = _fetch_token(base_url)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310 -- local trusted service
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def register_job(
    base_url: str,
    *,
    thread_id: str,
    pairs: list[tuple[str, str]] | None,
    db: str,
    max_turns: int,
    max_budget_usd: float,
    timeout_ms: int,
    demo: bool = False,
) -> str | None:
    """Register this run as a delta-kernel work-queue job.

    Returns the job_id, or None if delta-kernel is unreachable or the job
    wasn't APPROVED -- the caller should proceed with the run regardless
    (fail-soft; supervision is additive, not required for the graph to run).
    """
    result = _post(base_url, "/api/work/request", {
        "type": "system",
        "title": f"lattice-resume:{thread_id}",
        "timeout_ms": timeout_ms,
        "metadata": {
            "kind": "lattice_resume",
            "thread_id": thread_id,
            "pairs": [list(p) for p in pairs] if pairs else [],
            "db": db,
            "max_turns": max_turns,
            "max_budget_usd": max_budget_usd,
            "demo": demo,
        },
    })
    if not result or result.get("status") != "APPROVED":
        return None
    return result.get("job_id")


def complete_job(base_url: str, job_id: str, *, outcome: str, error: str | None = None) -> bool:
    """Report completion so the job leaves delta-kernel's active list. Fail-soft."""
    body: dict[str, Any] = {"job_id": job_id, "outcome": outcome}
    if error:
        body["error"] = error
    result = _post(base_url, "/api/work/complete", body)
    return bool(result and result.get("success"))

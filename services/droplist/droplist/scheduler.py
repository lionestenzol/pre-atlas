"""Scheduler core — in-repo due-evaluation for DropList (Brick 3, testable half).

The OS Task Scheduler `.ps1` scripts decide WHEN the host process wakes; this
module decides WHICH jobs are due at a given instant. It is pure temporal
selection: given a registry of cron-scheduled jobs, a `now`, and a per-job
``last_run`` map, return the ids that should fire. Brick 4's chain triggers
call ``due_jobs`` to know what to dispatch.

DETERMINISM RULE (mirrors clock.py:14 / DROPLIST_NOW): ``now`` is ALWAYS passed
in as a datetime. Nothing here reads the wall clock — that is what makes the
selection provable in test_scheduler.py without waiting for real time. The host
runner (daemon / .ps1) reads ``clock.now()`` once and hands it down.

LIBRARY DECISION (~/.claude/rules/common/assemble-first.md): cron-expression
math is delegated to **croniter** (PyPI, already installed under
site-packages/croniter). Cron parsing is a solved category — a hand-rolled
parser would be strictly worse (DST/edge-field bugs, no maintenance), not just
later. daemon.py:24-31 already named croniter as the intended candidate "when
richer recurrence lands"; this is that landing. It is now a hard dependency of
this module and is declared in pyproject.toml.

Action kinds are a CLOSED enum (~/.claude/rules/common/coding-style.md): a
schedule's action ``kind`` is one of {tick, run_chain, drop}. The scheduler
itself does not execute actions — it only selects due jobs; the host runner
dispatches by kind (tick -> daemon._run_once, run_chain -> graph advance,
drop -> intake.chain_intake). Selection and dispatch are kept apart so this
half stays clock-free and unit-testable.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import Any

from croniter import croniter

#: Closed set of action kinds a schedule may declare. The host runner maps each
#: to an existing entrypoint; the scheduler only validates membership.
ACTION_KINDS: frozenset[str] = frozenset({"tick", "run_chain", "drop"})

#: Default registry location, resolved under the same data dir as everything
#: else (storage.py:14) so a deployment's schedules live with its state.
DEFAULT_SCHEDULES_PATH = os.path.join(
    os.environ.get("DROPLIST_DATA", "data"), "schedules.json"
)


def is_valid_cron(expr: str) -> bool:
    """True iff ``expr`` is a croniter-parseable cron expression."""
    return bool(expr) and croniter.is_valid(expr)


def prev_fire(cron: str, now: _dt.datetime) -> _dt.datetime:
    """The most recent fire time of ``cron`` STRICTLY before ``now``.

    Delegates to croniter.get_prev. ``now`` is passed in; the wall clock is
    never read. Raises ValueError on a malformed expression (fail-loud at the
    boundary, ~/.claude/rules/common/coding-style.md) rather than silently
    treating a typo'd cron as "never fires".
    """
    if not is_valid_cron(cron):
        raise ValueError(f"invalid cron expression: {cron!r}")
    return croniter(cron, now).get_prev(_dt.datetime)


def cron_due(
    cron: str, now: _dt.datetime, last_run: _dt.datetime | None
) -> bool:
    """Evaluate a single cron expression against the (last_run, now] window.

    Due iff the most recent fire at/before ``now`` is later than ``last_run``
    (or the job never ran). Recording ``last_run = prev_fire`` after a run
    therefore closes the window: the same fire cannot select the job twice.
    """
    fire = prev_fire(cron, now)
    if last_run is None:
        return True
    return fire > last_run


def due_jobs(
    schedules: list[dict[str, Any]],
    now: _dt.datetime,
    last_run_map: dict[str, _dt.datetime],
) -> list[str]:
    """Return the ids of jobs that are due at ``now``.

    A job is due when its cron's previous fire time is later than its recorded
    ``last_run`` (or it never ran). ``now`` is supplied by the caller — this
    function is a pure function of (schedules, now, last_run_map) and never
    consults the real clock, which is what makes temporal selection provable.

    Order of the returned ids follows ``schedules`` order (stable, no churn).
    A job with a malformed cron raises via ``cron_due``; validate the registry
    up front with ``validate_schedules`` to fail at load instead of at poll.
    """
    due: list[str] = []
    for job in schedules:
        jid = job["id"]
        if cron_due(job["cron"], now, last_run_map.get(jid)):
            due.append(jid)
    return due


def mark_run(
    last_run_map: dict[str, _dt.datetime],
    job_id: str,
    cron: str,
    now: _dt.datetime,
) -> dict[str, _dt.datetime]:
    """Return a NEW last_run map with ``job_id`` settled to its fire instant.

    Records ``prev_fire`` (the cron fire time), NOT ``now`` — so a poll that
    runs a few seconds late still closes exactly the window that fired, and the
    job is not re-selected until the next fire. Immutable: the input map is not
    mutated (~/.claude/rules/common/coding-style.md).
    """
    updated = dict(last_run_map)
    updated[job_id] = prev_fire(cron, now)
    return updated


def validate_schedules(schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a schedules registry, returning it unchanged on success.

    Fail-loud at the boundary (~/.claude/rules/common/coding-style.md): every
    job must have a string ``id``, a croniter-valid ``cron``, and an ``action``
    whose ``kind`` is in the closed ACTION_KINDS set. Duplicate ids are
    rejected so ``last_run`` bookkeeping stays unambiguous.
    """
    seen: set[str] = set()
    for job in schedules:
        jid = job.get("id")
        if not isinstance(jid, str) or not jid:
            raise ValueError(f"schedule missing string id: {job!r}")
        if jid in seen:
            raise ValueError(f"duplicate schedule id: {jid!r}")
        seen.add(jid)
        if not is_valid_cron(job.get("cron", "")):
            raise ValueError(f"schedule {jid!r} has invalid cron: {job.get('cron')!r}")
        action = job.get("action") or {}
        kind = action.get("kind")
        if kind not in ACTION_KINDS:
            raise ValueError(
                f"schedule {jid!r} has unknown action kind {kind!r}; "
                f"expected one of {sorted(ACTION_KINDS)}"
            )
    return schedules


def load_schedules(path: str | None = None) -> list[dict[str, Any]]:
    """Load and validate the schedules registry from JSON.

    Returns ``[]`` for a missing file (an un-provisioned deployment has no
    schedules — that is a valid empty state, not an error). A present-but-
    malformed registry raises via ``validate_schedules`` so a typo cannot
    silently disable scheduling.
    """
    p = path or DEFAULT_SCHEDULES_PATH
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"schedules.json must be a JSON list, got {type(data).__name__}")
    return validate_schedules(data)

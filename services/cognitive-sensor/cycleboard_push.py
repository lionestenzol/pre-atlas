#!/usr/bin/env python3
"""CycleBoard push bridge for auto_actor.

Translates auto_actor's decisions into CycleBoard-visible entries via
delta-kernel's HTTP API:

    auto_executed directive  ->  Journal entry
    needs_approval directive ->  Task [REVIEW ...] + proposals.json entry
    loops_auto_closed        ->  Momentum win

Reads:
    auto_actor_log.json             (overwritten each auto_actor run)
    loop_recommendations.json       (titles for closed loops)
    cycleboard_push_sent.json       (dedup ledger for entries already pushed)

Writes:
    auto_actor_log_archive.jsonl    (append-only snapshot, one JSON per line)
    proposals.json                  (approval queue)
    cycleboard_push_sent.json       (updated ledger)
    HTTP POSTs / PUTs to delta-kernel on :3001

The bridge never crashes on API errors: a failed POST is logged at WARN and
left out of the sent ledger so the next run retries.

Usage:
    python cycleboard_push.py               # real run
    python cycleboard_push.py --dry-run     # print what would happen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from atomic_write import atomic_write_json, atomic_write_text

BASE = Path(__file__).parent.resolve()
DELTA_URL = "http://localhost:3001"
HTTP_TIMEOUT_S = 5.0

# Input files
AUTO_ACTOR_LOG = BASE / "auto_actor_log.json"
LOOP_RECS = BASE / "loop_recommendations.json"

# Output files
LOG_ARCHIVE = BASE / "auto_actor_log_archive.jsonl"
SENT_LEDGER_PATH = BASE / "cycleboard_push_sent.json"
PROPOSALS_PATH = BASE / "proposals.json"

log = logging.getLogger("cycleboard_push")


# ---------------------------------------------------------------------------
# Auth + HTTP
# ---------------------------------------------------------------------------
def _load_api_key() -> Optional[str]:
    """Match auto_actor.py: repo-root/.aegis-tenant-key."""
    candidates = [
        BASE.parent.parent / ".aegis-tenant-key",
        BASE.parent.parent.parent / ".aegis-tenant-key",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def _http(
    method: str,
    path: str,
    body: Optional[dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Make one HTTP call. Returns parsed JSON on 2xx, else None (logs WARN)."""
    url = f"{DELTA_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        log.warning("%s %s -> HTTP %s: %s", method, path, e.code, e.read()[:200])
    except urllib.error.URLError as e:
        log.warning("%s %s -> URL error: %s", method, path, e.reason)
    except Exception as e:  # defensive
        log.warning("%s %s -> %s: %s", method, path, type(e).__name__, e)
    return None


# ---------------------------------------------------------------------------
# CycleBoard endpoints (derived from services/delta-kernel/src/cli/atlas.ts)
# ---------------------------------------------------------------------------
def get_cycleboard_state(api_key: Optional[str]) -> Optional[dict[str, Any]]:
    resp = _http("GET", "/api/cycleboard", api_key=api_key)
    if resp is None:
        return None
    return resp.get("data") or {}


def put_cycleboard_state(
    merged: dict[str, Any], api_key: Optional[str]
) -> bool:
    resp = _http("PUT", "/api/cycleboard", body=merged, api_key=api_key)
    return resp is not None


def post_task(title: str, api_key: Optional[str]) -> bool:
    body = {
        "title_template": title,
        "title_params": {},
        "status": "OPEN",
        "priority": "NORMAL",
        "due_at": None,
        "linked_thread": None,
    }
    resp = _http("POST", "/api/tasks", body=body, api_key=api_key)
    return resp is not None


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("failed to read %s: %s", path, e)
        return default


def archive_log(log_obj: dict[str, Any]) -> None:
    """Append one JSON line to auto_actor_log_archive.jsonl with _archived_at."""
    entry = {**log_obj, "_archived_at": _now_iso()}
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    # Append is not atomic, but torn writes of single lines are OK here —
    # a line-level JSON decoder will skip malformed lines on recovery.
    with LOG_ARCHIVE.open("a", encoding="utf-8") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Dedup key synthesis
# ---------------------------------------------------------------------------
def directive_entry_id(
    dtype: str, domain: str, rationale: str, run_at: str
) -> str:
    """Stable id for a directive, bucketed to the day.

    Excludes `confidence` (drifts between runs). Uses run_at truncated to
    YYYY-MM-DD so a directive re-appearing on a later day is treated as new.
    """
    day = (run_at or "")[:10]
    key = f"{dtype}|{domain}|{(rationale or '')[:80]}|{day}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Mapping: auto_actor event -> CycleBoard action
# ---------------------------------------------------------------------------
def build_journal_content(directive: dict[str, Any]) -> str:
    dtype = directive.get("directive_type", "?")
    domain = directive.get("domain", "?")
    rationale = (directive.get("rationale") or "").strip()
    suffix = f" — {rationale[:80]}" if rationale else ""
    return f"auto: {dtype}/{domain}{suffix}"


def build_review_title(directive: dict[str, Any]) -> str:
    dtype = directive.get("directive_type", "?")
    domain = directive.get("domain", "?")
    return f"[REVIEW] {dtype}/{domain}"


def build_proposal(directive: dict[str, Any], entry_id: str) -> dict[str, Any]:
    return {
        "proposal_id": entry_id,
        "dtype": directive.get("directive_type"),
        "domain": directive.get("domain"),
        "rationale": directive.get("rationale", ""),
        "suggested_action": directive.get("suggested_action", ""),
        "confidence": directive.get("confidence"),
        "risk_level": directive.get("risk_level"),
        "status": "pending",
        "proposed_at": _now_iso(),
    }


def build_win_text(loop_id: str, title: str) -> str:
    return f"Closed #{loop_id}: {title}"[:200]


def loop_title(loop_id: str, loop_recs: dict[str, Any]) -> str:
    for entry in loop_recs.get("auto_closed") or []:
        if str(entry.get("convo_id")) == str(loop_id):
            return entry.get("title") or "(untitled)"
    for entry in loop_recs.get("recommendations") or []:
        if str(entry.get("convo_id")) == str(loop_id):
            return entry.get("title") or "(untitled)"
    return "(untitled)"


# ---------------------------------------------------------------------------
# Main bridge run
# ---------------------------------------------------------------------------
def run(dry_run: bool = False) -> dict[str, Any]:
    """Execute one bridge pass. Returns a summary dict."""
    summary: dict[str, Any] = {
        "started_at": _now_iso(),
        "dry_run": dry_run,
        "journal_added": 0,
        "tasks_added": 0,
        "wins_added": 0,
        "proposals_added": 0,
        "skipped_already_sent": 0,
        "failures": 0,
    }

    log_obj = read_json(AUTO_ACTOR_LOG, None)
    if not isinstance(log_obj, dict):
        log.info("no auto_actor_log.json found — nothing to push")
        summary["note"] = "no_auto_actor_log"
        return summary

    # Archive every run (even if we push nothing new)
    if not dry_run:
        archive_log(log_obj)

    sent_ledger: dict[str, str] = read_json(SENT_LEDGER_PATH, {}) or {}
    loop_recs: dict[str, Any] = read_json(LOOP_RECS, {}) or {}
    proposals: list[dict[str, Any]] = read_json(PROPOSALS_PATH, []) or []
    proposal_ids = {p.get("proposal_id") for p in proposals}

    run_at = log_obj.get("run_at") or _now_iso()

    # Collect work
    journal_pending: list[tuple[str, str]] = []   # (eid, text)
    task_pending: list[tuple[str, str, dict[str, Any]]] = []  # (eid, title, proposal)
    win_pending: list[tuple[str, str]] = []       # (eid, text)

    for d in log_obj.get("directives_executed") or []:
        eid = directive_entry_id(
            d.get("directive_type", ""),
            d.get("domain", ""),
            d.get("rationale", ""),
            run_at,
        )
        if eid in sent_ledger:
            summary["skipped_already_sent"] += 1
            continue
        status = d.get("status")
        if status == "auto_executed":
            journal_pending.append((eid, build_journal_content(d)))
        elif status == "needs_approval":
            task_pending.append(
                (eid, build_review_title(d), build_proposal(d, eid))
            )

    for loop_id in log_obj.get("loops_auto_closed") or []:
        eid = f"loop-{loop_id}"
        if eid in sent_ledger:
            summary["skipped_already_sent"] += 1
            continue
        win_pending.append((eid, build_win_text(str(loop_id), loop_title(loop_id, loop_recs))))

    if dry_run:
        print(f"DRY RUN — would push:")
        print(f"  journal entries: {len(journal_pending)}")
        for _, text in journal_pending:
            print(f"    - {text}")
        print(f"  review tasks:    {len(task_pending)}")
        for _, title, _prop in task_pending:
            print(f"    - {title}")
        print(f"  momentum wins:   {len(win_pending)}")
        for _, text in win_pending:
            print(f"    - {text}")
        summary.update(
            journal_added=len(journal_pending),
            tasks_added=len(task_pending),
            wins_added=len(win_pending),
            proposals_added=len([p for _, _, p in task_pending if p["proposal_id"] not in proposal_ids]),
        )
        return summary

    # Real run
    api_key = _load_api_key()
    newly_sent: dict[str, str] = {}

    # Tasks: independent POSTs
    for eid, title, proposal in task_pending:
        if post_task(title, api_key):
            newly_sent[eid] = _now_iso()
            summary["tasks_added"] += 1
            if proposal["proposal_id"] not in proposal_ids:
                proposals.append(proposal)
                proposal_ids.add(proposal["proposal_id"])
                summary["proposals_added"] += 1
        else:
            summary["failures"] += 1

    # Journal + Wins: single read-modify-write of /api/cycleboard
    if journal_pending or win_pending:
        state = get_cycleboard_state(api_key)
        if state is None:
            log.warning("could not fetch cycleboard state; skipping journal+win batch")
            summary["failures"] += len(journal_pending) + len(win_pending)
        else:
            merged = dict(state)
            if journal_pending:
                journal_list = list(merged.get("Journal") or [])
                for eid, text in journal_pending:
                    journal_list.append({
                        "id": f"auto-{eid}",
                        "date": _today_date(),
                        "createdAt": _now_iso(),
                        "content": text,
                        "mood": None,
                    })
                merged["Journal"] = journal_list
            if win_pending:
                wins_list = list(merged.get("MomentumWins") or [])
                for eid, text in win_pending:
                    wins_list.append({
                        "id": f"auto-{eid}",
                        "date": _today_date(),
                        "timestamp": _now_iso(),
                        "description": text,
                    })
                merged["MomentumWins"] = wins_list
            if put_cycleboard_state(merged, api_key):
                for eid, _ in journal_pending:
                    newly_sent[eid] = _now_iso()
                    summary["journal_added"] += 1
                for eid, _ in win_pending:
                    newly_sent[eid] = _now_iso()
                    summary["wins_added"] += 1
            else:
                summary["failures"] += len(journal_pending) + len(win_pending)

    # Persist ledgers only if anything was sent
    if newly_sent:
        sent_ledger.update(newly_sent)
        atomic_write_json(SENT_LEDGER_PATH, sent_ledger)
    if summary["proposals_added"]:
        atomic_write_json(PROPOSALS_PATH, proposals)

    summary["finished_at"] = _now_iso()
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--dry-run", action="store_true", help="print what would be pushed, do not call API")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    t0 = time.time()
    summary = run(dry_run=args.dry_run)
    summary["duration_seconds"] = round(time.time() - t0, 2)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("failures", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

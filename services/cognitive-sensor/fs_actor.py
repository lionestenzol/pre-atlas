"""Mark-only actor for filesystem cards.

Reads thread_decisions.json and, for every decision whose convo_id is
an fs loop (prefix "fs-") with a terminal verdict (CLOSE/ARCHIVE/DROP),
mirrors the closure into delta-kernel via /api/law/close_loop and
writes to fs_actor_log.json. No file mutation by default — the file
stays on disk, the loop just stops resurfacing.

Runs as Phase 4.6 of run_daily.py — after the convo-side auto_actor.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
DECISIONS_PATH = BASE / "thread_decisions.json"
LOG_PATH = BASE / "fs_actor_log.json"
DELTA_URL = "http://localhost:3001"
FS_PREFIX = "fs-"
TERMINAL_VERDICTS = {"CLOSE", "ARCHIVE", "DROP"}


def _notify_delta(loop_id: str, title: str, verdict: str) -> bool:
    outcome_map = {"CLOSE": "closed", "ARCHIVE": "archived", "DROP": "dropped"}
    status_map = {"CLOSE": "RESOLVED", "ARCHIVE": "DROPPED", "DROP": "DROPPED"}
    payload = {
        "loop_id": loop_id,
        "title": title,
        "outcome": outcome_map.get(verdict, "closed"),
        "actor": "fs_actor",
        "artifact_path": None,
        "coverage_score": None,
        "status": status_map.get(verdict, "RESOLVED"),
    }
    try:
        req = urllib.request.Request(
            f"{DELTA_URL}/api/law/close_loop",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except urllib.error.URLError as exc:
        logger.info("delta-kernel unreachable for %s (%s)", loop_id, exc)
        return False


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"runs": [], "closed_ids": []}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not DECISIONS_PATH.exists():
        print("  [SKIP] thread_decisions.json not found")
        return 0

    data = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    decisions = data.get("decisions", [])

    log = _load_log()
    already_closed = set(log.get("closed_ids", []))

    run_record = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "closed": [],
        "skipped_already_closed": 0,
        "delta_unreachable": 0,
    }

    for entry in decisions:
        convo_id = str(entry.get("convo_id", ""))
        if not convo_id.startswith(FS_PREFIX):
            continue
        verdict = entry.get("verdict")
        if verdict not in TERMINAL_VERDICTS:
            continue
        if convo_id in already_closed:
            run_record["skipped_already_closed"] += 1
            continue

        title = entry.get("title", convo_id)
        notified = _notify_delta(convo_id, title, verdict)
        if not notified:
            run_record["delta_unreachable"] += 1

        run_record["closed"].append({
            "loop_id": convo_id,
            "title": title,
            "verdict": verdict,
            "delta_notified": notified,
        })
        already_closed.add(convo_id)

    log["runs"].append(run_record)
    log["closed_ids"] = sorted(already_closed)
    log["runs"] = log["runs"][-50:]  # keep last 50 runs only
    atomic_write_json(LOG_PATH, log)

    print("\n=== FS ACTOR ===")
    print(f"  fs closures this run:    {len(run_record['closed'])}")
    print(f"  already closed (skipped): {run_record['skipped_already_closed']}")
    print(f"  delta unreachable:        {run_record['delta_unreachable']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Autonomous triage of HIGH-severity fs findings via Optogon.

For each HIGH severity item in machine_scan.json that hasn't already
been decided in thread_decisions.json, starts an Optogon triage_fs_loop
session, drives it to close, and records the proposed verdict.

If the proposed confidence >= threshold, upserts the verdict into
thread_decisions.json as if the user had swiped it. Lower-confidence
findings stay on the board for manual triage.

Dry-run by default: proposes only, never acts. Set AUTO_TRIAGE_APPLY=1
to write decisions back. Logged per run in auto_triage_log.json.

Runs as Phase 1.7 of run_daily.py: after es_to_cards, before wire.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN = BASE / "cycleboard" / "brain"
SCAN_PATH = BRAIN / "machine_scan.json"
DECISIONS_PATH = BASE / "thread_decisions.json"
LOG_PATH = BASE / "auto_triage_log.json"

OPTOGON_URL = os.environ.get("OPTOGON_URL", "http://localhost:3010")
APPLY = os.environ.get("AUTO_TRIAGE_APPLY", "0") == "1"
MIN_CONFIDENCE = float(os.environ.get("AUTO_TRIAGE_MIN_CONFIDENCE", "0.85"))
MAX_TURNS = 8


def _post_json(url: str, body: dict, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _drive_to_close(session_id: str) -> dict:
    """Walk turns until we land on a close node (or hit MAX_TURNS)."""
    for _ in range(MAX_TURNS):
        data = _post_json(
            f"{OPTOGON_URL}/session/{session_id}/turn",
            {"message": "approve"},
        )
        node = data.get("state", {}).get("current_node")
        if node == "done":
            return data
    return data


def _already_decided(convo_id: str, decisions: list[dict]) -> bool:
    return any(
        str(entry.get("convo_id")) == str(convo_id) and entry.get("verdict")
        for entry in decisions
    )


def _load_decisions() -> dict:
    if not DECISIONS_PATH.exists():
        return {"generated_at": "", "session": "auto_triage", "total_cards": 0, "decisions": []}
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _apply_verdict(data: dict, convo_id: str, verdict: str, note: str, title: str) -> None:
    decisions = data.setdefault("decisions", [])
    found = next((e for e in decisions if str(e.get("convo_id")) == str(convo_id)), None)
    if found is None:
        found = {"convo_id": str(convo_id)}
        decisions.append(found)
    found["title"] = title
    found["verdict"] = verdict
    found["note"] = note
    found["decided_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    found["decided_by"] = "auto_triage"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not SCAN_PATH.exists():
        print("  [SKIP] machine_scan.json not found")
        return 0
    scan = json.loads(SCAN_PATH.read_text(encoding="utf-8"))
    high_items = [i for i in scan.get("items", []) if i.get("severity") == "high"]

    if not high_items:
        print("\n=== AUTO TRIAGE ===")
        print("  no HIGH severity fs findings")
        return 0

    decisions_doc = _load_decisions()
    decisions = decisions_doc.get("decisions", [])

    run_record = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": not APPLY,
        "min_confidence": MIN_CONFIDENCE,
        "items": [],
        "optogon_unreachable": False,
    }

    for item in high_items:
        loop_id = item["loop_id"]
        if _already_decided(loop_id, decisions):
            run_record["items"].append({"loop_id": loop_id, "skipped": "already_decided"})
            continue

        try:
            start = _post_json(
                f"{OPTOGON_URL}/session/start",
                {
                    "path_id": "triage_fs_loop",
                    "initial_context": {
                        "loop_id": loop_id,
                        "evidence": item.get("evidence", ""),
                        "severity": item.get("severity", "medium"),
                        "fs_kind": "env" if item.get("severity") == "high" else "other",
                        "age_days": item.get("age_days") or 0,
                        "title": item.get("title", loop_id),
                    },
                },
            )
        except urllib.error.URLError as exc:
            logger.warning("optogon unreachable: %s", exc)
            run_record["optogon_unreachable"] = True
            break

        sid = start.get("session_id")
        if not sid:
            run_record["items"].append({"loop_id": loop_id, "skipped": "no_session_id"})
            continue

        try:
            final = _drive_to_close(sid)
        except urllib.error.URLError as exc:
            logger.warning("optogon turn failed: %s", exc)
            run_record["optogon_unreachable"] = True
            break

        system = final.get("state", {}).get("context", {}).get("system", {})
        proposed_verdict = system.get("proposed_verdict")
        proposed_action = system.get("proposed_action")
        confidence = float(system.get("confidence") or 0.0)
        rationale = system.get("rationale", "")

        applied = False
        if (
            APPLY
            and proposed_verdict
            and proposed_verdict in {"CLOSE", "ARCHIVE", "DROP", "KEEP"}
            and confidence >= MIN_CONFIDENCE
        ):
            _apply_verdict(
                decisions_doc,
                loop_id,
                proposed_verdict,
                f"auto: {rationale} (conf {confidence:.2f})",
                item.get("title", loop_id),
            )
            applied = True

        # Rung 3: emit a Directive to Cortex for action execution when we
        # have a proposed action that requires work (ARCHIVE/rotate/delete).
        # DRY-RUN by default — only logs the directive; flip
        # CORTEX_BRIDGE_APPLY=1 to actually POST.
        directive_summary = None
        if (
            proposed_verdict in {"ARCHIVE"}
            and proposed_action
            and proposed_action != "none"
            and confidence >= MIN_CONFIDENCE
        ):
            try:
                from cortex_bridge import emit as emit_directive
                directive_summary = emit_directive(
                    loop_id=loop_id,
                    title=item.get("title", loop_id),
                    evidence=item.get("evidence", ""),
                    proposed_action=proposed_action,
                    rationale=rationale,
                    confidence=confidence,
                )
            except Exception as exc:
                logger.warning("cortex_bridge failed for %s: %s", loop_id, exc)

        run_record["items"].append({
            "loop_id": loop_id,
            "session_id": sid,
            "proposed_verdict": proposed_verdict,
            "proposed_action": proposed_action,
            "confidence": confidence,
            "rationale": rationale,
            "applied": applied,
            "directive": directive_summary,
        })

    if APPLY and any(i.get("applied") for i in run_record["items"]):
        decisions_doc["total_cards"] = len(decisions_doc["decisions"])
        atomic_write_json(DECISIONS_PATH, decisions_doc)

    log = {"runs": [], "last_run": run_record}
    if LOG_PATH.exists():
        try:
            prior = json.loads(LOG_PATH.read_text(encoding="utf-8"))
            log["runs"] = (prior.get("runs") or [])[-19:]
        except json.JSONDecodeError:
            pass
    log["runs"].append(run_record)
    atomic_write_json(LOG_PATH, log)

    print("\n=== AUTO TRIAGE ===")
    print(f"  mode:            {'APPLY' if APPLY else 'DRY-RUN (set AUTO_TRIAGE_APPLY=1 to write)'}")
    print(f"  threshold:       {MIN_CONFIDENCE}")
    print(f"  fs findings:     {len(high_items)}")
    print(f"  sessions run:    {sum(1 for i in run_record['items'] if 'proposed_verdict' in i)}")
    print(f"  auto-applied:    {sum(1 for i in run_record['items'] if i.get('applied'))}")
    print(f"  skipped:         {sum(1 for i in run_record['items'] if 'skipped' in i)}")
    if run_record["optogon_unreachable"]:
        print("  [WARN] optogon unreachable: start it with services/optogon/start.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

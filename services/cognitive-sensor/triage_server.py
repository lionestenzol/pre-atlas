"""HTTP server for the thread cards triage UI.

Extends python's SimpleHTTPRequestHandler with one endpoint:

  POST /api/decide
    body: {"convo_id": "...", "verdict": "CLOSE", "note": "..."}
    writes the decision to thread_decisions.json and fires the
    atlas sync pipeline (fs_actor + decisions_to_atlas) in the
    background so closed loops vanish from governance state
    without a separate `atl apply` step.

GET requests fall through to the filesystem — same behaviour as
`python -m http.server`, so thread_cards.html still renders normally.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN = BASE / "cycleboard" / "brain"
DECISIONS_PATH = BASE / "thread_decisions.json"
SCAN_PATH = BRAIN / "machine_scan.json"
VALID_VERDICTS = {"KEEP", "CLOSE", "MINE", "ARCHIVE", "REVIEW", "DROP"}
SYNC_SCRIPTS = ("fs_actor.py", "decisions_to_atlas.py")
_sync_lock = threading.Lock()
_sync_pending = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_decisions() -> dict:
    if not DECISIONS_PATH.exists():
        return {
            "generated_at": _now_iso(),
            "session": "live",
            "total_cards": 0,
            "decisions": [],
        }
    return json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))


def _upsert_decision(convo_id: str, verdict: str, note: str, title: str) -> dict:
    data = _load_decisions()
    decisions = data.setdefault("decisions", [])
    found = None
    for entry in decisions:
        if str(entry.get("convo_id")) == str(convo_id):
            found = entry
            break
    if found is None:
        found = {"convo_id": str(convo_id), "title": title}
        decisions.append(found)
    found["verdict"] = verdict
    found["note"] = note
    found["decided_at"] = _now_iso()
    if title and not found.get("title"):
        found["title"] = title
    data["total_cards"] = len(decisions)
    data["generated_at"] = _now_iso()
    atomic_write_json(DECISIONS_PATH, data)
    return found


def _run_sync_pipeline() -> None:
    """Best-effort: push decisions downstream. Swallows failures."""
    global _sync_pending
    with _sync_lock:
        if _sync_pending:
            return
        _sync_pending = True
    try:
        for script in SYNC_SCRIPTS:
            script_path = BASE / script
            if not script_path.exists():
                continue
            try:
                subprocess.run(
                    [sys.executable, str(script_path)],
                    cwd=str(BASE),
                    capture_output=True,
                    timeout=20,
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                logger.warning("sync %s failed: %s", script, exc)
    finally:
        with _sync_lock:
            _sync_pending = False


class TriageHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write(f"[triage] {fmt % args}\n")

    def _respond(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/api/decide":
            self._respond(404, {"error": "not found", "path": self.path})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._respond(400, {"error": "invalid json"})
            return

        convo_id = str(body.get("convo_id", "")).strip()
        verdict = str(body.get("verdict", "")).strip().upper()
        note = str(body.get("note", ""))
        title = str(body.get("title", ""))

        if not convo_id:
            self._respond(400, {"error": "missing convo_id"})
            return
        if verdict and verdict not in VALID_VERDICTS:
            self._respond(400, {"error": f"invalid verdict {verdict!r}"})
            return

        entry = _upsert_decision(convo_id, verdict, note, title)
        threading.Thread(target=_run_sync_pipeline, daemon=True).start()

        # Rung 1: REVIEW on an fs card -> async Optogon reasoning session
        if verdict == "REVIEW" and convo_id.startswith("fs-"):
            threading.Thread(
                target=_fire_optogon_triage, args=(convo_id,), daemon=True
            ).start()

        self._respond(200, {"ok": True, "decision": entry})


def _fire_optogon_triage(convo_id: str) -> None:
    """Find the fs card in machine_scan.json and start an Optogon triage session."""
    try:
        from auto_triage import OPTOGON_URL, _drive_to_close, _post_json
    except ImportError:
        logger.warning("auto_triage import failed; skipping optogon fire")
        return
    if not SCAN_PATH.exists():
        return
    try:
        scan = json.loads(SCAN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    item = next((i for i in scan.get("items", []) if i.get("loop_id") == convo_id), None)
    if not item:
        return
    try:
        start = _post_json(
            f"{OPTOGON_URL}/session/start",
            {
                "path_id": "triage_fs_loop",
                "initial_context": {
                    "loop_id": convo_id,
                    "evidence": item.get("evidence", ""),
                    "severity": item.get("severity", "medium"),
                    "fs_kind": "env" if item.get("severity") == "high" else "other",
                    "age_days": item.get("age_days") or 0,
                    "title": item.get("title", convo_id),
                },
            },
        )
        sid = start.get("session_id")
        if sid:
            _drive_to_close(sid)
            logger.info("optogon triage fired for %s (session %s)", convo_id, sid)
    except Exception as exc:
        logger.warning("optogon fire failed for %s: %s", convo_id, exc)


def serve(port: int = 8765) -> int:
    import os
    os.chdir(str(BASE))
    server = ThreadingHTTPServer(("127.0.0.1", port), TriageHandler)
    print(f"[triage] serving {BASE}")
    print(f"[triage] http://localhost:{port}/thread_cards.html")
    print(f"[triage] POST /api/decide enabled (live atlas sync)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[triage] stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    raise SystemExit(serve(args.port))

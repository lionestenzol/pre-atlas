"""HTTP server for the thread cards triage UI.

Endpoints:

  POST /api/decide
    body: {"convo_id": "...", "verdict": "CLOSE", "note": "...", "title": "..."}
    writes the decision to thread_decisions.json and fires the atlas sync
    pipeline (fs_actor + decisions_to_atlas) on a background thread so
    closed loops vanish from governance state without a separate
    `atl apply` step.

  GET /api/conv/<index>
    returns one full conversation by its numeric index in memory_db.json.
    convo_ids in the atlas payload are these indices as strings.

All other GETs fall through to a StaticFiles mount over this directory —
same behaviour as `python -m http.server`, so thread_cards.html and the
other atlas viewers still render normally.

Bound to 127.0.0.1 only. Atlas Law #2 (Assemble First): raw http.server +
manual JSON dispatch is a solved-category reinvention — FastAPI handles
routing, CORS, and static-file serving; we keep the existing sync
helpers + daemon-thread fan-out for the background work.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from atomic_write import atomic_write_json

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.resolve()
BRAIN = BASE / "cycleboard" / "brain"
DECISIONS_PATH = BASE / "thread_decisions.json"
SCAN_PATH = BRAIN / "machine_scan.json"
MEMORY_DB_PATH = BASE / "memory_db.json"
VALID_VERDICTS = {"KEEP", "CLOSE", "MINE", "ARCHIVE", "REVIEW", "DROP", "DONE", "SKIP"}
SYNC_SCRIPTS = ("fs_actor.py", "decisions_to_atlas.py")
_sync_lock = threading.Lock()
_sync_pending = False
_memory_db_cache: list | None = None
_memory_db_lock = threading.Lock()


# --------------------------- helpers (unchanged) ---------------------------

def _load_memory_db() -> list:
    """Lazy-load memory_db.json on first request, cache thereafter."""
    global _memory_db_cache
    if _memory_db_cache is None:
        with _memory_db_lock:
            if _memory_db_cache is None:
                if MEMORY_DB_PATH.exists():
                    with open(MEMORY_DB_PATH, "r", encoding="utf-8") as f:
                        _memory_db_cache = json.load(f)
                else:
                    _memory_db_cache = []
    return _memory_db_cache


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


# ------------------------------ FastAPI app ------------------------------

app = FastAPI(title="cognitive-sensor triage", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/conv/{raw:path}")
def get_conv(raw: str) -> JSONResponse:
    """Return one full conversation by its numeric index in memory_db.json."""
    raw = raw.strip("/")
    try:
        idx = int(raw)
    except ValueError:
        return JSONResponse({"error": "convo_id must be integer index"}, status_code=400)
    db = _load_memory_db()
    if idx < 0 or idx >= len(db):
        return JSONResponse(
            {"error": "convo_id out of range", "convo_id": raw, "total": len(db)},
            status_code=404,
        )
    convo = db[idx]
    return JSONResponse(
        {
            "convo_id": str(idx),
            "title": convo.get("title", ""),
            "messages": convo.get("messages", []),
        }
    )


@app.post("/api/decide")
async def post_decide(request: Request) -> JSONResponse:
    """Record a triage verdict and fan out background syncs."""
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"error": "invalid json"}, status_code=400)

    convo_id = str(body.get("convo_id", "")).strip()
    verdict = str(body.get("verdict", "")).strip().upper()
    note = str(body.get("note", ""))
    title = str(body.get("title", ""))

    if not convo_id:
        return JSONResponse({"error": "missing convo_id"}, status_code=400)
    if verdict and verdict not in VALID_VERDICTS:
        return JSONResponse({"error": f"invalid verdict {verdict!r}"}, status_code=400)

    entry = _upsert_decision(convo_id, verdict, note, title)
    threading.Thread(target=_run_sync_pipeline, daemon=True).start()

    # Rung 1: REVIEW on an fs card -> async Optogon reasoning session
    if verdict == "REVIEW" and convo_id.startswith("fs-"):
        threading.Thread(
            target=_fire_optogon_triage, args=(convo_id,), daemon=True
        ).start()

    return JSONResponse({"ok": True, "decision": entry})


# Static-file fall-through — mounted LAST so /api/* routes take priority.
# `html=True` makes "/" return index.html if present (matches the prior
# SimpleHTTPRequestHandler fall-through used to serve thread_cards.html etc).
app.mount("/", StaticFiles(directory=str(BASE), html=True), name="static")


# ----------------------------- entry point -----------------------------

def serve(port: int = 8765) -> int:
    """Boot uvicorn with the FastAPI app. Preserves prior `serve()` contract."""
    import uvicorn

    os.chdir(str(BASE))
    print(f"[triage] serving {BASE}")
    print(f"[triage] http://localhost:{port}/thread_cards.html")
    print(f"[triage] http://localhost:{port}/cognitive_atlas.html  (atlas viewer)")
    print(f"[triage] POST /api/decide enabled (live atlas sync)")
    print(f"[triage] GET  /api/conv/<id> enabled (full conv text)")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except KeyboardInterrupt:
        print("\n[triage] stopped")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    raise SystemExit(serve(args.port))

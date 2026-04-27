"""
Derive lifecycle state from harvest manifests + closures.json.

Shared helper for wire_cycleboard.py, export_cognitive_state.py,
governor_daily.py, governor_weekly.py, build_dashboard.py.

Single source of truth — keeps all consumers aligned.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.resolve()
HARVEST_DIR = BASE / "harvest"
CLOSURES_PATH = BASE / "closures.json"

IN_PROGRESS_STATUSES = {"PLANNED", "BUILDING", "REVIEWING"}
TERMINAL_STATUSES = {"DONE", "RESOLVED", "DROPPED"}
ALL_STATUSES = ("HARVESTED", "PLANNED", "BUILDING", "REVIEWING", "DONE", "RESOLVED", "DROPPED")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_closures() -> list[dict]:
    raw = _read_json(CLOSURES_PATH)
    if raw is None:
        return []
    if isinstance(raw, dict):
        closures = raw.get("closures", [])
    else:
        closures = raw
    return closures if isinstance(closures, list) else []


def manifest_statuses() -> dict[str, dict]:
    """Return {convo_id (str): manifest-dict} for every harvest manifest on disk."""
    result: dict[str, dict] = {}
    if not HARVEST_DIR.exists():
        return result
    for entry in sorted(HARVEST_DIR.iterdir()):
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        m = _read_json(manifest_path)
        if not isinstance(m, dict):
            continue
        cid = m.get("convo_id")
        if cid is None:
            continue
        result[str(cid)] = m
    return result


def summarize(now: datetime | None = None, window_days: int = 1) -> dict[str, Any]:
    """Build the lifecycle summary used by all readers.

    window_days = 1 → today only (for daily brief / cycleboard).
    window_days = 7 → last 7 days (for weekly packet).
    """
    now = now or datetime.now(timezone.utc)
    cutoff_day = (now - timedelta(days=window_days)).date()

    counts = {s: 0 for s in ALL_STATUSES}
    in_progress: list[dict] = []
    manifests = manifest_statuses()
    for cid, m in manifests.items():
        status = m.get("status", "HARVESTED")
        if status in counts:
            counts[status] += 1
        if status in IN_PROGRESS_STATUSES:
            in_progress.append({
                "convo_id": cid,
                "title": m.get("title"),
                "status": status,
                "artifact_path": m.get("artifact_path"),
                "building_started_at": m.get("building_started_at"),
                "reviewed_at": m.get("reviewed_at"),
                "coverage_score": m.get("coverage_score"),
            })

    terminal_window: dict[str, list[dict]] = {s: [] for s in TERMINAL_STATUSES}
    artifacts_shipped: list[dict] = []
    for c in _load_closures():
        status = c.get("status")
        ts = c.get("ts")
        if status not in terminal_window or ts is None:
            continue
        closed_day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date()
        if closed_day < cutoff_day:
            continue
        entry = {
            "loop_id": c.get("loop_id"),
            "title": c.get("title"),
            "artifact_path": c.get("artifact_path"),
            "coverage_score": c.get("coverage_score"),
            "closed_at": closed_day.isoformat(),
        }
        terminal_window[status].append(entry)
        if status == "DONE" and c.get("artifact_path"):
            artifacts_shipped.append(entry)

    return {
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "window_days": window_days,
        "counts": counts,
        "in_progress": in_progress,
        "terminal_window": terminal_window,
        "artifacts_shipped": artifacts_shipped,
    }


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(json.dumps(summarize(window_days=days), indent=2))

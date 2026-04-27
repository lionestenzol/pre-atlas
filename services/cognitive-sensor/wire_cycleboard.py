"""
Wires cognitive, governance, and idea data into CycleBoard brain directory.

Copies state files so CycleBoard can load them via fetch().
For idea_registry.json, generates a trimmed version (top ideas only)
to keep the brain directory lightweight.
Also derives lifecycle_board.json from harvest manifests + today's closures.
"""

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from atomic_write import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).parent.resolve()
CYCLEBOARD_DIR = WORKSPACE / "cycleboard"
BRAIN_DIR = CYCLEBOARD_DIR / "brain"
HARVEST_DIR = WORKSPACE / "harvest"
IN_PROGRESS_STATUSES = {"PLANNED", "BUILDING", "REVIEWING"}
TERMINAL_STATUSES = {"DONE", "RESOLVED", "DROPPED"}

print("=" * 50)
print("COGNITIVE WIRING")
print("=" * 50)

BRAIN_DIR.mkdir(parents=True, exist_ok=True)

# Direct copy files: source name -> brain name
COPY_FILES = {
    "cognitive_state.json": "cognitive_state.json",
    "daily_directive.txt": "daily_directive.txt",
    "daily_payload.json": "daily_payload.json",
    "governance_state.json": "governance_state.json",
    "governor_headline.json": "governor_headline.json",
    "prediction_results.json": "prediction_results.json",
    "closures.json": "closures.json",
}

for src_name, dst_name in COPY_FILES.items():
    src = WORKSPACE / src_name
    if src.exists():
        content = src.read_text(encoding="utf-8")
        atomic_write_text(BRAIN_DIR / dst_name, content)
        print(f"[OK] {src_name}")
    else:
        print(f"[WARN] {src_name} not found")

# Trim idea_registry.json — full file is ~3MB, CycleBoard only needs top ideas
idea_src = WORKSPACE / "idea_registry.json"
if idea_src.exists():
    try:
        with open(idea_src, "r", encoding="utf-8") as f:
            registry = json.load(f)

        tiers = registry.get("tiers", {})
        metadata = registry.get("metadata", {})

        execute_now = tiers.get("execute_now", [])[:10]
        next_up = tiers.get("next_up", [])[:10]

        # Strip heavy fields to save space
        for idea in execute_now + next_up:
            idea.pop("embedding", None)
            idea.pop("all_key_quotes", None)
            idea.pop("combined_signals", None)

        trimmed = {
            "metadata": {
                "generated_at": metadata.get("generated_at", ""),
                "total_ideas": metadata.get("total_ideas", 0),
                "tier_breakdown": metadata.get("tier_breakdown", {}),
            },
            "execute_now": execute_now,
            "next_up": next_up,
        }

        out = BRAIN_DIR / "idea_registry.json"
        atomic_write_json(out, trimmed, ensure_ascii=False)
        print(f"[OK] idea_registry.json (trimmed: {len(execute_now)} execute_now, {len(next_up)} next_up)")
    except Exception as e:
        print(f"[WARN] idea_registry.json trim failed: {e}")
else:
    print("[WARN] idea_registry.json not found")


def _build_lifecycle_board() -> dict:
    """Join harvest manifests with today's closures into a single CycleBoard feed."""
    in_progress: list[dict] = []
    counts = {s: 0 for s in ("HARVESTED", "PLANNED", "BUILDING", "REVIEWING", "DONE", "RESOLVED", "DROPPED")}

    if HARVEST_DIR.exists():
        for entry in sorted(HARVEST_DIR.iterdir()):
            manifest = entry / "manifest.json"
            if not manifest.exists():
                continue
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            status = m.get("status", "HARVESTED")
            if status in counts:
                counts[status] += 1
            if status in IN_PROGRESS_STATUSES:
                in_progress.append({
                    "convo_id": m.get("convo_id"),
                    "title": m.get("title"),
                    "status": status,
                    "artifact_path": m.get("artifact_path"),
                    "building_started_at": m.get("building_started_at"),
                    "reviewed_at": m.get("reviewed_at"),
                    "coverage_score": m.get("coverage_score"),
                })

    terminal_today: dict[str, list[dict]] = {"DONE": [], "RESOLVED": [], "DROPPED": []}
    closures_path = WORKSPACE / "closures.json"
    today_iso = date.today().isoformat()
    if closures_path.exists():
        try:
            raw = json.loads(closures_path.read_text(encoding="utf-8"))
            closures = raw.get("closures", raw) if isinstance(raw, dict) else raw
            if isinstance(closures, list):
                for c in closures:
                    status = c.get("status")
                    ts = c.get("ts")
                    if status not in terminal_today or ts is None:
                        continue
                    # ts is ms since epoch
                    closed_day = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat()
                    if closed_day == today_iso:
                        terminal_today[status].append({
                            "loop_id": c.get("loop_id"),
                            "title": c.get("title"),
                            "artifact_path": c.get("artifact_path"),
                            "coverage_score": c.get("coverage_score"),
                        })
        except Exception:
            pass

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "in_progress": in_progress,
        "terminal_today": terminal_today,
        "counts": counts,
    }


lifecycle = _build_lifecycle_board()
atomic_write_json(BRAIN_DIR / "lifecycle_board.json", lifecycle, ensure_ascii=False)
print(f"[OK] lifecycle_board.json "
      f"({len(lifecycle['in_progress'])} in-progress, "
      f"{sum(len(v) for v in lifecycle['terminal_today'].values())} terminal today)")

print()
print("Brain files wired to:", BRAIN_DIR)

"""
Wires cognitive, governance, and idea data into CycleBoard brain directory.

Copies state files so CycleBoard can load them via fetch().
For idea_registry.json, generates a trimmed version (top ideas only)
to keep the brain directory lightweight.
"""

import json
import shutil
from pathlib import Path
from atomic_write import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).parent.resolve()
CYCLEBOARD_DIR = WORKSPACE / "cycleboard"
BRAIN_DIR = CYCLEBOARD_DIR / "brain"

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

print()
print("Brain files wired to:", BRAIN_DIR)

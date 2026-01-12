"""
Build daily projection artifact.
Combines cognitive_state.json + daily routing into a single stamped file.
"""
import json
from datetime import datetime
from pathlib import Path
from validate import require_valid

BASE = Path(__file__).parent.resolve()
REPO = BASE.parent.parent
OUT_DIR = REPO / "data" / "projections"

# Load cognitive state
cognitive = json.load(open(BASE / "cognitive_state.json", encoding="utf-8"))

# Compute directive (same logic as export_daily_payload.py)
loops = cognitive["loops"]
closure = cognitive["closure"]
open_count = closure["open"]
ratio = closure["ratio"]

if ratio < 15:
    mode = "CLOSURE"
    build_allowed = False
    risk = "HIGH"
    primary_action = f"Close or archive: {loops[0]['title']}" if loops else "No loops detected."
elif open_count > 20:
    mode = "CLOSURE"
    build_allowed = False
    risk = "HIGH"
    primary_action = f"Close 2 loops. Start with: {loops[0]['title']}" if loops else "Run loops.py"
elif open_count > 10:
    mode = "MAINTENANCE"
    build_allowed = True
    risk = "MEDIUM"
    primary_action = f"Review: {loops[0]['title']}" if loops else "Backlog healthy."
else:
    mode = "BUILD"
    build_allowed = True
    risk = "LOW"
    primary_action = "Create freely."

directive = {
    "mode": mode,
    "build_allowed": build_allowed,
    "primary_action": primary_action,
    "open_loops": [l["title"] for l in loops[:5]],
    "open_loop_count": open_count,
    "closure_ratio": ratio,
    "risk": risk
}

# Build projection
projection = {
    "version": "1",
    "generated_at": datetime.now().isoformat(),
    "cognitive": cognitive,
    "directive": directive
}

# Validate against contract
require_valid(projection, "DailyProjection.v1.json", "build_projection")

# Write to data/projections/today.json
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / "today.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(projection, f, indent=2)

print(f"Daily projection written to {out_path}")

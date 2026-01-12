import json
from datetime import datetime
from pathlib import Path
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# Load cognitive state (source of truth)
state = json.load(open(BASE / "cognitive_state.json", encoding="utf-8"))

loops = state["loops"]
closure = state["closure"]

open_count = closure["open"]
ratio = closure["ratio"]

# Routing logic
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

payload = {
    "mode": mode,
    "build_allowed": build_allowed,
    "primary_action": primary_action,
    "open_loops": [l["title"] for l in loops[:5]],
    "open_loop_count": open_count,
    "closure_ratio": ratio,
    "risk": risk,
    "generated_at": datetime.now().strftime("%Y-%m-%d")
}

# Validate against contract before writing
require_valid(payload, "DailyPayload.v1.json", "export_daily_payload")

# Destination: CycleBoard nervous system (repo-local)
OUT = BASE / "cycleboard" / "brain" / "daily_payload.json"
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

# Also write to local directory for easy access
LOCAL_OUT = BASE / "daily_payload.json"
with open(LOCAL_OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

print(f"Daily payload exported to {OUT} (contract validated).")

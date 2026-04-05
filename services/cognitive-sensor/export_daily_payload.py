import json
from datetime import datetime
from pathlib import Path
from validate import require_valid
from atlas_config import compute_mode
from atomic_write import atomic_write_json

BASE = Path(__file__).parent.resolve()

# Load cognitive state (source of truth)
state = json.load(open(BASE / "cognitive_state.json", encoding="utf-8"))

loops = state["loops"]
closure = state["closure"]

open_count = closure["open"]
ratio = closure["ratio"]

# Routing via single source of truth
mode, risk, build_allowed = compute_mode(ratio, open_count)

# Generate primary action based on mode
if mode == "CLOSURE":
    primary_action = f"Close or archive: {loops[0]['title']}" if loops else "No loops detected."
elif mode == "MAINTENANCE":
    primary_action = f"Review: {loops[0]['title']}" if loops else "Backlog healthy."
else:
    primary_action = "Create freely."

payload = {
    "schema_version": "1.1.0",
    "mode_source": "cognitive-sensor",
    "mode": mode,
    "build_allowed": build_allowed,
    "primary_action": primary_action,
    "open_loops": [l["title"] for l in loops[:5]],
    "open_loop_count": open_count,
    "closure_ratio": ratio,
    "risk": risk,
    "generated_at": datetime.now().strftime("%Y-%m-%d")
}

# Merge prediction results if available
pred_path = BASE / "prediction_results.json"
try:
    if pred_path.exists():
        pred_data = json.load(open(pred_path, encoding="utf-8"))
        payload["predictions"] = {
            "status": pred_data.get("status", "unavailable"),
            "top_actions": pred_data.get("top_actions", [])[:3],
            "pattern_count": len(pred_data.get("active_patterns", [])),
            "mode_forecast": pred_data.get("mode_forecast"),
            "exit_path": pred_data.get("exit_path"),
        }
except Exception:
    payload["predictions"] = {"status": "unavailable"}

# Validate against contract before writing
require_valid(payload, "DailyPayload.v1.json", "export_daily_payload")

# Destination: CycleBoard nervous system (repo-local)
OUT = BASE / "cycleboard" / "brain" / "daily_payload.json"
atomic_write_json(OUT, payload)

# Also write to local directory for easy access
LOCAL_OUT = BASE / "daily_payload.json"
atomic_write_json(LOCAL_OUT, payload)

print(f"Daily payload exported to {OUT} (contract validated).")

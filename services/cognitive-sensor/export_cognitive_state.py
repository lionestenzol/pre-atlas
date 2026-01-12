import json
import subprocess
from pathlib import Path
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# Generate cognitive state from API
out = subprocess.check_output(["python", str(BASE / "cognitive_api.py")], cwd=BASE)
state = json.loads(out)

# Validate against contract before writing
require_valid(state, "CognitiveMetricsComputed.json", "export_cognitive_state")

# Write validated output
with open(BASE / "cognitive_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)

print("Exported cognitive_state.json (contract validated).")

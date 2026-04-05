import json
import subprocess
from pathlib import Path
from validate import require_valid
from atomic_write import atomic_write_json

BASE = Path(__file__).parent.resolve()

# Generate cognitive state from API
out = subprocess.check_output(["python", str(BASE / "cognitive_api.py")], cwd=BASE)
state = json.loads(out)

# Validate against contract before writing
require_valid(state, "CognitiveMetricsComputed.json", "export_cognitive_state")

# Write validated output (atomic to prevent partial reads)
atomic_write_json(BASE / "cognitive_state.json", state)

print("Exported cognitive_state.json (contract validated).")

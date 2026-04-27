import json
import subprocess
from pathlib import Path
from validate import require_valid
from atomic_write import atomic_write_json
from lifecycle_summary import summarize, manifest_statuses

BASE = Path(__file__).parent.resolve()

# Generate cognitive state from API
out = subprocess.check_output(["python", str(BASE / "cognitive_api.py")], cwd=BASE)
state = json.loads(out)

# Enrich with lifecycle data so downstream readers see status + artifact links
manifests = manifest_statuses()
for loop in state.get("loops", []) or []:
    cid = str(loop.get("convo_id", ""))
    m = manifests.get(cid)
    if m:
        loop["status"] = m.get("status", "HARVESTED")
        loop["artifact_path"] = m.get("artifact_path")
        if m.get("coverage_score") is not None:
            loop["coverage_score"] = m["coverage_score"]
state["lifecycle"] = summarize(window_days=1)

# Validate against contract before writing
require_valid(state, "CognitiveMetricsComputed.json", "export_cognitive_state")

# Write validated output (atomic to prevent partial reads)
atomic_write_json(BASE / "cognitive_state.json", state)

print("Exported cognitive_state.json (contract validated, lifecycle enriched).")

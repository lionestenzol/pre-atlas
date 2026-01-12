"""
Push daily projection to Delta API.
Bridges cognitive-sensor → delta-kernel.
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.resolve()
PROJECTION_PATH = REPO / "data" / "projections" / "today.json"
DELTA_API = "http://localhost:3001/api/ingest/cognitive"


def push_projection():
    if not PROJECTION_PATH.exists():
        print(f"[ERROR] Projection not found: {PROJECTION_PATH}")
        return False

    projection = json.load(open(PROJECTION_PATH, encoding="utf-8"))

    try:
        req = urllib.request.Request(
            DELTA_API,
            data=json.dumps(projection).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"Pushed to Delta: mode={result.get('mode')}, open_loops={result.get('open_loops')}")
            return True
    except urllib.error.URLError as e:
        print(f"[WARN] Delta API not reachable: {e.reason}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to push to Delta: {e}")
        return False


if __name__ == "__main__":
    push_projection()

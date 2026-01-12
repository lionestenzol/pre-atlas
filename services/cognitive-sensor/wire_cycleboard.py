"""
Wires your cognitive directive into CycleBoard.

CycleBoard lives in services/cognitive-sensor/cycleboard_app3.html.
This script ensures cognitive_state.json is available for fetch().

For local file:// access, the cognitive integration works automatically.
For http:// server access, run: python -m http.server 8080
"""

import shutil
from pathlib import Path

# Paths (relative to this script's location)
WORKSPACE = Path(__file__).parent.resolve()
CYCLEBOARD_DIR = WORKSPACE / "cycleboard"
BRAIN_DIR = CYCLEBOARD_DIR / "brain"

print("=" * 50)
print("COGNITIVE WIRING")
print("=" * 50)

# Check cognitive state exists
state_file = WORKSPACE / "cognitive_state.json"
if state_file.exists():
    print(f"[OK] cognitive_state.json exists in workspace")
    print(f"     CycleBoard will load it via fetch()")
else:
    print("[FAIL] cognitive_state.json not found.")
    print("       Run: python refresh.py")

# Check daily directive exists
directive_file = WORKSPACE / "daily_directive.txt"
if directive_file.exists():
    print(f"[OK] daily_directive.txt exists in workspace")
else:
    print("[WARN] daily_directive.txt not found.")
    print("       Run: python route_today.py")

# Copy to cycleboard/brain for CycleBoard consumption
BRAIN_DIR.mkdir(parents=True, exist_ok=True)

if state_file.exists():
    shutil.copy(state_file, BRAIN_DIR / "cognitive_state.json")
    print(f"[OK] Copied to: {BRAIN_DIR}")

if directive_file.exists():
    shutil.copy(directive_file, BRAIN_DIR / "daily_directive.txt")

print()
print("=" * 50)
print("TO USE CYCLEBOARD:")
print("=" * 50)
print()
print("Option 1: Direct file access")
print(f"  Open: {WORKSPACE / 'cycleboard_app3.html'}")
print()
print("Option 2: Local server (required for fetch)")
print(f"  cd {WORKSPACE}")
print("  python -m http.server 8080")
print("  Open: http://localhost:8080/cycleboard_app3.html")
print()
print("The cognitive banner will show:")
print("  - RED    = CLOSURE mode (close loops)")
print("  - YELLOW = MAINTENANCE mode (review)")
print("  - GREEN  = BUILD mode (create)")
print()

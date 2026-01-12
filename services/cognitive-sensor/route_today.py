import json
from datetime import datetime

# Load cognitive state
state = json.load(open("cognitive_state.json", encoding="utf-8"))

loops = state["loops"]
closure = state["closure"]
open_count = closure["open"]
ratio = closure["ratio"]

# Routing logic: Protect against abandoned projects
if ratio < 15:
    mode = "CLOSURE"
    reason = f"Low closure ratio ({ratio}%). You're abandoning too many loops."
    action = f"Close or archive 1 loop today. Start with: {loops[0]['title']}" if loops else "No loops to close."
elif open_count > 20:
    mode = "CLOSURE"
    reason = f"High loop backlog ({open_count} open). Cognitive load building."
    action = f"Close 2 loops today. Start with: {loops[0]['title']}" if loops else "Run loops.py first."
elif open_count > 10:
    mode = "MAINTENANCE"
    reason = f"Moderate loop backlog ({open_count} open)."
    action = f"Review: {loops[0]['title']}" if loops else "Backlog under control."
else:
    mode = "BUILD"
    reason = f"Backlog healthy ({open_count} open, {ratio}% closure)."
    action = "Focus on creation today. Low cognitive debt."

# Output directive
directive = f"""
=== DAILY ROUTING ===
Date: {datetime.now().strftime('%Y-%m-%d')}

MODE: {mode}
WHY: {reason}
ACTION: {action}
"""

print(directive)

# Save for external tools
with open("daily_directive.txt", "w", encoding="utf-8") as f:
    f.write(directive)

print("Saved to daily_directive.txt")

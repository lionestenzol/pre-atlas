import json
from datetime import datetime
from atlas_config import compute_mode

# Load cognitive state
state = json.load(open("cognitive_state.json", encoding="utf-8"))

loops = state["loops"]
closure = state["closure"]
open_count = closure["open"]
ratio = closure["ratio"]
closure_quality = closure.get("closure_quality", 100.0)

# Routing via single source of truth in atlas_config
mode, _, _ = compute_mode(ratio, open_count, closure_quality)

# Generate human-readable reason and action
if mode == "CLOSURE":
    if closure_quality < 30:
        truly_closed = closure.get("truly_closed", 0)
        archived = closure.get("archived", 0)
        reason = f"Closure quality {closure_quality}% — you archived {archived} loops but only truly closed {truly_closed}. Archiving is not closing."
        action = f"Pick 1 archived loop and actually finish it. Or close: {loops[0]['title']}" if loops else "Review your archived loops — finish or delete them."
    elif ratio < 15:
        reason = f"Low closure ratio ({ratio}%). You're abandoning too many loops."
        action = f"Close or archive 1 loop today. Start with: {loops[0]['title']}" if loops else "No loops to close."
    else:
        reason = f"High loop backlog ({open_count} open). Cognitive load building."
        action = f"Close or archive 1 loop today. Start with: {loops[0]['title']}" if loops else "No loops to close."
elif mode == "MAINTENANCE":
    reason = f"Moderate loop backlog ({open_count} open)."
    action = f"Review: {loops[0]['title']}" if loops else "Backlog under control."
else:
    reason = f"Backlog healthy ({open_count} open, {ratio}% closure, {closure_quality}% quality)."
    action = "Focus on creation today. Low cognitive debt."

# Output directive
directive = f"""=== DAILY ROUTING ===
Date: {datetime.now().strftime('%Y-%m-%d')}

MODE: {mode}
CLOSURE QUALITY: {closure_quality}% (truly closed vs archived)
WHY: {reason}
ACTION: {action}
"""

print(directive)

# Save for external tools
with open("daily_directive.txt", "w", encoding="utf-8") as f:
    f.write(directive)

print("Saved to daily_directive.txt")

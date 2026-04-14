"""
Strategic Leverage Router — Pipeline Step

Reads leverage_map.json + cognitive_state.json, produces strategic_priorities.json.
Deterministic rule-based mapping: no AI, no ML, just rules.

Outputs:
  - strategic_priorities.json (canonical)
  - cycleboard/brain/strategic_priorities.json (CycleBoard copy)
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.resolve()
CYCLEBOARD_BRAIN = BASE / "cycleboard" / "brain"

# === INPUTS ===

def load_json(path: Path, name: str):
    if not path.exists():
        print(f"[WARN] {name} not found at {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

leverage = load_json(BASE / "leverage_map.json", "leverage_map.json")
cognitive = load_json(BASE / "cognitive_state.json", "cognitive_state.json")
overrides = load_json(BASE / "cluster_focus_overrides.json", "cluster_focus_overrides.json") or {}

if not leverage:
    print("[FAIL] Cannot build strategic priorities without leverage_map.json")
    raise SystemExit(1)

# === CLUSTER → FOCUS AREA MAPPING ===

FOCUS_AREA_RULES = {
    # (asset_vector, revenue_tag_contains) → focus_area
    ("Tool", None): "Production",
    ("Framework", None): "Production",
    ("Content Engine", "productizable"): "Production",
    ("Content Engine", "infrastructure"): "Growth",
    ("Content Engine", "social"): "Image",
    ("Internal Utility", None): "Growth",
    ("Consulting", None): "Network",
}

def map_cluster_to_focus_area(cluster: dict) -> str:
    cid = str(cluster["cluster_id"])

    # Manual override takes priority
    if cid in overrides:
        return overrides[cid]

    asset = cluster.get("asset_vector", "")
    tag = cluster.get("revenue_tag", "")

    # Try exact asset_vector match first
    for (rule_asset, rule_tag), area in FOCUS_AREA_RULES.items():
        if asset == rule_asset:
            if rule_tag is None:
                return area
            if rule_tag in tag:
                return area

    # Fallback
    if "social" in tag:
        return "Image"
    return "Growth"

# === GAP CLASSIFICATION ===

def classify_gap(cluster: dict) -> str:
    lev = cluster.get("normalized_leverage", 0)
    exe = cluster.get("execution_ratio", 0)

    if exe < 0.4 and lev > 7.0:
        return "high_leverage_low_execution"
    if exe > 0.6 and lev > 5.0:
        return "high_leverage_high_execution"
    if exe < 0.4 and lev < 3.0:
        return "low_leverage_low_execution"
    return "balanced"

# === DEEP BLOCK SUGGESTION ===

def suggest_deep_block_mins(cluster: dict) -> int:
    exe = cluster.get("execution_ratio", 0)
    if exe < 0.3:
        return 120
    if exe < 0.5:
        return 90
    return 60

# === LABEL FROM NGRAMS ===

def derive_label(cluster: dict) -> str:
    """Derive a human-readable label from central_messages or top_ngrams."""
    # Try to extract a title from the first central message
    centrals = cluster.get("central_messages", [])
    if centrals:
        first = centrals[0]
        # Look for markdown headers
        for line in first.split("\n"):
            line = line.strip()
            if line.startswith("#"):
                # Strip markdown and emoji
                clean = line.lstrip("#").strip()
                # Remove emoji patterns
                clean = "".join(c for c in clean if ord(c) < 0x1F600 or ord(c) > 0x1FAFF)
                clean = clean.strip(" *_")
                if len(clean) > 5:
                    return clean[:60]

    # Fallback: top 3 ngrams joined
    ngrams = cluster.get("top_ngrams", [])[:3]
    if ngrams:
        return " / ".join(ngrams).title()

    return f"Cluster {cluster['cluster_id']}"

# === DIRECTIVE TEXT ===

def generate_directive(cluster: dict, gap: str, mode: str, focus_area: str, mins: int, open_loops: int, ratio: float) -> str:
    cid = cluster["cluster_id"]
    label = derive_label(cluster)

    if mode == "CLOSURE":
        return f"Close loops before building. {open_loops} open. Ratio: {ratio:.0%}."

    if gap == "high_leverage_low_execution":
        return f"Build leverage in {label} (C{cid}). {mins}m deep block required."
    if gap == "high_leverage_high_execution":
        return f"Scale output from {label} (C{cid}). Ship reusable artifact."

    return f"Maintain focus on {focus_area}. C{cid} is balanced."

# === BUILD PRIORITIES ===

clusters = leverage.get("clusters", [])
clusters_sorted = sorted(clusters, key=lambda c: c.get("normalized_leverage", 0), reverse=True)

# Cognitive state
closure_data = (cognitive or {}).get("closure", {})
open_loops = closure_data.get("open", 0)
closed_loops = closure_data.get("closed", 0)
raw_ratio = closure_data.get("ratio", 0)
# Normalize: if stored as percentage, convert to decimal
closure_ratio = raw_ratio / 100 if raw_ratio > 1 else raw_ratio

# Mode calculation (same as route_today.py)
if raw_ratio < 15:
    mode = "CLOSURE"
    risk = "HIGH"
elif open_loops > 20:
    mode = "CLOSURE"
    risk = "HIGH"
elif open_loops > 10:
    mode = "MAINTENANCE"
    risk = "MEDIUM"
else:
    mode = "BUILD"
    risk = "LOW"

# Process each cluster
top_clusters = []
focus_area_buckets = {
    "Production": [], "Image": [], "Growth": [],
    "Personal": [], "Errands": [], "Network": []
}

for rank, cluster in enumerate(clusters_sorted, 1):
    focus_area = map_cluster_to_focus_area(cluster)
    gap = classify_gap(cluster)
    mins = suggest_deep_block_mins(cluster)
    label = derive_label(cluster)
    directive = generate_directive(cluster, gap, mode, focus_area, mins, open_loops, closure_ratio)

    entry = {
        "rank": rank,
        "cluster_id": cluster["cluster_id"],
        "label": label,
        "normalized_leverage": cluster.get("normalized_leverage", 0),
        "execution_ratio": cluster.get("execution_ratio", 0),
        "reusability_index": cluster.get("reusability_index", 0),
        "market_score": cluster.get("market_score", 0),
        "asset_vector": cluster.get("asset_vector", ""),
        "revenue_tag": cluster.get("revenue_tag", ""),
        "focus_area": focus_area,
        "gap": gap,
        "directive": directive,
        "top_ngrams": cluster.get("top_ngrams", [])[:5],
    }
    top_clusters.append(entry)

    if focus_area in focus_area_buckets:
        focus_area_buckets[focus_area].append(cluster)

# Focus area weights
focus_area_weights = {}
max_weight = 0
for area_name, area_clusters in focus_area_buckets.items():
    raw_weight = sum(c.get("normalized_leverage", 0) for c in area_clusters)
    if raw_weight > max_weight:
        max_weight = raw_weight

for area_name, area_clusters in focus_area_buckets.items():
    raw_weight = sum(c.get("normalized_leverage", 0) for c in area_clusters)
    normalized = round((raw_weight / max_weight) * 10, 1) if max_weight > 0 else 0
    cluster_ids = [c["cluster_id"] for c in area_clusters]
    count = len(area_clusters)
    reason = f"{count} cluster{'s' if count != 1 else ''} mapped here" if count > 0 else "No direct cluster alignment"
    focus_area_weights[area_name] = {
        "weight": normalized,
        "clusters": cluster_ids,
        "reason": reason,
    }

# Daily directive
top = top_clusters[0] if top_clusters else None
primary_focus = top["focus_area"] if top else "Production"
primary_cluster = top["cluster_id"] if top else None
primary_action = top["directive"] if top else "Run atlas pipeline to generate leverage data."
suggested_mins = suggest_deep_block_mins(clusters_sorted[0]) if clusters_sorted else 60

# Mode escalation: if top cluster gap is high_leverage_low_execution AND mode is not BUILD
mode_escalation = None
if top and top["gap"] == "high_leverage_low_execution" and mode != "BUILD":
    mode_escalation = f"Top cluster C{top['cluster_id']} has high leverage but low execution. Consider closing loops to unlock BUILD mode."

# Stretch goal
stretch_goal = None
if top:
    if top["gap"] == "high_leverage_low_execution":
        stretch_goal = f"Ship one reusable artifact from C{top['cluster_id']}"
    elif top["gap"] == "high_leverage_high_execution":
        stretch_goal = f"Package C{top['cluster_id']} output for distribution"
    else:
        stretch_goal = f"Make progress on {primary_focus} focus area"

# === OUTPUT ===

output = {
    "generated": datetime.now().isoformat(),
    "mode": mode,
    "risk": risk,
    "open_loops": open_loops,
    "closure_ratio": closure_ratio,
    "top_clusters": top_clusters,
    "focus_area_weights": focus_area_weights,
    "daily_directive": {
        "primary_focus": primary_focus,
        "primary_cluster": primary_cluster,
        "primary_action": primary_action,
        "suggested_deep_block_mins": suggested_mins,
        "stretch_goal": stretch_goal,
        "mode_escalation": mode_escalation,
    },
}

# Write canonical
out_path = BASE / "strategic_priorities.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"[OK] {out_path.name} ({len(top_clusters)} clusters, primary: {primary_focus})")

# Copy to CycleBoard brain
CYCLEBOARD_BRAIN.mkdir(parents=True, exist_ok=True)
shutil.copy(out_path, CYCLEBOARD_BRAIN / "strategic_priorities.json")
print(f"[OK] Copied to cycleboard/brain/")

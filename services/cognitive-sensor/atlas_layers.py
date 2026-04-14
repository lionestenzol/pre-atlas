"""
atlas_layers.py -- Build layer data and cluster summary for the Cognitive Atlas.

Pure functions with no I/O. Builds the 4 toggle-layer datasets (cluster, role,
time, convo) and the per-cluster summary table used in the dashboard sidebar.
"""
from datetime import datetime
from collections import defaultdict


def build_layers(data, labels):
    """
    Build layer data for atlas visualization layers.

    Args:
        data: dict from load_message_data() with keys: convo_ids, roles, dates
        labels: np.ndarray of cluster labels from HDBSCAN

    Returns:
        dict with keys:
            cluster: list[int] -- cluster label per message
            role: list[str] -- role per message
            time: list[float] -- normalized timestamp [0.0, 1.0] per message
            convo: list[int] -- conversation color index per message
    """
    n = len(data["convo_ids"])

    # Time layer: normalize dates to 0-1
    parsed_dates = []
    for d in data["dates"]:
        try:
            parsed_dates.append(datetime.strptime(d, "%Y-%m-%d").timestamp())
        except (ValueError, TypeError):
            parsed_dates.append(None)

    valid_ts = [t for t in parsed_dates if t is not None]
    if valid_ts:
        min_ts, max_ts = min(valid_ts), max(valid_ts)
        ts_range = max_ts - min_ts if max_ts > min_ts else 1
        time_norm = [
            round((t - min_ts) / ts_range, 4) if t is not None else 0.5
            for t in parsed_dates
        ]
    else:
        time_norm = [0.5] * n

    # Conversation layer: hash convo_id to color index
    convo_color = [int(cid) % 50 for cid in data["convo_ids"]]

    return {
        "cluster": labels.tolist(),
        "role": data["roles"],
        "time": time_norm,
        "convo": convo_color,
    }


def build_cluster_summary(data, labels):
    """
    Build per-cluster summary statistics.

    Args:
        data: dict from load_message_data() with keys: roles, titles, dates
        labels: np.ndarray of cluster labels

    Returns:
        list[dict] sorted by descending count. Each dict has:
            id: int -- cluster ID
            count: int -- message count
            dominant_role: str -- most common role
            user_pct: float -- percentage of user messages
            date_range: str -- "YYYY-MM-DD to YYYY-MM-DD" or ""
            top_titles: list[dict] -- top 3 conversation titles with counts
    """
    clusters = defaultdict(
        lambda: {"count": 0, "roles": defaultdict(int), "titles": defaultdict(int), "dates": []}
    )

    for i, label in enumerate(labels):
        if label == -1:
            continue
        cl = clusters[int(label)]
        cl["count"] += 1
        cl["roles"][data["roles"][i]] += 1
        cl["titles"][data["titles"][i]] += 1
        if data["dates"][i]:
            cl["dates"].append(data["dates"][i])

    summary = []
    for cid in sorted(clusters.keys()):
        cl = clusters[cid]
        top_titles = sorted(cl["titles"].items(), key=lambda x: -x[1])[:3]
        dominant_role = max(cl["roles"].items(), key=lambda x: x[1])[0] if cl["roles"] else "unknown"
        user_pct = round(100 * cl["roles"].get("user", 0) / cl["count"], 1) if cl["count"] > 0 else 0
        date_range = ""
        if cl["dates"]:
            cl["dates"].sort()
            date_range = f"{cl['dates'][0]} to {cl['dates'][-1]}"
        summary.append({
            "id": cid,
            "count": cl["count"],
            "dominant_role": dominant_role,
            "user_pct": user_pct,
            "date_range": date_range,
            "top_titles": [{"title": t[:50], "msgs": c} for t, c in top_titles],
        })

    return sorted(summary, key=lambda x: -x["count"])

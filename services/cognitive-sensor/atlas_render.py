"""
atlas_render.py -- Assemble JSON payload and generate cognitive_atlas.html.

Loads leverage data, builds the complete payload from pipeline outputs,
reads the HTML template, and writes the final self-contained HTML file.
"""
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from atlas_graph import build_graph_data

BASE = Path(__file__).parent.resolve()
TEMPLATE_FILE = BASE / "atlas_template.html"
DEFAULT_OUT_FILE = BASE / "cognitive_atlas.html"
DEFAULT_LEVERAGE_FILE = BASE / "leverage_map.json"


def load_leverage_data(leverage_path=None):
    """
    Load and structure leverage_map.json for embedding in the HTML payload.

    Args:
        leverage_path: Path to leverage_map.json. Defaults to BASE/leverage_map.json.

    Returns:
        dict with structured leverage data, or None if file not found / invalid.
    """
    path = leverage_path or DEFAULT_LEVERAGE_FILE
    if not path.exists():
        print(f"  leverage_map.json not found -- leverage layer disabled")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            leverage_raw = json.load(f)

        cluster_lookup = {}
        for cl in leverage_raw.get("clusters", []):
            cid = cl["cluster_id"]
            cluster_lookup[str(cid)] = {
                "normalized_leverage": cl["normalized_leverage"],
                "raw_composite": cl["raw_composite"],
                "tightness": cl["tightness"],
                "execution_ratio": cl["execution_ratio"],
                "reusability_index": cl["reusability_index"],
                "dependency_load": cl["dependency_load"],
                "fragmentation_ratio": cl["fragmentation_ratio"],
                "revenue_tag": cl["revenue_tag"],
                "market_score": cl["market_score"],
                "asset_vector": cl["asset_vector"],
                "top_ngrams": cl["top_ngrams"][:10],
                "central_messages": [m[:200] for m in cl.get("central_messages", [])[:3]],
                "size": cl["size"],
                "conversations": cl["conversations"],
                "user_pct": cl["user_pct"],
            }

        leverage_data = {
            "generated": leverage_raw.get("generated", ""),
            "clusters_analyzed": leverage_raw.get("clusters_analyzed", 0),
            "clusters": [
                {
                    "cluster_id": cl["cluster_id"],
                    "size": cl["size"],
                    "conversations": cl["conversations"],
                    "user_pct": cl["user_pct"],
                    "normalized_leverage": cl["normalized_leverage"],
                    "raw_composite": cl["raw_composite"],
                    "execution_ratio": cl["execution_ratio"],
                    "reusability_index": cl["reusability_index"],
                    "asset_vector": cl["asset_vector"],
                    "revenue_tag": cl["revenue_tag"],
                    "market_score": cl["market_score"],
                }
                for cl in leverage_raw.get("clusters", [])
            ],
            "cluster_lookup": cluster_lookup,
        }
        print(f"  Leverage data loaded: {len(cluster_lookup)} clusters")
        return leverage_data

    except Exception as e:
        print(f"  WARNING: Could not load leverage_map.json: {e}")
        return None


def load_template(template_path=None):
    """
    Load the HTML template from disk.

    Args:
        template_path: Path to atlas_template.html. Defaults to TEMPLATE_FILE.

    Returns:
        str -- the template content
    """
    path = template_path or TEMPLATE_FILE
    return path.read_text(encoding="utf-8")


def build_payload(data, umap_coords, labels, layers, cluster_summary,
                  matrix, leverage_data=None, graph_kwargs=None):
    """
    Assemble the complete JSON payload for the atlas HTML.

    Args:
        data: dict from load_message_data()
        umap_coords: np.ndarray (N, 2)
        labels: np.ndarray of cluster labels
        layers: dict from build_layers()
        cluster_summary: list from build_cluster_summary()
        matrix: np.ndarray (N, D) embeddings
        leverage_data: dict or None (pre-loaded leverage data)
        graph_kwargs: optional dict of graph params (overlap_min, sim_min, etc.)

    Returns:
        dict -- the complete payload ready for JSON serialization
    """
    n = len(data["convo_ids"])

    # Build lookup tables (title + date per convo_id, not per message)
    title_lookup = {}
    date_lookup = {}
    for i in range(n):
        cid = data["convo_ids"][i]
        if cid not in title_lookup:
            title_lookup[cid] = data["titles"][i]
            date_lookup[cid] = data["dates"][i]

    # Compute stats
    n_clusters = len(set(labels.tolist())) - (1 if -1 in labels else 0)
    noise_count = int(np.sum(labels == -1))
    noise_pct = round(100 * noise_count / n, 1)
    role_counts = defaultdict(int)
    for r in data["roles"]:
        role_counts[r] += 1
    unique_convos = len(set(data["convo_ids"]))

    # Build graph data
    print("  Building graph data...")
    gkw = graph_kwargs or {}
    graph_data = build_graph_data(data, labels, umap_coords, matrix, leverage_data, **gkw)

    # Load prediction results if available
    prediction_data = _load_prediction_data()

    payload = {
        "stats": {
            "total": n,
            "clusters": n_clusters,
            "noise": noise_count,
            "noise_pct": noise_pct,
            "user": role_counts.get("user", 0),
            "assistant": role_counts.get("assistant", 0),
            "tool": role_counts.get("tool", 0),
            "conversations": unique_convos,
        },
        "x": [round(float(v), 4) for v in umap_coords[:, 0]],
        "y": [round(float(v), 4) for v in umap_coords[:, 1]],
        "convo_ids": data["convo_ids"],
        "roles": data["roles"],
        "msg_indices": data["msg_indices"],
        "word_counts": data["word_counts"],
        "titleLookup": title_lookup,
        "dateLookup": date_lookup,
        "layers": layers,
        "cluster_summary": cluster_summary,
        "leverage": leverage_data,
        "graph": graph_data,
        "predictions": prediction_data,
    }

    return payload


def _load_prediction_data():
    """Load prediction_results.json for Atlas payload. Returns None if unavailable."""
    pred_path = BASE / "prediction_results.json"
    if not pred_path.exists():
        return None
    try:
        data = json.loads(pred_path.read_text(encoding="utf-8"))
        if data.get("status") != "ok":
            return None
        return {
            "status": "ok",
            "loop_predictions": data.get("loop_predictions", []),
            "active_patterns": data.get("active_patterns", []),
            "top_actions": data.get("top_actions", []),
            "mode_forecast": data.get("mode_forecast"),
            "exit_path": data.get("exit_path"),
        }
    except Exception:
        return None


def build_html(data, umap_coords, labels, layers, cluster_summary, matrix,
               *, out_file=None, template_path=None, leverage_path=None,
               graph_kwargs=None):
    """
    Generate cognitive_atlas.html.

    Args:
        data: dict from load_message_data()
        umap_coords: np.ndarray (N, 2)
        labels: np.ndarray of cluster labels
        layers: dict from build_layers()
        cluster_summary: list from build_cluster_summary()
        matrix: np.ndarray (N, D) embeddings
        out_file: Path for output HTML (default: cognitive_atlas.html)
        template_path: Path for template (default: atlas_template.html)
        leverage_path: Path for leverage data (default: leverage_map.json)
        graph_kwargs: optional dict of graph construction params
    """
    out = out_file or DEFAULT_OUT_FILE

    leverage_data = load_leverage_data(leverage_path)
    payload = build_payload(
        data, umap_coords, labels, layers, cluster_summary, matrix,
        leverage_data=leverage_data, graph_kwargs=graph_kwargs,
    )

    payload_json = json.dumps(payload, ensure_ascii=False)
    n = len(data["convo_ids"])
    n_clusters = len(set(labels.tolist())) - (1 if -1 in labels else 0)
    subtitle = (
        f"{n:,} messages | UMAP + HDBSCAN | {n_clusters} clusters | "
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    template = load_template(template_path)
    page = template.replace("__DATA_PAYLOAD__", payload_json)
    page = page.replace("__SUBTITLE__", subtitle)

    Path(out).write_text(page, encoding="utf-8")
    size_mb = len(payload_json) / 1024 / 1024
    print(f"  Output: {out} ({size_mb:.1f} MB payload)")

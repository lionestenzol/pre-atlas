"""atlas_query.py — Headless CLI access to the Cognitive Atlas.

Every piece of data and every control that the cognitive_atlas.html page
exposes is reachable here from the shell, with JSON output by default
(so AI agents can pipe it) and --text for human-readable tables.

Usage:
    python atlas_query.py stats
    python atlas_query.py clusters [--limit N] [--sort size|user_pct|id]
    python atlas_query.py cluster <id>
    python atlas_query.py leverage [--top N] [--vector <asset_vector>]
    python atlas_query.py vectors
    python atlas_query.py search <text> [--limit N]
    python atlas_query.py near <cluster_id> [--top N]
    python atlas_query.py convo <convo_id>
    python atlas_query.py layers              # describe available layers
    python atlas_query.py inspect <cluster_id>  # full inspector (== UI panel)

Global flags:
    --text          Pretty text output (default: JSON to stdout)
    --pretty        Pretty-print JSON with indent
    --root DIR      Override data directory (default: this file's dir)
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

BASE = Path(__file__).parent.resolve()


@dataclass(frozen=True)
class AtlasData:
    clusters_path: Path
    leverage_path: Path
    state_path: Path
    clusters: dict[str, Any]
    leverage: dict[str, Any]
    state: dict[str, Any]
    graph: dict[str, Any]
    points_index: dict[str, Any]


def load(root: Path = BASE) -> AtlasData:
    def _read(p: Path) -> dict[str, Any]:
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    return AtlasData(
        clusters_path=root / "atlas_clusters.json",
        leverage_path=root / "leverage_map.json",
        state_path=root / "atlas_state.json",
        clusters=_read(root / "atlas_clusters.json"),
        leverage=_read(root / "leverage_map.json"),
        state=_read(root / "atlas_state.json"),
        graph=_read(root / "atlas_graph.json"),
        points_index=_read(root / "atlas_points_index.json"),
    )


def _db(root: Path = BASE) -> sqlite3.Connection | None:
    """Open results.db for richer joins (titles + topics + decisions). None if missing."""
    p = root / "results.db"
    if not p.exists():
        return None
    return sqlite3.connect(str(p))


def _convos_in_cluster(data: AtlasData, cluster_id: int) -> list[str]:
    assignments = data.clusters.get("convo_cluster_assignments", {})
    return [c for c, l in assignments.items() if int(l) == cluster_id]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _by_cluster_id(items: list[dict[str, Any]], key: str = "id") -> dict[int, dict[str, Any]]:
    return {int(it[key]): it for it in items}


def _merge_cluster(cs: dict[str, Any] | None, lv: dict[str, Any] | None) -> dict[str, Any]:
    """Merge cluster_summary entry and leverage entry into one record."""
    out: dict[str, Any] = {}
    if cs:
        out.update(
            id=int(cs["id"]),
            size=cs.get("count"),
            dominant_role=cs.get("dominant_role"),
            user_pct=cs.get("user_pct"),
            date_range=cs.get("date_range"),
            top_titles=cs.get("top_titles", []),
        )
    if lv:
        out.update(
            id=out.get("id", int(lv["cluster_id"])),
            size=out.get("size", lv.get("size")),
            user_pct=out.get("user_pct", lv.get("user_pct")),
            conversations=lv.get("conversations"),
            tightness=lv.get("tightness"),
            execution_ratio=lv.get("execution_ratio"),
            reusability_index=lv.get("reusability_index"),
            dependency_load=lv.get("dependency_load"),
            revenue_tag=lv.get("revenue_tag"),
            market_score=lv.get("market_score"),
            raw_composite=lv.get("raw_composite"),
            normalized_leverage=lv.get("normalized_leverage"),
            asset_vector=lv.get("asset_vector"),
            top_ngrams=lv.get("top_ngrams", []),
            central_messages=lv.get("central_messages", []),
        )
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_stats(data: AtlasData, _args: argparse.Namespace) -> dict[str, Any]:
    """Top-of-page stats bar."""
    c = data.clusters
    lev = data.leverage
    return {
        "generated_at": c.get("generated_at"),
        "total_messages": c.get("total_messages"),
        "total_conversations": c.get("total_conversations"),
        "cluster_count": c.get("cluster_count"),
        "noise_messages": c.get("total_messages", 0) - sum(
            cs.get("count", 0) for cs in c.get("cluster_summary", [])
        ),
        "leverage_clusters_analyzed": lev.get("clusters_analyzed"),
        "scoring_strategy": lev.get("scoring"),
    }


def cmd_clusters(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """List all clusters, sortable + limitable."""
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    all_ids = sorted(set(cs_by_id) | set(lv_by_id))
    rows = [_merge_cluster(cs_by_id.get(i), lv_by_id.get(i)) for i in all_ids]

    sort_key = args.sort
    reverse = sort_key != "id"

    def _key(r: dict[str, Any]) -> Any:
        v = r.get(sort_key)
        return v if v is not None else (-1 if reverse else math.inf)

    rows.sort(key=_key, reverse=reverse)
    if args.limit:
        rows = rows[: args.limit]
    return rows


def cmd_cluster(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Full record on one cluster (== Cluster Inspector card)."""
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    cid = int(args.cluster_id)
    record = _merge_cluster(cs_by_id.get(cid), lv_by_id.get(cid))
    if not record:
        raise SystemExit(f"cluster {cid} not found")
    return record


cmd_inspect = cmd_cluster  # alias — same data UI shows in Inspector


def cmd_leverage(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Leverage Ranking table from the right sidebar."""
    rows = list(data.leverage.get("clusters", []))
    if args.vector:
        rows = [r for r in rows if r.get("asset_vector") == args.vector]
    # Sort by normalized_leverage desc (the rendered order), fallback to raw_composite
    rows.sort(key=lambda r: r.get("normalized_leverage", r.get("raw_composite", 0)), reverse=True)
    if args.top:
        rows = rows[: args.top]
    return rows


def cmd_vectors(data: AtlasData, _args: argparse.Namespace) -> dict[str, Any]:
    """Group clusters by asset_vector — what the Asset Vectors card shows."""
    by_vec: dict[str, list[int]] = {}
    for c in data.leverage.get("clusters", []):
        v = c.get("asset_vector") or "Unscored"
        by_vec.setdefault(v, []).append(int(c["cluster_id"]))
    return {
        "groups": [
            {
                "asset_vector": v,
                "count": len(ids),
                "cluster_ids": sorted(ids),
                "avg_leverage": round(
                    sum(
                        c.get("normalized_leverage", 0)
                        for c in data.leverage.get("clusters", [])
                        if c.get("asset_vector") == v
                    )
                    / max(len(ids), 1),
                    2,
                ),
            }
            for v, ids in sorted(by_vec.items(), key=lambda kv: -len(kv[1]))
        ]
    }


def cmd_search(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Search clusters whose titles or n-grams mention <query>."""
    q = args.query.lower().strip()
    if not q:
        return []
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    hits: list[tuple[int, list[str], dict[str, Any]]] = []
    for cid in set(cs_by_id) | set(lv_by_id):
        cs = cs_by_id.get(cid, {})
        lv = lv_by_id.get(cid, {})
        matches: list[str] = []
        for t in cs.get("top_titles", []) or []:
            if q in str(t.get("title") or "").lower():
                matches.append(f"title: {t.get('title')}")
        for ng in lv.get("top_ngrams", []) or []:
            if q in str(ng).lower():
                matches.append(f"ngram: {ng}")
        rtag = str(lv.get("revenue_tag") or "")
        if q in rtag.lower():
            matches.append(f"revenue_tag: {rtag}")
        vec = str(lv.get("asset_vector") or "")
        if q in vec.lower():
            matches.append(f"asset_vector: {vec}")
        if matches:
            hits.append((cid, matches, _merge_cluster(cs, lv)))

    hits.sort(key=lambda x: -(x[2].get("normalized_leverage") or x[2].get("size") or 0))
    if args.limit:
        hits = hits[: args.limit]
    return [
        {"cluster_id": cid, "matched_on": m, "cluster": rec}
        for cid, m, rec in hits
    ]


def cmd_near(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Cosine-nearest clusters to <cluster_id> by centroid."""
    centroids: dict[str, list[float]] = data.clusters.get("cluster_centroids", {})
    target = centroids.get(str(args.cluster_id))
    if not target:
        raise SystemExit(f"no centroid for cluster {args.cluster_id}")
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    sims = []
    for other_id_str, vec in centroids.items():
        other_id = int(other_id_str)
        if other_id == int(args.cluster_id):
            continue
        sim = _cosine(target, vec)
        rec = _merge_cluster(cs_by_id.get(other_id), lv_by_id.get(other_id))
        rec["similarity"] = round(sim, 4)
        sims.append(rec)
    sims.sort(key=lambda r: -(r.get("similarity") or 0))
    return sims[: args.top] if args.top else sims


def cmd_convo(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Show the cluster a conversation belongs to + its cluster siblings."""
    assignments = data.clusters.get("convo_cluster_assignments", {})
    convo_id = args.convo_id
    if convo_id not in assignments:
        raise SystemExit(f"conversation {convo_id} not found in atlas_clusters.json")
    cluster_id = int(assignments[convo_id])
    siblings = [c for c, l in assignments.items() if int(l) == cluster_id and c != convo_id]
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    return {
        "convo_id": convo_id,
        "cluster_id": cluster_id,
        "cluster": _merge_cluster(cs_by_id.get(cluster_id), lv_by_id.get(cluster_id)),
        "sibling_count": len(siblings),
        "sibling_sample": siblings[:20],
    }


def cmd_messages(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Show every conversation in a cluster with title, date, msg count, top topic words.

    This is the 'what is this cluster actually MADE of' command — far richer than
    the 3-title sample in the cluster_summary.
    """
    cid = int(args.cluster_id)
    convos = _convos_in_cluster(data, cid)
    if not convos:
        raise SystemExit(f"no conversations in cluster {cid}")

    db = _db(args.root)
    rows: list[dict[str, Any]] = []
    topic_totals: Counter = Counter()
    if db is None:
        for c in convos[: args.limit or 999999]:
            rows.append({"convo_id": c})
    else:
        placeholder = ",".join("?" * len(convos))
        # Titles
        titles = {r[0]: r[1] for r in db.execute(
            f"SELECT convo_id, title FROM convo_titles WHERE convo_id IN ({placeholder})", convos
        )}
        # Dates
        dates = {r[0]: r[1] for r in db.execute(
            f"SELECT convo_id, date FROM convo_time WHERE convo_id IN ({placeholder})", convos
        )}
        # Message counts per convo
        msgs = {r[0]: r[1] for r in db.execute(
            f"SELECT convo_id, COUNT(*) FROM messages WHERE convo_id IN ({placeholder}) GROUP BY convo_id",
            convos,
        )}
        # Topic words per convo
        topics_by_convo: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for cv, tpc, w in db.execute(
            f"SELECT convo_id, topic, weight FROM topics WHERE convo_id IN ({placeholder})", convos
        ):
            topics_by_convo[cv].append((tpc, w))
            topic_totals[tpc] += w
        # Decisions
        decisions = {r[0]: r[1] for r in db.execute(
            f"SELECT convo_id, decision FROM loop_decisions WHERE convo_id IN ({placeholder})", convos
        )}
        db.close()

        for cv in convos:
            cv_topics = sorted(topics_by_convo.get(cv, []), key=lambda t: -t[1])[:5]
            rows.append({
                "convo_id": cv,
                "title": titles.get(cv, "(no title)"),
                "date": dates.get(cv),
                "msg_count": msgs.get(cv, 0),
                "decision": decisions.get(cv),
                "top_topics": [t for t, _ in cv_topics],
            })

        rows.sort(key=lambda r: -(r.get("msg_count") or 0))
        if args.limit:
            rows = rows[: args.limit]

    return {
        "cluster_id": cid,
        "total_convos": len(convos),
        "topic_distribution": [{"word": w, "weight": n} for w, n in topic_totals.most_common(20)],
        "conversations": rows,
    }


def cmd_themes(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Topic words that span multiple clusters — the cross-cluster thematic threads.

    Answers: 'which themes recur across my whole atlas, not just inside one cluster?'
    """
    db = _db(args.root)
    if db is None:
        raise SystemExit("results.db not found — themes needs the topics table")
    assignments = data.clusters.get("convo_cluster_assignments", {})
    # Group convos by cluster
    by_cluster: dict[int, list[str]] = defaultdict(list)
    for cv, cl in assignments.items():
        by_cluster[int(cl)].append(cv)

    # For each topic word, count distinct clusters it appears in + total weight
    topic_clusters: dict[str, set[int]] = defaultdict(set)
    topic_weight: Counter = Counter()
    for convo_id, topic, weight in db.execute("SELECT convo_id, topic, weight FROM topics"):
        cl = assignments.get(convo_id)
        if cl is None:
            continue
        topic_clusters[topic].add(int(cl))
        topic_weight[topic] += weight
    db.close()

    spanning = [
        {
            "topic": t,
            "cluster_count": len(cs),
            "total_weight": topic_weight[t],
            "cluster_ids": sorted(cs),
        }
        for t, cs in topic_clusters.items()
        if len(cs) >= (args.min_clusters or 5)
    ]
    spanning.sort(key=lambda x: (-x["cluster_count"], -x["total_weight"]))
    return spanning[: args.top] if args.top else spanning[:50]


def cmd_region(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Spatial-neighborhood view: clusters around <cluster_id> with their relative position.

    Uses 2D centroids derived from the cluster_centroids (semantic) AND the existing
    `near` cosine ranking. This is the closest CLI analogue to 'look at the map and
    see what's around this cluster'.
    """
    cid = int(args.cluster_id)
    centroids: dict[str, list[float]] = data.clusters.get("cluster_centroids", {})
    target = centroids.get(str(cid))
    if not target:
        raise SystemExit(f"no centroid for cluster {cid}")
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")

    sims = []
    for other_id_str, vec in centroids.items():
        other_id = int(other_id_str)
        if other_id == cid:
            continue
        sims.append((other_id, _cosine(target, vec)))
    sims.sort(key=lambda x: -x[1])

    radius = args.radius or 0.6
    near = [(oid, s) for oid, s in sims if s >= radius][: args.limit or 20]

    return {
        "cluster_id": cid,
        "self": _merge_cluster(cs_by_id.get(cid), lv_by_id.get(cid)),
        "radius_cosine": radius,
        "neighbors_in_radius": len(near),
        "neighborhood": [
            {
                "cluster_id": oid,
                "similarity": round(s, 4),
                "size": (cs_by_id.get(oid) or {}).get("count"),
                "asset_vector": (lv_by_id.get(oid) or {}).get("asset_vector"),
                "leverage": (lv_by_id.get(oid) or {}).get("normalized_leverage"),
                "top_title": ((cs_by_id.get(oid) or {}).get("top_titles") or [{}])[0].get("title"),
            }
            for oid, s in near
        ],
    }


def cmd_graph(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Whole sigma graph topology — every cluster as a node, every overlap as an edge."""
    g = data.graph
    if not g:
        raise SystemExit("atlas_graph.json missing — run `python extract_atlas_data.py` first")
    nodes = g.get("nodes", [])
    edges = g.get("edges", [])
    if args.summary:
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "leveraged_nodes": sum(1 for n in nodes if n.get("has_leverage")),
            "edge_types": dict(Counter(e.get("type", "?") for e in edges)),
            "weight_range": [
                min((e.get("weight", 0) for e in edges), default=0),
                max((e.get("weight", 0) for e in edges), default=0),
            ],
        }
    return {"nodes": nodes, "edges": edges}


def cmd_graph_node(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """One cluster's node in the graph + every edge that touches it."""
    g = data.graph
    if not g:
        raise SystemExit("atlas_graph.json missing — run `python extract_atlas_data.py` first")
    cid = f"C{args.cluster_id}"
    node = next((n for n in g.get("nodes", []) if n.get("id") == cid), None)
    if node is None:
        raise SystemExit(f"node {cid} not in graph")
    incident = [e for e in g.get("edges", []) if e.get("source") == cid or e.get("target") == cid]
    # Resolve "other end" for each edge
    edges_out = [
        {
            "neighbor": e["target"] if e["source"] == cid else e["source"],
            "weight": e.get("weight"),
            "type": e.get("type"),
        }
        for e in incident
    ]
    edges_out.sort(key=lambda e: -(e["weight"] or 0))
    return {"node": node, "degree": len(edges_out), "edges": edges_out}


def cmd_bridges(data: AtlasData, args: argparse.Namespace) -> list[dict[str, Any]]:
    """Clusters with the highest graph degree — the connectors of the atlas."""
    g = data.graph
    if not g:
        raise SystemExit("atlas_graph.json missing")
    deg: Counter = Counter()
    weight_sum: dict[str, float] = defaultdict(float)
    for e in g.get("edges", []):
        deg[e["source"]] += 1; deg[e["target"]] += 1
        weight_sum[e["source"]] += e.get("weight", 0) or 0
        weight_sum[e["target"]] += e.get("weight", 0) or 0
    nodes_by_id = {n["id"]: n for n in g.get("nodes", [])}
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    lv_by_id = _by_cluster_id(data.leverage.get("clusters", []), key="cluster_id")
    rows = []
    for nid, d in deg.most_common():
        cid = int(nid[1:]) if nid.startswith("C") else int(nid)
        rows.append({
            "cluster_id": cid,
            "degree": d,
            "total_edge_weight": round(weight_sum[nid], 3),
            "size": (cs_by_id.get(cid) or {}).get("count"),
            "asset_vector": (lv_by_id.get(cid) or {}).get("asset_vector"),
            "leverage": (lv_by_id.get(cid) or {}).get("normalized_leverage"),
            "top_title": ((cs_by_id.get(cid) or {}).get("top_titles") or [{}])[0].get("title"),
        })
    return rows[: args.top] if args.top else rows


def cmd_path(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """BFS shortest path in the cluster graph from cluster A to cluster B."""
    g = data.graph
    if not g:
        raise SystemExit("atlas_graph.json missing")
    adj: dict[str, list[str]] = defaultdict(list)
    weights: dict[tuple[str, str], float] = {}
    for e in g.get("edges", []):
        a, b = e["source"], e["target"]
        adj[a].append(b); adj[b].append(a)
        weights[(a, b)] = weights[(b, a)] = e.get("weight", 0) or 0

    start, end = f"C{args.from_id}", f"C{args.to_id}"
    if start not in adj and start != end:
        raise SystemExit(f"node {start} has no edges (isolated)")
    if end not in adj and start != end:
        raise SystemExit(f"node {end} has no edges (isolated)")

    # BFS
    seen = {start}
    queue: list[tuple[str, list[str]]] = [(start, [start])]
    while queue:
        node, path = queue.pop(0)
        if node == end:
            return {
                "from": start, "to": end, "hops": len(path) - 1,
                "path": path,
                "edges": [
                    {"from": path[i], "to": path[i+1], "weight": weights.get((path[i], path[i+1]))}
                    for i in range(len(path) - 1)
                ],
            }
        for nb in adj[node]:
            if nb in seen:
                continue
            seen.add(nb)
            queue.append((nb, path + [nb]))
    return {"from": start, "to": end, "path": None, "reason": "no graph path (clusters in different components)"}


def cmd_evolution(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Time evolution of a cluster — when did its messages happen?"""
    idx = data.points_index.get(str(args.cluster_id))
    if not idx:
        raise SystemExit(f"cluster {args.cluster_id} not in atlas_points_index.json")
    bins = idx.get("time_histogram_10bin", [])
    total = sum(bins) or 1
    return {
        "cluster_id": int(args.cluster_id),
        "n_points": idx["n_points"],
        "time_histogram_10bin": bins,
        "time_histogram_pct": [round(100 * b / total, 1) for b in bins],
        "note": "Bins are normalized time 0..1 (oldest..newest across the whole atlas)",
    }


def cmd_role_breakdown(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Role split (user/assistant/tool) inside one cluster — from the per-message data."""
    idx = data.points_index.get(str(args.cluster_id))
    if not idx:
        raise SystemExit(f"cluster {args.cluster_id} not in atlas_points_index.json")
    rb = idx["role_breakdown"]
    total = sum(rb.values()) or 1
    return {
        "cluster_id": int(args.cluster_id),
        "n_points": idx["n_points"],
        "counts": rb,
        "pct": {k: round(100 * v / total, 1) for k, v in rb.items()},
    }


def cmd_density(data: AtlasData, args: argparse.Namespace) -> Any:
    """Spatial density / bounding box info per cluster in 2D UMAP space."""
    if args.cluster_id is not None:
        idx = data.points_index.get(str(args.cluster_id))
        if not idx:
            raise SystemExit(f"cluster {args.cluster_id} not in atlas_points_index.json")
        return {"cluster_id": int(args.cluster_id), **idx}
    # Else rank ALL clusters by metric
    cs_by_id = _by_cluster_id(data.clusters.get("cluster_summary", []), key="id")
    rows = []
    for cid_str, agg in data.points_index.items():
        cid = int(cid_str)
        rows.append({
            "cluster_id": cid,
            "n_points": agg["n_points"],
            "density": agg["density"],
            "centroid_2d": agg["centroid_2d"],
            "top_title": ((cs_by_id.get(cid) or {}).get("top_titles") or [{}])[0].get("title"),
        })
    key = args.sort or "density"
    rows.sort(key=lambda r: -(r.get(key) or 0))
    return rows[: args.top] if args.top else rows[:30]


def cmd_text(data: AtlasData, args: argparse.Namespace) -> dict[str, Any]:
    """Pull the actual message text of a conversation from the ChatGPT export bundle.

    Maps numeric convo_id (atlas) -> title+date (results.db) -> exported JSON file
    (chatgpt_index.json) -> mapping graph walk -> ordered messages.

    Requires: chatgpt_index.json (run `python index_chatgpt_exports.py` once).
    """
    # 1. Find title + date for numeric convo_id
    db = _db(args.root)
    if db is None:
        raise SystemExit("results.db missing — needed for title lookup")
    row = db.execute("SELECT t.title, c.date FROM convo_titles t LEFT JOIN convo_time c USING (convo_id) WHERE t.convo_id=?", (str(args.convo_id),)).fetchone()
    db.close()
    if not row:
        raise SystemExit(f"convo_id {args.convo_id} not in results.db")
    title, date = row

    # 2. Find conversation in chatgpt_index
    idx_path = args.root / "chatgpt_index.json"
    if not idx_path.exists():
        raise SystemExit(f"{idx_path.name} missing — run `python index_chatgpt_exports.py` first")
    with open(idx_path, encoding="utf-8") as f:
        index = json.load(f)

    matches = [e for e in index if (e.get("title") or "").strip() == (title or "").strip()]
    if date:
        # narrow by date if multiple titles collide
        date_str = str(date)[:10]
        narrowed = [e for e in matches if (e.get("date") or "").startswith(date_str)]
        if narrowed:
            matches = narrowed
    if not matches:
        raise SystemExit(f"no export file matches title {title!r} (date {date})")

    target = matches[0]

    # 3. Load the file + entry
    export_dir = args.export_dir or Path(r"C:\Users\bruke\OneDrive\Desktop\claude-mining\source-chatgpt")
    file_path = export_dir / target["file"]
    if not file_path.exists():
        raise SystemExit(f"export file missing: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        arr = json.load(f)
    entry = arr[target["position"]]

    # 4. Walk the mapping graph in chronological order
    mapping = entry.get("mapping", {})
    # ChatGPT's mapping is a tree: each node has children. Root has parent=None.
    # current_node leads from leaf back. Order msgs by create_time after extracting all.
    messages: list[dict] = []
    for node_id, node in mapping.items():
        msg = node.get("message")
        if not msg:
            continue
        author = (msg.get("author") or {}).get("role")
        if author == "system":
            continue
        content = msg.get("content") or {}
        ctype = content.get("content_type", "text")
        parts = content.get("parts") or []
        # Concatenate text parts (skip non-string parts like images)
        text = "\n".join(p for p in parts if isinstance(p, str)).strip()
        if not text:
            continue
        messages.append({
            "role": author,
            "create_time": msg.get("create_time") or 0,
            "content_type": ctype,
            "text": text[: args.max_chars] if args.max_chars else text,
            "truncated": bool(args.max_chars and len(text) > args.max_chars),
        })
    messages.sort(key=lambda m: m["create_time"] or 0)
    if args.limit:
        messages = messages[: args.limit]

    return {
        "convo_id": args.convo_id,
        "title": title,
        "date": str(date) if date else None,
        "uuid": target.get("uuid"),
        "source_file": target["file"],
        "total_messages": len(messages),
        "messages": messages,
    }


def cmd_layers(_data: AtlasData, _args: argparse.Namespace) -> dict[str, Any]:
    """Describe the layer toggle (Cluster / Role / Time / Conversation / Leverage)."""
    return {
        "layers": [
            {"name": "cluster", "description": "HDBSCAN cluster id per message"},
            {"name": "role", "description": "user / assistant / tool"},
            {"name": "time", "description": "normalized timestamp 0..1 (oldest -> newest)"},
            {"name": "convo", "description": "conversation id colored uniquely"},
            {"name": "leverage", "description": "leverage score 0..10 (only for scored clusters)"},
        ],
        "note": "Per-message layer arrays live in cognitive_atlas.html. Use atlas_query for cluster-level questions.",
    }


# --------------------------------------------------------------------------
# Text renderers (for --text mode)
# --------------------------------------------------------------------------


def _t_table(rows: list[dict[str, Any]], cols: list[str]) -> str:
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    lines = [header, sep]
    for r in rows:
        lines.append("  ".join(str(r.get(c, ""))[: widths[c]].ljust(widths[c]) for c in cols))
    return "\n".join(lines)


def _render_text(cmd: str, result: Any) -> str:
    if cmd == "stats":
        return "\n".join(f"{k}: {v}" for k, v in result.items())
    if cmd == "clusters":
        return _t_table(result, ["id", "size", "user_pct", "asset_vector", "normalized_leverage", "date_range"])
    if cmd in ("cluster", "inspect"):
        out = [f"Cluster #{result['id']} ({result.get('size', '?')} msgs)"]
        for k in ("dominant_role", "user_pct", "date_range", "asset_vector",
                  "revenue_tag", "normalized_leverage", "raw_composite", "market_score",
                  "tightness", "execution_ratio", "reusability_index", "dependency_load"):
            v = result.get(k)
            if v is not None:
                out.append(f"  {k}: {v}")
        if result.get("top_titles"):
            out.append("  top_titles:")
            for t in result["top_titles"][:10]:
                out.append(f"    - {t.get('title', '?')} ({t.get('msgs', 0)} msgs)")
        if result.get("top_ngrams"):
            out.append("  top_ngrams: " + ", ".join(result["top_ngrams"][:15]))
        return "\n".join(out)
    if cmd == "leverage":
        return _t_table(result, ["cluster_id", "normalized_leverage", "asset_vector", "revenue_tag", "size"])
    if cmd == "vectors":
        return _t_table(result["groups"], ["asset_vector", "count", "avg_leverage"])
    if cmd == "search":
        out = []
        for hit in result:
            out.append(f"#{hit['cluster_id']}  matched: {', '.join(hit['matched_on'])}")
            c = hit["cluster"]
            out.append(f"   size={c.get('size')} vec={c.get('asset_vector', '-')} "
                       f"leverage={c.get('normalized_leverage', '-')}")
        return "\n".join(out) if out else "(no matches)"
    if cmd == "near":
        return _t_table(result, ["id", "similarity", "size", "asset_vector", "date_range"])
    if cmd == "convo":
        out = [f"Conversation {result['convo_id']} -> Cluster #{result['cluster_id']}",
               f"  Sibling conversations in same cluster: {result['sibling_count']}"]
        c = result["cluster"]
        if c:
            out.append(f"  cluster size={c.get('size')} vec={c.get('asset_vector', '-')} "
                       f"leverage={c.get('normalized_leverage', '-')}")
        return "\n".join(out)
    if cmd == "layers":
        out = ["Layers:"]
        for l in result["layers"]:
            out.append(f"  {l['name']:<10} {l['description']}")
        out.append("")
        out.append(result.get("note", ""))
        return "\n".join(out)
    if cmd == "messages":
        out = [f"Cluster #{result['cluster_id']}: {result['total_convos']} conversations"]
        out.append("")
        out.append("Topic distribution (top 20 words by weight):")
        for t in result["topic_distribution"]:
            out.append(f"  {t['word']:<20} {t['weight']}")
        out.append("")
        out.append("Conversations:")
        for c in result["conversations"]:
            line = f"  #{c['convo_id']:<6}  {(c.get('title') or '')[:60]:<60}"
            if c.get("msg_count"):
                line += f"  ({c['msg_count']} msgs"
                if c.get("date"):
                    line += f", {c['date']}"
                line += ")"
            if c.get("decision"):
                line += f"  [{c['decision']}]"
            out.append(line)
            if c.get("top_topics"):
                out.append(f"          topics: {', '.join(c['top_topics'])}")
        return "\n".join(out)
    if cmd == "themes":
        return _t_table(result, ["topic", "cluster_count", "total_weight"])
    if cmd == "region":
        out = [f"Cluster #{result['cluster_id']} — neighborhood within cosine >= {result['radius_cosine']}"]
        out.append(f"  ({result['neighbors_in_radius']} neighbors found)")
        out.append("")
        return "\n".join(out) + _t_table(
            result["neighborhood"],
            ["cluster_id", "similarity", "size", "asset_vector", "leverage", "top_title"],
        )
    return json.dumps(result, indent=2, default=str)


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------


HANDLERS = {
    "stats":          cmd_stats,
    "clusters":       cmd_clusters,
    "cluster":        cmd_cluster,
    "inspect":        cmd_inspect,
    "leverage":       cmd_leverage,
    "vectors":        cmd_vectors,
    "search":         cmd_search,
    "near":           cmd_near,
    "convo":          cmd_convo,
    "layers":         cmd_layers,
    "messages":       cmd_messages,
    "themes":         cmd_themes,
    "region":         cmd_region,
    "graph":          cmd_graph,
    "graph-node":     cmd_graph_node,
    "bridges":        cmd_bridges,
    "path":           cmd_path,
    "evolution":      cmd_evolution,
    "role-breakdown": cmd_role_breakdown,
    "density":        cmd_density,
    "text":           cmd_text,
}


def _common_flags(p: argparse.ArgumentParser) -> None:
    """Flags available before OR after the subcommand."""
    p.add_argument("--text", action="store_true", help="Human-readable text output (default is JSON)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON with indent")
    p.add_argument("--root", type=Path, default=BASE, help="Directory holding atlas_*.json")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="atlas_query",
        description="Headless CLI for the Cognitive Atlas (cognitive_atlas.html in shell form).",
    )
    _common_flags(p)

    common = argparse.ArgumentParser(add_help=False)
    _common_flags(common)

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats",   help="Top-bar stats (messages, clusters, noise, etc.)", parents=[common])
    sub.add_parser("layers",  help="List available layer toggles", parents=[common])
    sub.add_parser("vectors", help="Group clusters by asset_vector", parents=[common])

    sp = sub.add_parser("clusters", help="List all clusters", parents=[common])
    sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--sort", choices=["id", "size", "user_pct", "normalized_leverage"], default="size")

    sp = sub.add_parser("cluster", help="Full cluster record (Inspector view)", parents=[common])
    sp.add_argument("cluster_id", type=int)

    sp = sub.add_parser("inspect", help="Alias for `cluster`", parents=[common])
    sp.add_argument("cluster_id", type=int)

    sp = sub.add_parser("leverage", help="Leverage Ranking table", parents=[common])
    sp.add_argument("--top", type=int, default=0)
    sp.add_argument("--vector", default=None, help="Filter by asset_vector (Tool, Content Engine, ...)")

    sp = sub.add_parser("search", help="Find clusters whose titles/ngrams mention QUERY", parents=[common])
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("near", help="Cosine-nearest clusters to CLUSTER_ID", parents=[common])
    sp.add_argument("cluster_id", type=int)
    sp.add_argument("--top", type=int, default=10)

    sp = sub.add_parser("convo", help="Find what cluster a conversation belongs to", parents=[common])
    sp.add_argument("convo_id", type=str)

    sp = sub.add_parser("messages", help="All conversations in a cluster with titles, dates, topic words (joins results.db)", parents=[common])
    sp.add_argument("cluster_id", type=int)
    sp.add_argument("--limit", type=int, default=0)

    sp = sub.add_parser("themes", help="Cross-cluster topic threads (themes that span multiple clusters)", parents=[common])
    sp.add_argument("--top", type=int, default=30)
    sp.add_argument("--min-clusters", type=int, default=5, help="Minimum clusters a topic must appear in")

    sp = sub.add_parser("region", help="Spatial neighborhood around a cluster (within cosine radius)", parents=[common])
    sp.add_argument("cluster_id", type=int)
    sp.add_argument("--radius", type=float, default=0.6, help="Min cosine similarity to be considered in the region")
    sp.add_argument("--limit", type=int, default=20)

    sp = sub.add_parser("graph", help="Full sigma graph (nodes + edges) or --summary for shape", parents=[common])
    sp.add_argument("--summary", action="store_true")

    sp = sub.add_parser("graph-node", help="One cluster's graph node + all incident edges", parents=[common])
    sp.add_argument("cluster_id", type=int)

    sp = sub.add_parser("bridges", help="Most-connected clusters (high graph degree)", parents=[common])
    sp.add_argument("--top", type=int, default=15)

    sp = sub.add_parser("path", help="Shortest path in cluster graph from A to B", parents=[common])
    sp.add_argument("from_id", type=int)
    sp.add_argument("to_id", type=int)

    sp = sub.add_parser("evolution", help="Time histogram of a cluster (oldest..newest in 10 bins)", parents=[common])
    sp.add_argument("cluster_id", type=int)

    sp = sub.add_parser("role-breakdown", help="User/assistant/tool split inside a cluster", parents=[common])
    sp.add_argument("cluster_id", type=int)

    sp = sub.add_parser("density", help="Spatial density per cluster (UMAP 2D space)", parents=[common])
    sp.add_argument("cluster_id", type=int, nargs="?", default=None)
    sp.add_argument("--sort", choices=["density", "n_points"], default="density")
    sp.add_argument("--top", type=int, default=20)

    sp = sub.add_parser("text", help="Pull actual message text of a conversation from the ChatGPT export bundle", parents=[common])
    sp.add_argument("convo_id", type=int)
    sp.add_argument("--limit", type=int, default=0, help="Max messages to return")
    sp.add_argument("--max-chars", type=int, default=0, help="Truncate each message to N chars (0 = full)")
    sp.add_argument("--export-dir", type=Path, default=None, help="Override ChatGPT export bundle location")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    data = load(args.root)
    handler = HANDLERS[args.cmd]
    try:
        result = handler(data, args)
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"error: {e}\n")
        return 2

    if args.text:
        print(_render_text(args.cmd, result))
    else:
        print(json.dumps(result, indent=2 if args.pretty else None, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
GENESIS TREE -- Self-Organizing Knowledge Graph Builder
======================================================
Reads HDBSCAN cluster assignments from atlas_clusters.json (produced by
build_cognitive_atlas.py) and builds a hierarchical knowledge tree on top.

What Genesis adds beyond the Atlas HDBSCAN pipeline:
  - Hierarchical tree (parent-child relationships between clusters)
  - Auto-labeling from topic weights
  - Maturity scoring per branch
  - Cross-domain bridge detection
  - Convergence detection (ideas arriving at same point from different angles)
  - Obsidian-compatible vault generation

Inputs:
  - atlas_clusters.json   (HDBSCAN cluster labels + centroids from Atlas)
  - results.db            (conversation metadata, topics)
  - memory_db.json        (full conversation text -- for vault depth)

Outputs:
  - genesis_output/genesis_tree.json
  - genesis_output/genesis_scoreboard.json
  - genesis_output/genesis_cross_links.json
  - genesis_output/genesis_convergences.json
  - genesis_output/genesis_report.md
  - genesis_output/vault/

Usage:
  python genesis_tree.py  # uses defaults relative to script dir
  python genesis_tree.py --db path/to/results.db --atlas-clusters path/to/atlas_clusters.json
"""

import sqlite3
import json
import os
import sys
import argparse
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent.resolve()

CLUSTER_MIN_SIZE = 5          # Minimum conversations to form a branch
CROSS_LINK_THRESHOLD = 0.40   # Cosine sim threshold for cross-domain links
MATURITY_THRESHOLD = 15       # Node count before a branch is "mature"
CONVERGENCE_THRESHOLD = 0.60  # Sim threshold for convergence detection
PARENT_MERGE_THRESHOLD = 0.50 # Sim threshold for grouping clusters into domains

# ---------------------------------------------------------------------------
# DATABASE ACCESS
# ---------------------------------------------------------------------------

def connect_db(db_path: str) -> sqlite3.Connection:
    """Connect to results.db."""
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_conversations(conn: sqlite3.Connection) -> dict[str, dict]:
    """Load conversation metadata."""
    convos: dict[str, dict] = {}
    cursor = conn.execute("""
        SELECT ct.convo_id, ct.title, ctime.date
        FROM convo_titles ct
        LEFT JOIN convo_time ctime ON ct.convo_id = ctime.convo_id
    """)
    for row in cursor:
        convos[row['convo_id']] = {
            'title': row['title'],
            'date': row['date']
        }
    return convos


def load_topics(conn: sqlite3.Connection) -> dict[str, dict[str, float]]:
    """Load topic weights per conversation."""
    topics: dict[str, dict[str, float]] = defaultdict(dict)
    cursor = conn.execute("SELECT convo_id, topic, weight FROM topics")
    for row in cursor:
        topics[row['convo_id']][row['topic']] = row['weight']
    return topics


def load_message_stats(conn: sqlite3.Connection) -> dict[str, dict]:
    """Load message counts and word totals per conversation."""
    stats: dict[str, dict] = {}
    cursor = conn.execute("""
        SELECT convo_id,
               COUNT(*) as msg_count,
               SUM(words) as total_words,
               SUM(CASE WHEN role='user' THEN words ELSE 0 END) as user_words
        FROM messages
        GROUP BY convo_id
    """)
    for row in cursor:
        stats[row['convo_id']] = {
            'msg_count': row['msg_count'],
            'total_words': row['total_words'],
            'user_words': row['user_words']
        }
    return stats

# ---------------------------------------------------------------------------
# LOAD ATLAS CLUSTERS (replaces raw embedding clustering)
# ---------------------------------------------------------------------------

def load_atlas_clusters(clusters_path: str) -> dict:
    """Load HDBSCAN cluster assignments from atlas_clusters.json."""
    if not os.path.exists(clusters_path):
        print(f"ERROR: Atlas clusters not found at {clusters_path}")
        print("Run build_cognitive_atlas.py first to generate atlas_clusters.json")
        sys.exit(1)
    with open(clusters_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# BUILD TREE FROM HDBSCAN CLUSTERS
# ---------------------------------------------------------------------------

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(dot / (na * nb))


def build_tree_from_clusters(
    atlas_data: dict,
) -> tuple[dict[int, dict], dict[str, np.ndarray]]:
    """
    Build a hierarchical tree from HDBSCAN cluster assignments.

    Instead of re-clustering from embeddings, this groups conversations by
    their HDBSCAN cluster label and then builds parent-child relationships
    between clusters based on centroid similarity.

    Returns:
        tree: dict mapping domain_id -> {members, sub_branches, centroid}
        convo_centroids: dict mapping convo_id -> centroid vector
    """
    assignments = atlas_data["convo_cluster_assignments"]
    convo_centroids_raw = atlas_data["convo_centroids"]
    cluster_centroids_raw = atlas_data["cluster_centroids"]

    # Convert centroids to numpy
    convo_centroids = {
        cid: np.array(vec, dtype=np.float32)
        for cid, vec in convo_centroids_raw.items()
    }
    cluster_centroids = {
        int(k): np.array(v, dtype=np.float32)
        for k, v in cluster_centroids_raw.items()
    }

    # Group conversations by cluster (exclude noise = -1)
    clusters: dict[int, list[str]] = defaultdict(list)
    for convo_id, label in assignments.items():
        label = int(label)
        if label != -1:
            clusters[label].append(convo_id)

    # Filter out tiny clusters
    significant = {
        cid: members for cid, members in clusters.items()
        if len(members) >= CLUSTER_MIN_SIZE
    }

    print(f"  {len(significant)} significant clusters "
          f"(of {len(clusters)} total, min_size={CLUSTER_MIN_SIZE})")

    # Build parent-child: merge similar clusters into domains
    cluster_ids = sorted(significant.keys())
    n = len(cluster_ids)

    if n == 0:
        return {}, convo_centroids

    # Compute pairwise similarity between cluster centroids
    vecs = np.array([cluster_centroids.get(cid, np.zeros(384))
                     for cid in cluster_ids])
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vecs = vecs / norms
    sim_matrix = vecs @ vecs.T

    # Simple agglomerative merge of clusters into domains
    # Use the first cluster in each group as domain_id
    merged: dict[int, list[int]] = {i: [i] for i in range(n)}
    active = set(range(n))

    while len(active) > 1:
        best_sim = -1.0
        best_pair = None
        active_list = sorted(active)
        for i_idx, ci in enumerate(active_list):
            for cj in active_list[i_idx + 1:]:
                sims = []
                for a in merged[ci]:
                    for b in merged[cj]:
                        sims.append(float(sim_matrix[a][b]))
                avg_sim = sum(sims) / len(sims)
                if avg_sim > best_sim:
                    best_sim = avg_sim
                    best_pair = (ci, cj)

        if best_sim < PARENT_MERGE_THRESHOLD or best_pair is None:
            break

        ci, cj = best_pair
        merged[ci] = merged[ci] + merged[cj]
        del merged[cj]
        active.discard(cj)

    # Build tree structure
    tree: dict[int, dict[str, Any]] = {}
    for group_idx, member_indices in merged.items():
        member_cluster_ids = [cluster_ids[i] for i in member_indices]
        all_convos: list[str] = []
        sub_branches: dict[int, list[str]] = {}

        for cid in member_cluster_ids:
            convos = significant[cid]
            all_convos.extend(convos)
            if len(convos) >= 3:
                sub_branches[cid] = convos

        if not all_convos:
            continue

        # Domain centroid = mean of member cluster centroids
        domain_vecs = [cluster_centroids.get(cid, np.zeros(384))
                       for cid in member_cluster_ids
                       if cid in cluster_centroids]
        if domain_vecs:
            domain_centroid = np.mean(domain_vecs, axis=0)
        else:
            domain_centroid = np.zeros(384)

        domain_id = cluster_ids[group_idx]
        tree[domain_id] = {
            'members': all_convos,
            'sub_branches': sub_branches,
            'centroid': domain_centroid,
            'hdbscan_clusters': member_cluster_ids,
        }

    print(f"  Merged into {len(tree)} domain groups")
    return tree, convo_centroids

# ---------------------------------------------------------------------------
# AUTO-LABEL BRANCHES USING TOPIC DATA
# ---------------------------------------------------------------------------

def label_branch(
    convo_ids: list[str],
    topics_data: dict[str, dict],
    convos_data: dict[str, dict],
) -> tuple[str, list[str], list[str]]:
    """Auto-generate a label for a branch based on dominant topics."""
    stopwords = {
        'this', 'that', 'with', 'from', 'have', 'what',
        'your', 'about', 'would', 'could', 'should', 'their',
        'there', 'where', 'when', 'they', 'them', 'then',
        'than', 'just', 'like', 'also', 'been', 'were',
        'some', 'each', 'make', 'made', 'will', 'into',
        'more', 'very', 'want', 'need', 'here', 'does'
    }

    topic_scores: dict[str, float] = defaultdict(float)
    for cid in convo_ids:
        if cid in topics_data:
            for topic, weight in topics_data[cid].items():
                if len(topic) > 3 and topic.lower() not in stopwords:
                    topic_scores[topic] += weight

    sorted_topics = sorted(topic_scores.items(), key=lambda x: -x[1])[:5]
    top_words = [t[0] for t in sorted_topics]

    titles = [convos_data[cid]['title'] for cid in convo_ids
              if cid in convos_data and convos_data[cid].get('title')]
    title_words: dict[str, int] = defaultdict(int)
    for title in titles:
        if title:
            for word in title.lower().split():
                if len(word) > 4:
                    title_words[word] += 1

    sorted_title_words = sorted(title_words.items(), key=lambda x: -x[1])[:3]
    title_keywords = [t[0] for t in sorted_title_words]

    label_parts = top_words[:3]
    if title_keywords:
        label_parts = title_keywords[:2] + top_words[:2]

    label = " / ".join(label_parts[:3]) if label_parts else "unlabeled"
    return label, top_words, titles

# ---------------------------------------------------------------------------
# CROSS-LINK DETECTION
# ---------------------------------------------------------------------------

def find_cross_links(
    tree: dict[int, dict],
    threshold: float = CROSS_LINK_THRESHOLD,
) -> list[dict]:
    """Find connections between branches in different domains.
    Only emits domain-level bridges (one per domain pair)."""
    cross_links: list[dict] = []
    domain_ids = list(tree.keys())

    for i, d1 in enumerate(domain_ids):
        for d2 in domain_ids[i + 1:]:
            sim = cosine_sim(tree[d1]['centroid'], tree[d2]['centroid'])
            if sim >= threshold:
                cross_links.append({
                    'domain_a': d1,
                    'domain_b': d2,
                    'similarity': round(sim, 4),
                    'type': 'domain_bridge'
                })

    cross_links.sort(key=lambda x: -x['similarity'])
    return cross_links

# ---------------------------------------------------------------------------
# MATURITY SCORING
# ---------------------------------------------------------------------------

def score_branches(
    tree: dict[int, dict],
    convos_data: dict[str, dict],
    stats_data: dict[str, dict],
    topics_data: dict[str, dict],
) -> list[dict]:
    """Score each branch on maturity axes."""
    scored: list[dict] = []

    for domain_id, domain in tree.items():
        members = domain['members']
        n = len(members)

        density = min(n / 50.0, 1.0)

        total_words = sum(
            stats_data.get(cid, {}).get('user_words', 0)
            for cid in members
        )
        depth = min(total_words / 100000.0, 1.0)

        dates: list[datetime] = []
        for cid in members:
            if cid in convos_data and convos_data[cid].get('date'):
                try:
                    dates.append(datetime.strptime(
                        convos_data[cid]['date'], '%Y-%m-%d'))
                except (ValueError, TypeError):
                    pass

        if dates:
            most_recent = max(dates)
            days_ago = (datetime.now() - most_recent).days
            recency = max(0, 1.0 - (days_ago / 180.0))
        else:
            recency = 0.0

        all_topics: set[str] = set()
        for cid in members:
            if cid in topics_data:
                all_topics.update(topics_data[cid].keys())
        richness = min(len(all_topics) / 100.0, 1.0)

        maturity = (
            0.25 * density +
            0.25 * depth +
            0.25 * recency +
            0.25 * richness
        )

        if n >= MATURITY_THRESHOLD and recency > 0.5:
            status = "ACTIVE_MATURE"
        elif n >= MATURITY_THRESHOLD and recency <= 0.5:
            status = "DORMANT_MATURE"
        elif n < MATURITY_THRESHOLD and recency > 0.5:
            status = "GROWING"
        else:
            status = "SEED"

        scored.append({
            'domain_id': domain_id,
            'conversation_count': n,
            'sub_branch_count': len(domain.get('sub_branches', {})),
            'hdbscan_clusters': domain.get('hdbscan_clusters', []),
            'total_user_words': total_words,
            'density': round(density, 3),
            'depth': round(depth, 3),
            'recency': round(recency, 3),
            'richness': round(richness, 3),
            'maturity_score': round(maturity, 3),
            'status': status
        })

    scored.sort(key=lambda x: -x['maturity_score'])
    return scored

# ---------------------------------------------------------------------------
# CONVERGENCE DETECTION
# ---------------------------------------------------------------------------

def detect_convergences(tree: dict[int, dict]) -> list[dict]:
    """Find ideas that independently evolved toward the same point."""
    convergences: list[dict] = []
    domain_ids = list(tree.keys())

    for i, d1 in enumerate(domain_ids):
        for d2 in domain_ids[i + 1:]:
            sim = cosine_sim(tree[d1]['centroid'], tree[d2]['centroid'])
            if sim >= CONVERGENCE_THRESHOLD:
                convergences.append({
                    'domain_a': d1,
                    'domain_b': d2,
                    'members_a': len(tree[d1]['members']),
                    'members_b': len(tree[d2]['members']),
                    'convergence_score': round(sim, 4)
                })

    convergences.sort(key=lambda x: -x['convergence_score'])
    return convergences

# ---------------------------------------------------------------------------
# OBSIDIAN VAULT GENERATION
# ---------------------------------------------------------------------------

def generate_vault(
    tree: dict[int, dict],
    labels: dict[int, dict],
    convos_data: dict[str, dict],
    stats_data: dict[str, dict],
    scored: list[dict],
    cross_links: list[dict],
    convergences: list[dict],
    output_dir: str,
) -> None:
    """Generate an Obsidian-compatible markdown vault."""
    vault_dir = os.path.join(output_dir, 'vault')
    os.makedirs(vault_dir, exist_ok=True)

    # Index page
    index_lines = [
        "# Genesis Knowledge Tree",
        "",
        f"*Auto-generated from "
        f"{sum(s['conversation_count'] for s in scored)} conversations*",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Domains",
        ""
    ]

    for domain_id, domain in tree.items():
        label = labels.get(domain_id, {}).get('label', 'unlabeled')
        score_data = next(
            (s for s in scored if s['domain_id'] == domain_id), {})
        status = score_data.get('status', 'UNKNOWN')
        maturity = score_data.get('maturity_score', 0)
        n = len(domain['members'])

        safe_label = label.replace('/', '-').replace(' ', '_')
        index_lines.append(
            f"- [[domain_{safe_label}|{label}]] -- "
            f"{n} convos | {status} | maturity: {maturity:.2f}"
        )

    index_lines += ["", "## Cross-Domain Bridges", ""]
    for cl in cross_links[:10]:
        la = labels.get(cl['domain_a'], {}).get('label', '?')
        lb = labels.get(cl['domain_b'], {}).get('label', '?')
        index_lines.append(f"- **{la}** <-> **{lb}** (sim: {cl['similarity']})")

    if convergences:
        index_lines += ["", "## Convergence Points", ""]
        for c in convergences[:10]:
            la = labels.get(c['domain_a'], {}).get('label', '?')
            lb = labels.get(c['domain_b'], {}).get('label', '?')
            index_lines.append(
                f"- {la} branch -> {lb} branch "
                f"(score: {c['convergence_score']}, "
                f"{c['members_a']}+{c['members_b']} convos converging)"
            )

    with open(os.path.join(vault_dir, 'INDEX.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(index_lines))

    # Domain pages
    for domain_id, domain in tree.items():
        label_data = labels.get(domain_id, {})
        label = label_data.get('label', 'unlabeled')
        top_words = label_data.get('top_words', [])
        safe_label = label.replace('/', '-').replace(' ', '_')

        score_data = next(
            (s for s in scored if s['domain_id'] == domain_id), {})

        lines = [
            f"# {label}",
            "",
            f"**Status**: {score_data.get('status', '?')}",
            f"**Maturity**: {score_data.get('maturity_score', 0):.3f}",
            f"**Conversations**: {len(domain['members'])}",
            f"**User Words Invested**: "
            f"{score_data.get('total_user_words', 0):,}",
            f"**Key Topics**: {', '.join(top_words[:8])}",
            "",
        ]

        if domain.get('sub_branches'):
            lines.append("## Sub-Branches")
            lines.append("")
            for sb_id, sb_members in domain['sub_branches'].items():
                sb_titles = [
                    convos_data[cid]['title']
                    for cid in sb_members
                    if cid in convos_data and convos_data[cid].get('title')
                ][:5]
                lines.append(f"### Branch {sb_id} ({len(sb_members)} convos)")
                for t in sb_titles:
                    lines.append(f"  - {t}")
                lines.append("")

        dated_members = []
        for cid in domain['members']:
            if cid in convos_data:
                dated_members.append((cid, convos_data[cid]))
        dated_members.sort(
            key=lambda x: x[1].get('date', ''), reverse=True)

        lines.append("## Recent Conversations")
        lines.append("")
        for cid, cdata in dated_members[:15]:
            date = cdata.get('date', '?')
            title = cdata.get('title', 'Untitled')
            words = stats_data.get(cid, {}).get('user_words', 0)
            lines.append(f"- **{date}** -- {title} ({words:,} words)")

        lines.append("")
        lines.append("---")
        lines.append(f"*Tags: #{safe_label}*")
        lines.append(f"*[[INDEX|<- Back to Index]]*")

        with open(os.path.join(vault_dir, f'domain_{safe_label}.md'),
                  'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    print(f"  Vault generated: {vault_dir}/ "
          f"({len(tree)} domain pages + index)")

# ---------------------------------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------------------------------

def generate_report(
    tree: dict[int, dict],
    labels: dict[int, dict],
    scored: list[dict],
    cross_links: list[dict],
    convergences: list[dict],
    output_dir: str,
) -> None:
    """Generate a human-readable synthesis report."""
    lines = [
        "# GENESIS TREE -- Knowledge Graph Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source: HDBSCAN clusters from Atlas pipeline",
        "",
        "---",
        "",
        "## Domain Map",
        "",
    ]

    for s in scored:
        label = labels.get(s['domain_id'], {}).get('label', 'unlabeled')
        lines.append(f"### {label}")
        lines.append(
            f"  Status: {s['status']} | Maturity: {s['maturity_score']:.3f}")
        lines.append(
            f"  Conversations: {s['conversation_count']} | "
            f"Sub-branches: {s['sub_branch_count']} | "
            f"Words: {s['total_user_words']:,}")
        lines.append(
            f"  Density: {s['density']:.2f} | Depth: {s['depth']:.2f} | "
            f"Recency: {s['recency']:.2f} | Richness: {s['richness']:.2f}")
        if s.get('hdbscan_clusters'):
            lines.append(
                f"  HDBSCAN clusters: {s['hdbscan_clusters']}")
        lines.append("")

    lines += [
        "---", "",
        "## Cross-Domain Bridges (Top 15)", "",
        "Connections between different knowledge domains -- ",
        "ideas that live near each other in vector space but came from ",
        "different contexts. High-value collision points.", "",
    ]
    for cl in cross_links[:15]:
        la = labels.get(cl['domain_a'], {}).get('label', '?')
        lb = labels.get(cl['domain_b'], {}).get('label', '?')
        lines.append(f"  {la}  <->  {lb}  (sim: {cl['similarity']})")

    if convergences:
        lines += [
            "", "---", "",
            "## Convergence Points", "",
            "Ideas that independently evolved toward the same conclusion ",
            "from different starting points. High-conviction signal.", "",
        ]
        for c in convergences[:15]:
            la = labels.get(c['domain_a'], {}).get('label', '?')
            lb = labels.get(c['domain_b'], {}).get('label', '?')
            lines.append(
                f"  [{la}] -> [{lb}] "
                f"(score: {c['convergence_score']}, "
                f"{c['members_a']}+{c['members_b']} convos)")

    lines += ["", "---", "", "## Action Summary", ""]

    active_mature = [s for s in scored if s['status'] == 'ACTIVE_MATURE']
    dormant_mature = [s for s in scored if s['status'] == 'DORMANT_MATURE']
    growing = [s for s in scored if s['status'] == 'GROWING']
    seeds = [s for s in scored if s['status'] == 'SEED']

    if active_mature:
        lines.append(
            f"**ACTIVE MATURE ({len(active_mature)})** -- Ready for execution:")
        for s in active_mature:
            label = labels.get(s['domain_id'], {}).get('label', '?')
            lines.append(
                f"  -> {label} (maturity: {s['maturity_score']:.3f})")
        lines.append("")

    if dormant_mature:
        lines.append(
            f"**DORMANT MATURE ({len(dormant_mature)})** "
            f"-- Deep knowledge, recently inactive. Resurrect?")
        for s in dormant_mature:
            label = labels.get(s['domain_id'], {}).get('label', '?')
            lines.append(
                f"  -> {label} (maturity: {s['maturity_score']:.3f})")
        lines.append("")

    if growing:
        lines.append(
            f"**GROWING ({len(growing)})** -- Active but need more depth:")
        for s in growing:
            label = labels.get(s['domain_id'], {}).get('label', '?')
            lines.append(
                f"  -> {label} (maturity: {s['maturity_score']:.3f})")
        lines.append("")

    if seeds:
        lines.append(
            f"**SEEDS ({len(seeds)})** -- Early-stage, low investment:")
        for s in seeds[:10]:
            label = labels.get(s['domain_id'], {}).get('label', '?')
            lines.append(f"  -> {label}")
        if len(seeds) > 10:
            lines.append(f"  ... and {len(seeds) - 10} more")
        lines.append("")

    report_path = os.path.join(output_dir, 'genesis_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"  Report written: {report_path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Genesis Tree -- Self-Organizing Knowledge Graph')
    parser.add_argument(
        '--db', default=str(BASE / 'results.db'),
        help='Path to results.db')
    parser.add_argument(
        '--atlas-clusters', default=str(BASE / 'atlas_clusters.json'),
        help='Path to atlas_clusters.json (from build_cognitive_atlas.py)')
    parser.add_argument(
        '--output', default=str(BASE / 'genesis_output'),
        help='Output directory')
    args = parser.parse_args()

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  GENESIS TREE -- Knowledge Graph Builder")
    print("  (consuming HDBSCAN clusters from Atlas pipeline)")
    print("=" * 60)

    # Load atlas clusters
    print("\n[1/7] Loading Atlas HDBSCAN clusters...")
    atlas_clusters = load_atlas_clusters(args.atlas_clusters)
    print(f"  {atlas_clusters['cluster_count']} clusters, "
          f"{atlas_clusters['total_conversations']} conversations")

    # Load DB metadata
    print("\n[2/7] Loading database metadata...")
    conn = connect_db(args.db)
    convos_data = load_conversations(conn)
    topics_data = load_topics(conn)
    stats_data = load_message_stats(conn)
    print(f"  {len(convos_data)} conversations loaded")

    # Build tree from HDBSCAN clusters
    print("\n[3/7] Building tree from HDBSCAN clusters...")
    tree, convo_centroids = build_tree_from_clusters(atlas_clusters)

    # Label branches
    print("\n[4/7] Auto-labeling branches...")
    labels: dict[int, dict] = {}
    for domain_id, domain in tree.items():
        label, top_words, titles = label_branch(
            domain['members'], topics_data, convos_data)
        labels[domain_id] = {
            'label': label,
            'top_words': top_words,
            'sample_titles': titles[:5]
        }
        print(f"  Domain {domain_id}: \"{label}\" "
              f"({len(domain['members'])} convos)")

    # Cross-links and convergences
    print("\n[5/7] Detecting cross-links and convergences...")
    cross_links = find_cross_links(tree)
    convergences = detect_convergences(tree)
    print(f"  {len(cross_links)} cross-links found")
    print(f"  {len(convergences)} convergence points detected")

    # Score branches
    print("\n[6/7] Scoring branches...")
    scored = score_branches(tree, convos_data, stats_data, topics_data)

    # Serialize tree to JSON
    tree_json: dict[str, dict] = {}
    for domain_id, domain in tree.items():
        tree_json[str(domain_id)] = {
            'label': labels.get(domain_id, {}).get('label', 'unlabeled'),
            'member_count': len(domain['members']),
            'members': domain['members'],
            'sub_branches': {
                str(k): v for k, v in domain.get('sub_branches', {}).items()
            },
            'centroid': domain['centroid'].tolist(),
            'hdbscan_clusters': domain.get('hdbscan_clusters', []),
        }

    # Write outputs
    print("\n[7/7] Writing outputs...")

    tree_path = os.path.join(output_dir, 'genesis_tree.json')
    with open(tree_path, 'w', encoding='utf-8') as f:
        json.dump(tree_json, f, indent=2, default=str)
    print(f"  Tree: {tree_path}")

    score_path = os.path.join(output_dir, 'genesis_scoreboard.json')
    with open(score_path, 'w', encoding='utf-8') as f:
        json.dump(scored, f, indent=2)
    print(f"  Scoreboard: {score_path}")

    links_path = os.path.join(output_dir, 'genesis_cross_links.json')
    with open(links_path, 'w', encoding='utf-8') as f:
        json.dump(cross_links, f, indent=2)
    print(f"  Cross-links: {links_path}")

    conv_path = os.path.join(output_dir, 'genesis_convergences.json')
    with open(conv_path, 'w', encoding='utf-8') as f:
        json.dump(convergences, f, indent=2)
    print(f"  Convergences: {conv_path}")

    generate_vault(
        tree, labels, convos_data, stats_data,
        scored, cross_links, convergences, output_dir)
    generate_report(
        tree, labels, scored, cross_links, convergences, output_dir)

    conn.close()

    print("\n" + "=" * 60)
    print("  GENESIS COMPLETE")
    print(f"  Output: {output_dir}/")
    print("=" * 60)
    print("\nFiles generated:")
    print("  genesis_tree.json        -- Full graph structure")
    print("  genesis_scoreboard.json  -- Ranked branches by maturity")
    print("  genesis_cross_links.json -- Cross-domain connections")
    print("  genesis_convergences.json -- Convergence points")
    print("  genesis_report.md        -- Human-readable synthesis")
    print("  vault/                   -- Obsidian-compatible markdown vault")


if __name__ == '__main__':
    main()

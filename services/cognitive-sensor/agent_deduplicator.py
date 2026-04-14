"""
Agent 2: Deduplicator
Takes excavated_ideas_raw.json and merges duplicate/near-duplicate ideas
into canonical entries with version histories.

Uses cosine similarity on idea embeddings with union-find clustering.
Threshold 0.75 = same idea, 0.60-0.75 = related idea.

Input:  excavated_ideas_raw.json
Output: ideas_deduplicated.json
"""

import json, base64
import numpy as np
from pathlib import Path
from numpy.linalg import norm
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# --- Configuration ---
SAME_THRESHOLD = 0.70      # Above this = same idea, merge
RELATED_THRESHOLD = 0.55   # Above this = related idea, link

# --- Union-Find for clustering ---

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px == py:
            return
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1

    def groups(self):
        clusters = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(i)
        return list(clusters.values())


def load_raw_ideas():
    """Load excavated ideas."""
    path = BASE / "excavated_ideas_raw.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def decode_embedding(b64_str):
    """Decode base64 embedding back to numpy array."""
    raw = base64.b64decode(b64_str)
    return np.frombuffer(raw, dtype=np.float32).copy()


def build_embedding_matrix(ideas):
    """Build numpy matrix from all idea embeddings."""
    embeddings = []
    for idea in ideas:
        emb = decode_embedding(idea["embedding"])
        embeddings.append(emb)
    return np.array(embeddings)


def compute_pairwise_similarity(matrix):
    """Compute pairwise cosine similarity matrix (batch)."""
    # Normalize rows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    normalized = matrix / norms
    # Cosine similarity = dot product of normalized vectors
    return np.dot(normalized, normalized.T)


def select_canonical(cluster_ideas):
    """Select the canonical idea from a cluster.
    Prefer: most recent date, then highest semantic similarity signal.
    """
    def sort_key(idea):
        date = idea.get("convo_date", "0000-00-00")
        sim = idea.get("extraction_signals", {}).get("semantic_similarity", 0)
        return (date, sim)

    sorted_ideas = sorted(cluster_ideas, key=sort_key, reverse=True)
    return sorted_ideas[0]


def build_version_timeline(cluster_ideas):
    """Build a version timeline from all instances of the same idea."""
    timeline = []
    # Sort by date ascending
    sorted_ideas = sorted(cluster_ideas, key=lambda x: x.get("convo_date", "0000-00-00"))

    for i, idea in enumerate(sorted_ideas):
        entry = {
            "idea_id": idea["idea_id"],
            "convo_id": idea["convo_id"],
            "convo_title": idea["convo_title"],
            "date": idea.get("convo_date", "unknown"),
            "category": idea["category_guess"],
        }
        # Add key quotes if present
        if idea.get("key_quotes"):
            entry["key_quote"] = idea["key_quotes"][0]

        # Evolution note
        if i == 0:
            entry["evolution_note"] = "First mention"
        else:
            entry["evolution_note"] = f"Revisited ({i + 1})"

        timeline.append(entry)

    return timeline


def merge_key_quotes(cluster_ideas, max_quotes=5):
    """Merge key quotes from all ideas, deduplicated."""
    all_quotes = []
    seen = set()
    for idea in cluster_ideas:
        for q in idea.get("key_quotes", []):
            q_clean = q.strip().lower()[:100]  # Rough dedup key
            if q_clean not in seen:
                seen.add(q_clean)
                all_quotes.append(q.strip())
    return all_quotes[:max_quotes]


def determine_best_category(cluster_ideas):
    """Pick the most common category from the cluster."""
    cats = [idea["category_guess"] for idea in cluster_ideas]
    from collections import Counter
    counts = Counter(cats)
    return counts.most_common(1)[0][0]


def main():
    print("=" * 60)
    print("AGENT 2: DEDUPLICATOR")
    print("Merging duplicate ideas via cosine similarity")
    print("=" * 60)

    # Load data
    data = load_raw_ideas()
    ideas = data["ideas"]
    print(f"\nLoaded {len(ideas)} raw ideas")

    if len(ideas) == 0:
        print("No ideas to deduplicate.")
        output = {
            "metadata": {
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "ideas_before_dedup": 0,
                "ideas_after_dedup": 0,
                "merge_groups": 0,
            },
            "ideas": [],
        }
        out_path = BASE / "ideas_deduplicated.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Wrote {out_path.name}")
        return

    # Build embedding matrix
    print("Building embedding matrix...")
    matrix = build_embedding_matrix(ideas)
    print(f"Matrix shape: {matrix.shape}")

    # Compute pairwise similarity
    print("Computing pairwise cosine similarity...")
    sim_matrix = compute_pairwise_similarity(matrix)

    # Cluster using union-find at SAME_THRESHOLD
    print(f"Clustering (threshold={SAME_THRESHOLD})...")
    uf = UnionFind(len(ideas))
    for i in range(len(ideas)):
        for j in range(i + 1, len(ideas)):
            if sim_matrix[i][j] >= SAME_THRESHOLD:
                uf.union(i, j)

    groups = uf.groups()
    merge_groups = sum(1 for g in groups if len(g) > 1)
    print(f"Found {len(groups)} unique ideas ({merge_groups} merge groups)")

    # Build deduplicated ideas
    deduped = []
    canon_counter = 0

    for group_indices in groups:
        canon_counter += 1
        cluster_ideas = [ideas[i] for i in group_indices]

        # Select canonical
        canonical = select_canonical(cluster_ideas)

        # Build version timeline
        timeline = build_version_timeline(cluster_ideas)

        # Merge quotes
        all_quotes = merge_key_quotes(cluster_ideas)

        # Best category
        category = determine_best_category(cluster_ideas)

        # Find related (but not same) ideas
        related_ids = set()
        for i in group_indices:
            for j in range(len(ideas)):
                if j in group_indices:
                    continue
                if RELATED_THRESHOLD <= sim_matrix[i][j] < SAME_THRESHOLD:
                    # Find the canonical id that j belongs to
                    related_ids.add(uf.find(j))

        # Date range
        all_dates = [idea.get("convo_date", "unknown") for idea in cluster_ideas]
        valid_dates = sorted([d for d in all_dates if d != "unknown"])

        # Combined signals
        max_sim = max(
            idea.get("extraction_signals", {}).get("semantic_similarity", 0)
            for idea in cluster_ideas
        )

        entry = {
            "canonical_id": f"canon_{canon_counter:04d}",
            "canonical_title": canonical["convo_title"],
            "canonical_text": canonical.get("idea_text", "")[:2000],
            "category": category,
            "mention_count": len(cluster_ideas),
            "merged_from": [idea["idea_id"] for idea in cluster_ideas],
            "version_timeline": timeline,
            "related_canonical_indices": list(related_ids),  # Resolved later
            "all_key_quotes": all_quotes,
            "combined_signals": {
                "max_semantic_similarity": round(max_sim, 4),
                "total_mentions": len(cluster_ideas),
                "first_date": valid_dates[0] if valid_dates else "unknown",
                "last_date": valid_dates[-1] if valid_dates else "unknown",
            },
            "embedding": canonical["embedding"],  # Keep canonical embedding
        }

        deduped.append(entry)

    # Resolve related_canonical_indices to canonical_ids
    # Build index map: group root -> canonical_id
    root_to_canon = {}
    for i, group_indices in enumerate(groups):
        root = uf.find(group_indices[0])
        root_to_canon[root] = deduped[i]["canonical_id"]

    for entry in deduped:
        related_roots = entry.pop("related_canonical_indices")
        entry["related_ideas"] = [
            root_to_canon[r] for r in related_roots if r in root_to_canon
        ]

    # Sort by mention count (most recurring first)
    deduped.sort(key=lambda x: x["mention_count"], reverse=True)

    # Build output
    output = {
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "ideas_before_dedup": len(ideas),
            "ideas_after_dedup": len(deduped),
            "merge_groups": merge_groups,
            "same_threshold": SAME_THRESHOLD,
            "related_threshold": RELATED_THRESHOLD,
        },
        "ideas": deduped,
    }

    # Validate before write
    require_valid(output, "ExcavatedIdeas.v1.json", "deduplicator")

    # Write
    out_path = BASE / "ideas_deduplicated.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"DEDUPLICATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Ideas before:  {len(ideas)}")
    print(f"Ideas after:   {len(deduped)}")
    print(f"Merge groups:  {merge_groups}")
    print(f"Reduction:     {len(ideas) - len(deduped)} ideas merged ({(1 - len(deduped)/max(len(ideas),1))*100:.1f}%)")
    print()

    # Show top merged clusters
    multi = [d for d in deduped if d["mention_count"] > 1]
    if multi:
        print("Most recurring ideas:")
        for d in multi[:10]:
            print(f"  [{d['mention_count']}x] {d['canonical_title'][:60]}")

    print(f"\nWrote {out_path.name}")


if __name__ == "__main__":
    main()

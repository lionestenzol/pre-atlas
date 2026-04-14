"""
Agent 3: Classifier
Takes ideas_deduplicated.json and builds hierarchical structure with
parent-child relationships, dependencies, alignment scoring, and status.

Uses semantic clustering for vision groups, text analysis for status
detection, and psychological profile data for alignment scoring.

Input:  ideas_deduplicated.json, DEEP_PSYCHOLOGICAL_PROFILE.md
Output: ideas_classified.json
"""

import json, re, base64
import numpy as np
from pathlib import Path
from numpy.linalg import norm
from collections import Counter
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# --- Configuration ---
VISION_CLUSTER_THRESHOLD = 0.55   # Similarity for grouping into vision clusters
PARENT_CHILD_THRESHOLD = 0.50     # Similarity for parent-child detection
MIN_VISION_CLUSTER_SIZE = 2       # Minimum ideas to form a vision cluster

# --- Status detection keywords ---
STARTED_SIGNALS = [
    "built", "created", "coded", "deployed", "launched", "set up",
    "installed", "configured", "implemented", "wrote", "tested",
    "running", "working on", "started building", "prototype",
]

STALLED_SIGNALS = [
    "haven't finished", "need to get back", "still need to",
    "put on hold", "paused", "stuck", "not sure how",
    "didn't finish", "abandoned", "gave up", "stopped",
]

DONE_SIGNALS = [
    "finished", "completed", "shipped", "done", "solved",
    "deployed", "live", "working", "accomplished",
]

# --- Skill extraction keywords ---
SKILL_KEYWORDS = {
    "python": ["python", "script", "pip", "django", "flask"],
    "javascript": ["javascript", "react", "node", "typescript", "vue", "next"],
    "ai_ml": ["ai", "machine learning", "llm", "gpt", "model", "embedding", "neural"],
    "automation": ["automation", "workflow", "zapier", "make.com", "taskade", "n8n"],
    "sales": ["sales", "cold call", "outreach", "prospect", "close", "pitch", "lead"],
    "marketing": ["marketing", "content", "seo", "ads", "social media", "brand", "audience"],
    "design": ["design", "ui", "ux", "figma", "wireframe", "prototype", "layout"],
    "data": ["database", "sql", "data", "analytics", "dashboard", "metrics"],
    "devops": ["deploy", "server", "docker", "cloud", "aws", "hosting", "ci/cd"],
    "writing": ["write", "copy", "blog", "article", "documentation", "course"],
    "finance": ["finance", "accounting", "budget", "revenue", "pricing", "investment"],
    "prompt_engineering": ["prompt", "custom gpt", "system prompt", "instruction", "few-shot"],
}

# --- Profile-based alignment values ---
# Extracted from DEEP_PSYCHOLOGICAL_PROFILE.md
PROFILE_VALUES = {
    "authenticity": 0.22,    # Being real, not fake
    "justice": 0.17,         # Fairness, standing up
    "success": 0.14,         # Achievement, results
    "growth": 0.12,          # Learning, evolving
    "truth": 0.10,           # Understanding reality
    "control": 0.09,         # Agency, autonomy
    "freedom": 0.08,         # Independence
    "recognition": 0.08,     # Being seen, valued
}

# Keywords that signal alignment with each value
VALUE_KEYWORDS = {
    "authenticity": ["authentic", "real", "genuine", "honest", "true to", "original"],
    "justice": ["fair", "right", "deserve", "should be", "wrong that", "stand up"],
    "success": ["succeed", "win", "achieve", "accomplish", "results", "outcome", "revenue", "profit"],
    "growth": ["learn", "grow", "improve", "develop", "evolve", "progress", "level up"],
    "truth": ["understand", "figure out", "discover", "analyze", "research", "truth"],
    "control": ["control", "manage", "own", "master", "command", "decide", "agency"],
    "freedom": ["free", "independent", "autonomous", "my own", "no boss", "remote"],
    "recognition": ["recognized", "noticed", "respected", "valued", "appreciated", "impact"],
}

# Strength alignment
STRENGTH_KEYWORDS = {
    "sublimation": ["create", "build", "channel", "transform", "make something"],
    "resilience": ["overcome", "despite", "anyway", "persist", "keep going"],
    "pattern_recognition": ["pattern", "system", "framework", "structure", "connect"],
}

# Cognitive fit indicators
COGNITIVE_FIT_POSITIVE = [
    "architecture", "system", "design", "meta", "strategy", "high-level",
    "framework", "orchestrate", "coordinate", "vision",
]
COGNITIVE_FIT_NEGATIVE = [
    "repetitive", "routine", "daily grind", "maintenance", "manual",
    "data entry", "admin", "paperwork",
]


def load_deduplicated():
    """Load deduplicated ideas."""
    path = BASE / "ideas_deduplicated.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def decode_embedding(b64_str):
    """Decode base64 embedding back to numpy array."""
    raw = base64.b64decode(b64_str)
    return np.frombuffer(raw, dtype=np.float32).copy()


def determine_status(idea):
    """Determine idea status based on text content and timeline."""
    text = idea.get("canonical_text", "").lower()
    quotes = " ".join(idea.get("all_key_quotes", [])).lower()
    combined = text + " " + quotes
    timeline = idea.get("version_timeline", [])

    # Check for done signals
    done_count = sum(1 for s in DONE_SIGNALS if s in combined)
    if done_count >= 2:
        return "completed"

    # Check for started signals
    started_count = sum(1 for s in STARTED_SIGNALS if s in combined)

    # Check for stalled signals
    stalled_count = sum(1 for s in STALLED_SIGNALS if s in combined)

    # Check temporal patterns
    dates = [e.get("date", "unknown") for e in timeline]
    valid_dates = sorted([d for d in dates if d != "unknown"])

    if len(valid_dates) >= 2:
        # Multiple mentions across different dates suggests stalling if no done signals
        first = valid_dates[0]
        last = valid_dates[-1]
        if first != last and stalled_count > 0:
            return "stalled"
        if first != last and started_count > 0:
            return "stalled"  # Started but revisited = likely stalled

    # Check if abandoned (very old, no recent mentions)
    if valid_dates:
        last_date = valid_dates[-1]
        # If last mention is far from most recent data (rough heuristic)
        if last_date < "2025-01-01" and len(timeline) == 1:
            return "abandoned"

    if started_count > 0:
        return "started"

    if stalled_count > 0:
        return "stalled"

    return "idea"


def extract_skills(idea):
    """Extract required skills from idea text."""
    text = idea.get("canonical_text", "").lower()
    quotes = " ".join(idea.get("all_key_quotes", [])).lower()
    combined = text + " " + quotes

    skills = []
    for skill, keywords in SKILL_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            skills.append(skill)

    return skills


def compute_alignment(idea):
    """Compute alignment score (0-1) based on psychological profile."""
    text = idea.get("canonical_text", "").lower()
    quotes = " ".join(idea.get("all_key_quotes", [])).lower()
    combined = text + " " + quotes

    breakdown = {}

    # Value alignment (50%)
    value_score = 0.0
    for value, weight in PROFILE_VALUES.items():
        keywords = VALUE_KEYWORDS.get(value, [])
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > 0:
            contribution = min(matches / 3, 1.0) * weight
            value_score += contribution
            breakdown[f"value_{value}"] = round(contribution, 3)

    # Normalize value score to 0-0.5 range
    value_score = min(value_score, 0.5)

    # Strength alignment (25%)
    strength_score = 0.0
    for strength, keywords in STRENGTH_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in combined)
        if matches > 0:
            contribution = min(matches / 2, 1.0) * 0.083  # 0.25 / 3 strengths
            strength_score += contribution
            breakdown[f"strength_{strength}"] = round(contribution, 3)

    strength_score = min(strength_score, 0.25)

    # Cognitive fit (25%)
    positive_hits = sum(1 for kw in COGNITIVE_FIT_POSITIVE if kw in combined)
    negative_hits = sum(1 for kw in COGNITIVE_FIT_NEGATIVE if kw in combined)
    cog_raw = (positive_hits - negative_hits) / max(len(COGNITIVE_FIT_POSITIVE), 1)
    cog_score = max(0, min(cog_raw, 1.0)) * 0.25
    breakdown["cognitive_fit"] = round(cog_score, 3)

    total = value_score + strength_score + cog_score
    return round(total, 3), breakdown


def build_vision_clusters(ideas):
    """Group ideas into vision clusters using semantic similarity."""
    if len(ideas) == 0:
        return [], {}

    # Build embedding matrix
    embeddings = []
    for idea in ideas:
        emb = decode_embedding(idea["embedding"])
        embeddings.append(emb)
    matrix = np.array(embeddings)

    # Normalize
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = matrix / norms
    sim_matrix = np.dot(normalized, normalized.T)

    # Greedy clustering
    assigned = set()
    clusters = []
    cluster_map = {}  # idea index -> cluster index

    # Sort ideas by mention count (most mentioned first = cluster seeds)
    sorted_indices = sorted(range(len(ideas)), key=lambda i: ideas[i].get("mention_count", 1), reverse=True)

    for seed_idx in sorted_indices:
        if seed_idx in assigned:
            continue

        cluster = [seed_idx]
        assigned.add(seed_idx)

        for j in range(len(ideas)):
            if j in assigned:
                continue
            if sim_matrix[seed_idx][j] >= VISION_CLUSTER_THRESHOLD:
                cluster.append(j)
                assigned.add(j)

        if len(cluster) >= MIN_VISION_CLUSTER_SIZE:
            cluster_idx = len(clusters)
            for idx in cluster:
                cluster_map[idx] = cluster_idx
            clusters.append(cluster)
        else:
            # Singleton — still track it
            cluster_idx = len(clusters)
            for idx in cluster:
                cluster_map[idx] = cluster_idx
            clusters.append(cluster)

    return clusters, cluster_map


def name_vision_cluster(ideas, indices):
    """Generate a name for a vision cluster based on its ideas."""
    # Collect all categories
    cats = [ideas[i]["category"] for i in indices]
    dominant_cat = Counter(cats).most_common(1)[0][0]

    # Collect title words
    title_words = []
    for i in indices:
        words = ideas[i].get("canonical_title", "").split()
        title_words.extend(w.lower() for w in words if len(w) > 3)

    common_words = Counter(title_words).most_common(3)
    name_parts = [w for w, _ in common_words]

    if name_parts:
        name = " ".join(w.capitalize() for w in name_parts)
    else:
        name = dominant_cat.replace("_", " ").title()

    return name


def detect_parent_child(ideas, sim_matrix):
    """Detect parent-child relationships.
    An idea is a parent if it's broader/bigger and a child is a specific component.
    Heuristic: longer text + more mentions = more likely parent.
    """
    relationships = {}  # child_idx -> parent_idx

    for i in range(len(ideas)):
        for j in range(i + 1, len(ideas)):
            if sim_matrix[i][j] < PARENT_CHILD_THRESHOLD:
                continue

            # Determine which is parent (broader/bigger idea)
            text_i = ideas[i].get("canonical_text", "")
            text_j = ideas[j].get("canonical_text", "")
            mentions_i = ideas[i].get("mention_count", 1)
            mentions_j = ideas[j].get("mention_count", 1)

            # Check for containment keywords
            title_i = ideas[i].get("canonical_title", "").lower()
            title_j = ideas[j].get("canonical_title", "").lower()

            big_words = ["empire", "conglomerate", "ecosystem", "platform", "system", "master", "blueprint"]
            small_words = ["feature", "component", "tool", "module", "step", "task"]

            i_big = any(w in title_i for w in big_words)
            j_big = any(w in title_j for w in big_words)
            i_small = any(w in title_i for w in small_words)
            j_small = any(w in title_j for w in small_words)

            # Score parent likelihood
            parent_score_i = len(text_i) * 0.001 + mentions_i + (3 if i_big else 0) - (2 if i_small else 0)
            parent_score_j = len(text_j) * 0.001 + mentions_j + (3 if j_big else 0) - (2 if j_small else 0)

            if parent_score_i > parent_score_j:
                if j not in relationships:  # Don't override existing parent
                    relationships[j] = i
            else:
                if i not in relationships:
                    relationships[i] = j

    return relationships


def detect_dependencies(ideas):
    """Detect dependency relationships.
    If idea A requires skills/knowledge from idea B, B is a dependency.
    """
    dependencies = {}  # idea_idx -> [dep_idx, ...]

    for i in range(len(ideas)):
        deps = []
        text_i = ideas[i].get("canonical_text", "").lower()
        title_i = ideas[i].get("canonical_title", "").lower()

        for j in range(len(ideas)):
            if i == j:
                continue

            title_j = ideas[j].get("canonical_title", "").lower()
            text_j = ideas[j].get("canonical_text", "").lower()

            # Check if idea i mentions something idea j is about
            # Simple heuristic: if j's title keywords appear in i's text as requirements
            j_words = set(title_j.split()) - {"a", "the", "and", "or", "to", "for", "of", "in", "with"}
            if len(j_words) < 2:
                continue

            # Check for dependency language
            dep_patterns = [
                f"need.*{'.*'.join(list(j_words)[:3])}",
                f"require.*{'.*'.join(list(j_words)[:3])}",
                f"first.*{'.*'.join(list(j_words)[:3])}",
                f"before.*{'.*'.join(list(j_words)[:3])}",
            ]

            for pat in dep_patterns:
                try:
                    if re.search(pat, text_i):
                        deps.append(j)
                        break
                except re.error:
                    continue

        if deps:
            dependencies[i] = deps

    return dependencies


def main():
    print("=" * 60)
    print("AGENT 3: CLASSIFIER")
    print("Building hierarchy, dependencies, and alignment scores")
    print("=" * 60)

    # Load data
    data = load_deduplicated()
    ideas = data["ideas"]
    print(f"\nLoaded {len(ideas)} deduplicated ideas")

    if len(ideas) == 0:
        print("No ideas to classify.")
        output = {
            "metadata": {
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "total_ideas": 0,
                "vision_clusters": 0,
                "status_breakdown": {},
            },
            "vision_clusters": [],
            "ideas": [],
        }
        out_path = BASE / "ideas_classified.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Wrote {out_path.name}")
        return

    # Build embedding matrix for relationship detection
    print("Building embedding matrix...")
    embeddings = []
    for idea in ideas:
        emb = decode_embedding(idea["embedding"])
        embeddings.append(emb)
    matrix = np.array(embeddings)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = matrix / norms
    sim_matrix = np.dot(normalized, normalized.T)

    # 1. Build vision clusters
    print("Building vision clusters...")
    clusters, cluster_map = build_vision_clusters(ideas)
    print(f"Found {len(clusters)} vision clusters")

    # Name clusters
    vision_clusters = []
    for ci, indices in enumerate(clusters):
        name = name_vision_cluster(ideas, indices)
        vision_clusters.append({
            "cluster_id": f"vision_{ci + 1:03d}",
            "name": name,
            "size": len(indices),
            "idea_ids": [ideas[i]["canonical_id"] for i in indices],
        })

    # 2. Detect parent-child relationships
    print("Detecting parent-child relationships...")
    parent_child = detect_parent_child(ideas, sim_matrix)
    print(f"Found {len(parent_child)} parent-child relationships")

    # 3. Detect dependencies
    print("Detecting dependencies...")
    dependencies = detect_dependencies(ideas)
    print(f"Found {len(dependencies)} ideas with dependencies")

    # 4. Classify each idea
    print("Classifying ideas (status, skills, alignment)...")
    classified_ideas = []
    status_counts = Counter()

    for i, idea in enumerate(ideas):
        # Status
        status = determine_status(idea)
        status_counts[status] += 1

        # Skills
        skills = extract_skills(idea)

        # Alignment
        alignment, alignment_breakdown = compute_alignment(idea)

        # Vision cluster
        vc_idx = cluster_map.get(i)
        vc_id = vision_clusters[vc_idx]["cluster_id"] if vc_idx is not None else None

        # Parent/children
        parent_idx = parent_child.get(i)
        parent_id = ideas[parent_idx]["canonical_id"] if parent_idx is not None else None
        child_indices = [j for j, p in parent_child.items() if p == i]
        child_ids = [ideas[j]["canonical_id"] for j in child_indices]

        # Dependencies
        dep_indices = dependencies.get(i, [])
        dep_ids = [ideas[j]["canonical_id"] for j in dep_indices]

        classified = {
            "canonical_id": idea["canonical_id"],
            "canonical_title": idea["canonical_title"],
            "canonical_text": idea["canonical_text"],
            "category": idea["category"],
            "mention_count": idea["mention_count"],
            "status": status,
            "skills_required": skills,
            "alignment_score": alignment,
            "alignment_breakdown": alignment_breakdown,
            "vision_cluster": vc_id,
            "parent_idea": parent_id,
            "child_ideas": child_ids,
            "dependencies": dep_ids,
            "related_ideas": idea.get("related_ideas", []),
            "version_timeline": idea["version_timeline"],
            "all_key_quotes": idea.get("all_key_quotes", []),
            "combined_signals": idea.get("combined_signals", {}),
            "embedding": idea["embedding"],
        }

        classified_ideas.append(classified)

    # Build hierarchy tree
    roots = []
    children_map = {}
    for idea in classified_ideas:
        if idea["parent_idea"] is None:
            roots.append(idea["canonical_id"])
        if idea["child_ideas"]:
            children_map[idea["canonical_id"]] = idea["child_ideas"]

    # Build output
    output = {
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "total_ideas": len(classified_ideas),
            "vision_clusters_count": len(vision_clusters),
            "status_breakdown": dict(status_counts),
            "parent_child_relationships": len(parent_child),
            "ideas_with_dependencies": len(dependencies),
        },
        "vision_clusters": vision_clusters,
        "ideas": classified_ideas,
        "hierarchy_tree": {
            "roots": roots,
            "children": children_map,
        },
    }

    # Validate before write
    require_valid(output, "ExcavatedIdeas.v1.json", "classifier")

    # Write
    out_path = BASE / "ideas_classified.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"CLASSIFICATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total ideas:      {len(classified_ideas)}")
    print(f"Vision clusters:  {len(vision_clusters)}")
    print()
    print("Status breakdown:")
    for status, count in status_counts.most_common():
        print(f"  {status:<15} {count:>4}")
    print()
    print("Vision clusters:")
    for vc in sorted(vision_clusters, key=lambda x: x["size"], reverse=True)[:10]:
        print(f"  [{vc['size']:>3} ideas] {vc['name']}")
    print()

    # Top aligned ideas
    top_aligned = sorted(classified_ideas, key=lambda x: x["alignment_score"], reverse=True)[:5]
    print("Top 5 aligned ideas:")
    for idea in top_aligned:
        print(f"  [{idea['alignment_score']:.2f}] {idea['canonical_title'][:55]}")

    print(f"\nWrote {out_path.name}")


if __name__ == "__main__":
    main()

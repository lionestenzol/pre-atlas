"""
cluster_leverage_map.py — Strategic Asset Extraction Protocol

Reads Phase 2 atlas cluster labels, message embeddings, and raw message texts.
Computes 5 leverage metrics + Asset Vector Type per cluster.
Outputs leverage_map.json and LEVERAGE_MAP.md.

Input:  cognitive_atlas.html (cluster labels), results.db (embeddings),
        memory_db.json (message texts)
Output: leverage_map.json, LEVERAGE_MAP.md

Usage:
    python cluster_leverage_map.py
"""

import json, sqlite3, re, gc, numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

BASE = Path(__file__).parent.resolve()
DB_FILE = BASE / "results.db"
ATLAS_HTML = BASE / "cognitive_atlas.html"
MEMORY_DB = BASE / "memory_db.json"
OUT_JSON = BASE / "leverage_map.json"
OUT_MD = BASE / "LEVERAGE_MAP.md"

TOP_N_CLUSTERS = 15
TIGHTNESS_SAMPLE_THRESHOLD = 2000
TIGHTNESS_SAMPLE_SIZE = 500
MAX_TEXT_CHARS = 2000
MIN_WORDS = 3

# ── Execution Signal Patterns (pre-compiled) ────────────────────────────────

RE_CODE_BLOCK = re.compile(r'```')
RE_INDENT_BLOCK = re.compile(r'\n\n {4,}\S')
RE_NUMBERED_LIST = re.compile(r'^\s*\d+\.\s+', re.MULTILINE)
RE_BULLET_LIST = re.compile(r'^\s*[-*]\s+', re.MULTILINE)
RE_FRAMEWORK = re.compile(
    r'\b(?:step\s+\d|phase\s+\d|framework[:\s]|protocol[:\s]|system[:\s]|template[:\s])',
    re.IGNORECASE
)
RE_DELIVERABLE = re.compile(
    r'\b(?:deliverable|output|produce|generate|create|build)\s*:',
    re.IGNORECASE
)

# ── Revenue Tag Keywords ────────────────────────────────────────────────────

REVENUE_TAG_KEYWORDS = {
    "personal_regulation": [
        "emotion", "feeling", "cope", "stress", "anxiety", "anger", "frustration",
        "self-care", "mindset", "therapy", "overwhelm", "burnout", "mental health",
        "regulate", "process", "vent", "struggle", "hurt", "pain", "depressed",
    ],
    "infrastructure_build": [
        "code", "script", "api", "database", "deploy", "architecture", "server",
        "backend", "frontend", "pipeline", "devops", "docker", "git", "build",
        "implement", "function", "class", "module", "import", "python", "typescript",
    ],
    "tool_orchestration": [
        "app", "subscription", "integration", "workflow", "compare", "review",
        "notion", "obsidian", "todoist", "zapier", "slack", "tool", "setup",
        "configure", "install", "plugin", "extension", "spreadsheet",
    ],
    "productizable_system": [
        "framework", "template", "sop", "protocol", "playbook", "system",
        "repeatable", "package", "sell", "productize", "methodology", "process",
        "reusable", "standard", "checklist", "workflow", "blueprint",
    ],
    "narrative_processing": [
        "story", "identity", "meaning", "narrative", "reflection", "journey",
        "purpose", "legacy", "vision", "belief", "philosophy", "metaphor",
        "pattern", "insight", "realization", "awareness", "understanding",
    ],
    "social_dynamics": [
        "relationship", "boundary", "confrontation", "manipulation", "trust",
        "conflict", "communication", "power", "dynamic", "toxic", "narcissist",
        "gaslight", "respect", "assert", "negotiate", "family", "friend",
    ],
}

MARKET_SCORE_BASE = {
    "personal_regulation": 1,
    "infrastructure_build": 4,
    "tool_orchestration": 5,
    "productizable_system": 8,
    "narrative_processing": 3,
    "social_dynamics": 6,
}


# ── Step 1: Parse Cluster Labels from Atlas HTML ────────────────────────────

def parse_cluster_labels():
    """Parse cluster labels and metadata from cognitive_atlas.html payload."""
    if not ATLAS_HTML.exists():
        print(f"ERROR: {ATLAS_HTML.name} not found. Run: python build_cognitive_atlas.py")
        exit(1)

    print(f"  Reading {ATLAS_HTML.name}...")
    html_text = ATLAS_HTML.read_text(encoding="utf-8")

    # Find the JSON payload: const D = {...};
    marker = "const D = "
    start = html_text.find(marker)
    if start == -1:
        print("ERROR: Could not find 'const D = ' in atlas HTML.")
        exit(1)

    json_start = start + len(marker)
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(html_text, json_start)

    cluster_labels = payload["layers"]["cluster"]
    convo_ids = payload["convo_ids"]
    msg_indices = payload.get("msg_indices", [])
    roles = payload["roles"]
    word_counts = payload.get("word_counts", [])

    print(f"  Parsed {len(cluster_labels)} cluster labels from atlas payload")
    return {
        "cluster_labels": cluster_labels,
        "convo_ids": convo_ids,
        "msg_indices": msg_indices,
        "roles": roles,
        "word_counts": word_counts,
    }


# ── Step 2: Load Embeddings from results.db ─────────────────────────────────

def load_embeddings():
    """Load 384-dim embeddings from results.db in atlas order."""
    con = sqlite3.connect(str(DB_FILE))
    cur = con.cursor()

    rows = cur.execute("""
        SELECT embedding FROM message_embeddings
        ORDER BY CAST(convo_id AS INTEGER), msg_index
    """).fetchall()
    con.close()

    embeddings = np.array([
        np.frombuffer(row[0], dtype=np.float32) for row in rows
    ])
    print(f"  Loaded {embeddings.shape[0]} embeddings ({embeddings.shape[1]}D)")
    return embeddings


# ── Step 3: Load Message Texts from memory_db.json ──────────────────────────

def load_message_texts():
    """Build (convo_id, msg_index) -> text lookup from memory_db.json."""
    print(f"  Reading {MEMORY_DB.name} (140MB)...")
    raw = json.load(open(MEMORY_DB, encoding="utf-8"))

    texts = {}
    for convo_idx, convo in enumerate(raw):
        cid = str(convo_idx)
        for msg_idx, msg in enumerate(convo.get("messages", [])):
            role = msg.get("role", "unknown")
            text = msg.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            text = str(text)
            word_count = len(text.split())

            # Same filtering as init_message_embeddings.py
            if role == "system":
                continue
            if word_count < MIN_WORDS:
                continue

            texts[(cid, msg_idx)] = text

    # Free raw JSON
    del raw
    gc.collect()

    print(f"  Built text lookup: {len(texts)} messages")
    return texts


# ── Step 4: Build Cluster Index ─────────────────────────────────────────────

def build_cluster_index(atlas_data):
    """Group messages by cluster label. Returns top N clusters by size."""
    labels = atlas_data["cluster_labels"]
    convo_ids = atlas_data["convo_ids"]
    msg_indices = atlas_data["msg_indices"]
    roles = atlas_data["roles"]
    word_counts = atlas_data["word_counts"]

    clusters = defaultdict(lambda: {
        "indices": [], "convo_ids": [], "msg_indices": [],
        "roles": [], "word_counts": [], "unique_convos": set(),
    })

    for i, label in enumerate(labels):
        if label == -1:
            continue
        cl = clusters[label]
        cl["indices"].append(i)
        cl["convo_ids"].append(convo_ids[i])
        cl["msg_indices"].append(msg_indices[i] if msg_indices else i)
        cl["roles"].append(roles[i])
        cl["word_counts"].append(word_counts[i] if word_counts else 0)
        cl["unique_convos"].add(convo_ids[i])

    # Sort by size, take top N
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]["indices"]), reverse=True)
    top = dict(sorted_clusters[:TOP_N_CLUSTERS])

    print(f"  {len(clusters)} total clusters, analyzing top {len(top)}")
    return top, clusters


# ── Metric 1: Tightness Score ───────────────────────────────────────────────

def compute_tightness(indices, embeddings):
    """Mean pairwise cosine similarity within cluster."""
    if len(indices) <= 1:
        return 1.0

    cluster_embeds = embeddings[indices]

    if len(indices) > TIGHTNESS_SAMPLE_THRESHOLD:
        rng = np.random.default_rng(42)
        sample_idx = rng.choice(len(cluster_embeds), TIGHTNESS_SAMPLE_SIZE, replace=False)
        cluster_embeds = cluster_embeds[sample_idx]

    sim_matrix = cosine_similarity(cluster_embeds)
    # Upper triangle excluding diagonal
    n = sim_matrix.shape[0]
    triu_indices = np.triu_indices(n, k=1)
    pairwise_sims = sim_matrix[triu_indices]

    return float(np.nan_to_num(pairwise_sims.mean(), nan=0.0))


# ── Metric 2: Execution Ratio ──────────────────────────────────────────────

def compute_execution_ratio(cluster_data, texts_lookup):
    """% of messages with 2+ co-occurring execution signals."""
    execution_count = 0
    total = 0

    for i in range(len(cluster_data["indices"])):
        cid = cluster_data["convo_ids"][i]
        midx = cluster_data["msg_indices"][i]
        text = texts_lookup.get((cid, midx), "")
        if not text:
            continue

        total += 1
        signals = 0
        if RE_CODE_BLOCK.search(text):
            signals += 1
        if RE_INDENT_BLOCK.search(text):
            signals += 1
        if RE_NUMBERED_LIST.search(text):
            signals += 1
        if RE_BULLET_LIST.search(text):
            signals += 1
        if RE_FRAMEWORK.search(text):
            signals += 1
        if RE_DELIVERABLE.search(text):
            signals += 1

        if signals >= 2:
            execution_count += 1

    return execution_count / total if total > 0 else 0.0


# ── Metric 3: Reusability Index ─────────────────────────────────────────────

def compute_reusability_index(cluster_data, texts_lookup):
    """Detect repeated structural patterns across conversations."""
    # Group texts by conversation
    convo_texts = defaultdict(list)
    convo_user_openings = defaultdict(list)

    for i in range(len(cluster_data["indices"])):
        cid = cluster_data["convo_ids"][i]
        midx = cluster_data["msg_indices"][i]
        role = cluster_data["roles"][i]
        text = texts_lookup.get((cid, midx), "")
        if not text:
            continue

        convo_texts[cid].append(text[:MAX_TEXT_CHARS])

        # Track user message openings for prompt template detection
        if role == "user" and len(text.split()) >= 5:
            opening = " ".join(text.split()[:10]).lower()
            convo_user_openings[cid].append(opening)

    unique_convos = list(convo_texts.keys())
    if len(unique_convos) < 2:
        return 0.0, []

    # Concatenate per conversation for TF-IDF
    convo_docs = [" ".join(convo_texts[cid]) for cid in unique_convos]

    try:
        tfidf = TfidfVectorizer(
            ngram_range=(2, 3), max_features=200,
            stop_words="english", min_df=2
        )
        tfidf_matrix = tfidf.fit_transform(convo_docs)
        feature_names = tfidf.get_feature_names_out()
    except ValueError:
        return 0.0, []

    # Structural fingerprints: top-10 TF-IDF terms per conversation
    fingerprints = []
    for row_idx in range(tfidf_matrix.shape[0]):
        row = tfidf_matrix[row_idx].toarray().flatten()
        top_indices = row.argsort()[-10:][::-1]
        top_terms = set(feature_names[j] for j in top_indices if row[j] > 0)
        fingerprints.append(top_terms)

    # Count conversations sharing 3+ fingerprint terms
    shared_count = 0
    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            overlap = fingerprints[i] & fingerprints[j]
            if len(overlap) >= 3:
                shared_count += 1
                break  # Only count conversation i once

    # Detect repeated prompt templates (same opening across 5+ conversations)
    all_openings = []
    for cid in unique_convos:
        all_openings.extend(convo_user_openings.get(cid, []))

    opening_counts = Counter(all_openings)
    repeated_templates = sum(1 for _, c in opening_counts.items() if c >= 5)

    # Reusability score
    total_convos = len(unique_convos)
    fingerprint_ratio = shared_count / total_convos if total_convos > 0 else 0
    template_ratio = min(repeated_templates / max(total_convos, 1), 1.0)
    reusability = min((fingerprint_ratio + template_ratio) / 2, 1.0)

    # Top n-grams by aggregate weight
    col_sums = np.asarray(tfidf_matrix.sum(axis=0)).flatten()
    top_ngram_indices = col_sums.argsort()[-15:][::-1]
    top_ngrams = [feature_names[i] for i in top_ngram_indices if col_sums[i] > 0]

    return reusability, top_ngrams


# ── Metric 4: Dependency Load ──────────────────────────────────────────────

def compute_dependency_load(cluster_data, convo_to_clusters, total_clusters):
    """Cross-cluster conversation spread."""
    if total_clusters <= 1:
        return 0.0

    spreads = []
    for cid in cluster_data["unique_convos"]:
        other_count = len(convo_to_clusters.get(cid, set())) - 1
        spread = other_count / (total_clusters - 1)
        spreads.append(spread)

    return float(np.mean(spreads)) if spreads else 0.0


# ── Metric 5: Revenue Alignment Tag ────────────────────────────────────────

def compute_revenue_tag(cluster_data, texts_lookup, execution_ratio, reusability):
    """Auto-classify cluster + compute market score."""
    # Concatenate cluster text (cap at 50K chars)
    all_text = []
    char_count = 0
    for i in range(len(cluster_data["indices"])):
        cid = cluster_data["convo_ids"][i]
        midx = cluster_data["msg_indices"][i]
        text = texts_lookup.get((cid, midx), "")
        if text and char_count < 50000:
            all_text.append(text[:1000])
            char_count += min(len(text), 1000)

    combined = " ".join(all_text).lower()

    # Count keyword hits per category
    tag_scores = {}
    for tag, keywords in REVENUE_TAG_KEYWORDS.items():
        hits = sum(combined.count(kw) for kw in keywords)
        tag_scores[tag] = hits

    # Assign tag with highest hits (tie-break: higher base market score)
    best_tag = max(
        tag_scores.keys(),
        key=lambda t: (tag_scores[t], MARKET_SCORE_BASE[t])
    )

    # Market score
    base = MARKET_SCORE_BASE[best_tag]
    market = min(round(base + (execution_ratio * 3) + (reusability * 4)), 10)

    return best_tag, market


# ── Asset Vector Type ───────────────────────────────────────────────────────

def classify_asset_vector(tag, execution_ratio, reusability, dependency_load,
                          tightness, composite, user_pct):
    """Rule-based classification of extraction path."""
    # 1. Internal Utility
    if tag == "personal_regulation" or composite < 3.0:
        return "Internal Utility"

    # 2. Framework
    if (execution_ratio > 0.3 and reusability > 0.25
            and tag in ("productizable_system", "social_dynamics")):
        return "Framework"

    # 3. Tool
    if (execution_ratio > 0.3
            and tag in ("infrastructure_build", "tool_orchestration")
            and dependency_load < 0.3):
        return "Tool"

    # 4. Content Engine
    if reusability > 0.2 and (tag == "narrative_processing" or user_pct > 80):
        return "Content Engine"

    # 5. Consulting Angle
    if (tightness > 0.5
            and tag in ("social_dynamics", "productizable_system")):
        return "Consulting Angle"

    # 6. Fallback
    return "Content Engine"


# ── Composite Leverage Score ────────────────────────────────────────────────

def compute_composite_leverage(tightness, execution_ratio, reusability,
                               dependency_load, market_score):
    """Weighted composite: 0-10 scale."""
    raw = (
        reusability * 2.5 +
        (market_score / 10.0) * 3.5 +
        execution_ratio * 2.0 +
        tightness * 1.0 +
        (1.0 - dependency_load) * 1.0
    )
    return round(raw, 2)


# ── Central / Peripheral Messages ───────────────────────────────────────────

def get_central_peripheral(indices, embeddings, cluster_data, texts_lookup, n=5):
    """Find n closest and n farthest messages from cluster centroid."""
    cluster_embeds = embeddings[indices]
    centroid = cluster_embeds.mean(axis=0, keepdims=True)
    sims = cosine_similarity(centroid, cluster_embeds).flatten()

    sorted_idx = np.argsort(sims)

    def get_texts(positions):
        result = []
        for pos in positions:
            i = pos
            cid = cluster_data["convo_ids"][i]
            midx = cluster_data["msg_indices"][i]
            text = texts_lookup.get((cid, midx), "(no text)")
            result.append(text[:200])
        return result

    # Central: highest similarity to centroid
    central_positions = sorted_idx[-n:][::-1].tolist()
    # Peripheral: lowest similarity
    peripheral_positions = sorted_idx[:n].tolist()

    return get_texts(central_positions), get_texts(peripheral_positions)


# ── Fragmentation Ratio ─────────────────────────────────────────────────────

def compute_fragmentation(cluster_data):
    """Ratio of conversations contributing only 1 message to the cluster."""
    convo_counts = Counter(cluster_data["convo_ids"])
    single_msg_convos = sum(1 for c in convo_counts.values() if c == 1)
    total_convos = len(convo_counts)
    return single_msg_convos / total_convos if total_convos > 0 else 0.0


# ── Markdown Report ─────────────────────────────────────────────────────────

def generate_markdown(leverage_data):
    """Generate LEVERAGE_MAP.md from computed metrics."""
    lines = []
    clusters = leverage_data["clusters"]
    ts = leverage_data["generated"]

    lines.append("# Cluster Leverage Map")
    lines.append("")
    lines.append(f"**Generated:** {ts}")
    lines.append(f"**Clusters analyzed:** {leverage_data['clusters_analyzed']}")
    lines.append(f"**Total messages in atlas:** {leverage_data['total_messages']:,}")
    lines.append("")

    # ── Ranked Table ──
    lines.append("## Ranked Clusters by Normalized Leverage")
    lines.append("")
    lines.append("| Rank | Cluster | Size | Norm Score | Raw Score | Asset Vector | Exec | Reuse | Tag |")
    lines.append("|------|---------|------|-----------|-----------|-------------|------|-------|-----|")

    for rank, cl in enumerate(clusters, 1):
        lines.append(
            f"| {rank} | C{cl['cluster_id']} | {cl['size']:,} | "
            f"**{cl['normalized_leverage']:.2f}** | {cl['raw_composite']:.2f} | "
            f"{cl['asset_vector']} | {cl['execution_ratio']:.2f} | "
            f"{cl['reusability_index']:.2f} | {cl['revenue_tag']} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Per-Cluster Detail ──
    for cl in clusters:
        lines.append(f"## Cluster {cl['cluster_id']} — {cl['asset_vector']} ({cl['size']:,} messages)")
        lines.append("")
        lines.append(f"**Revenue Tag:** {cl['revenue_tag']} | **Market Score:** {cl['market_score']}/10")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Tightness | {cl['tightness']:.4f} |")
        lines.append(f"| Execution Ratio | {cl['execution_ratio']:.4f} |")
        lines.append(f"| Reusability Index | {cl['reusability_index']:.4f} |")
        lines.append(f"| Dependency Load | {cl['dependency_load']:.4f} |")
        lines.append(f"| Fragmentation | {cl['fragmentation_ratio']:.4f} |")
        lines.append(f"| Conversations | {cl['conversations']} |")
        lines.append(f"| User % | {cl['user_pct']}% |")
        lines.append(f"| Raw Composite | {cl['raw_composite']:.2f} |")
        lines.append(f"| **Normalized** | **{cl['normalized_leverage']:.2f}** |")
        lines.append("")

        if cl.get("top_ngrams"):
            lines.append(f"**Top N-grams:** {', '.join(cl['top_ngrams'][:10])}")
            lines.append("")

        if cl.get("central_messages"):
            lines.append("**Central Messages (cluster core):**")
            for i, msg in enumerate(cl["central_messages"][:3], 1):
                safe = msg.replace("|", "\\|").replace("\n", " ")
                lines.append(f"{i}. {safe}")
            lines.append("")

        if cl.get("peripheral_messages"):
            lines.append("**Peripheral Messages (cluster boundary):**")
            for i, msg in enumerate(cl["peripheral_messages"][:3], 1):
                safe = msg.replace("|", "\\|").replace("\n", " ")
                lines.append(f"{i}. {safe}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ── Cognitive ROI Table ──
    lines.append("## Cognitive ROI Table")
    lines.append("")
    lines.append("Where energy produces assets vs where it leaks:")
    lines.append("")

    tag_groups = defaultdict(lambda: {"clusters": [], "msgs": 0, "leverages": []})
    for cl in clusters:
        tag = cl["revenue_tag"]
        tag_groups[tag]["clusters"].append(f"C{cl['cluster_id']}")
        tag_groups[tag]["msgs"] += cl["size"]
        tag_groups[tag]["leverages"].append(cl["normalized_leverage"])

    lines.append("| Category | Clusters | Total Msgs | Avg Leverage | Assessment |")
    lines.append("|----------|----------|-----------|-------------|------------|")

    for tag in sorted(tag_groups.keys(), key=lambda t: -np.mean(tag_groups[t]["leverages"])):
        g = tag_groups[tag]
        avg_lev = np.mean(g["leverages"])
        if avg_lev >= 7:
            assessment = "HIGH ROI"
        elif avg_lev >= 4:
            assessment = "MODERATE"
        else:
            assessment = "ENERGY LEAK"
        lines.append(
            f"| {tag} | {', '.join(g['clusters'])} | {g['msgs']:,} | "
            f"{avg_lev:.1f} | **{assessment}** |"
        )

    lines.append("")

    # ── Asset Vector Summary ──
    lines.append("## Asset Vector Summary")
    lines.append("")

    vector_groups = defaultdict(list)
    for cl in clusters:
        vector_groups[cl["asset_vector"]].append(cl)

    for vec_type in ["Framework", "Tool", "Content Engine", "Consulting Angle", "Internal Utility"]:
        if vec_type not in vector_groups:
            continue
        cls = vector_groups[vec_type]
        ids = ", ".join(f"C{c['cluster_id']}" for c in cls)
        avg_score = np.mean([c["normalized_leverage"] for c in cls])
        lines.append(f"**{vec_type}** ({ids}): avg normalized leverage {avg_score:.1f}")
        lines.append("")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    t0 = datetime.now()

    print("=" * 60)
    print("STRATEGIC ASSET EXTRACTION PROTOCOL")
    print("Cluster Leverage Map")
    print("=" * 60)

    # ── Load Data ──
    print("\n[1/6] Parsing cluster labels from atlas...")
    atlas_data = parse_cluster_labels()

    print("\n[2/6] Loading embeddings from results.db...")
    embeddings = load_embeddings()

    # Validate alignment
    n_labels = len(atlas_data["cluster_labels"])
    n_embeds = embeddings.shape[0]
    if n_labels != n_embeds:
        print(f"ERROR: Alignment mismatch — {n_labels} labels vs {n_embeds} embeddings.")
        print("The atlas HTML is stale. Re-run: python build_cognitive_atlas.py")
        exit(1)
    print(f"  Alignment verified: {n_labels} messages")

    print("\n[3/6] Loading message texts from memory_db.json...")
    texts_lookup = load_message_texts()

    elapsed = (datetime.now() - t0).total_seconds()
    print(f"  [{elapsed:.1f}s elapsed]")

    # ── Build Cluster Index ──
    print("\n[4/6] Building cluster index...")
    top_clusters, all_clusters = build_cluster_index(atlas_data)

    # Global convo-to-clusters lookup (for dependency load)
    convo_to_clusters = defaultdict(set)
    for cid, cdata in all_clusters.items():
        for convo_id in cdata["unique_convos"]:
            convo_to_clusters[convo_id].add(cid)
    total_cluster_count = len(all_clusters)

    # ── Compute Metrics ──
    print(f"\n[5/6] Computing metrics for {len(top_clusters)} clusters...")
    results = []

    for cluster_id in sorted(top_clusters.keys(), key=lambda k: len(top_clusters[k]["indices"]), reverse=True):
        cdata = top_clusters[cluster_id]
        n_msgs = len(cdata["indices"])
        print(f"  C{cluster_id} ({n_msgs:,} msgs)...", end="", flush=True)

        tightness = compute_tightness(cdata["indices"], embeddings)
        exec_ratio = compute_execution_ratio(cdata, texts_lookup)
        reusability, top_ngrams = compute_reusability_index(cdata, texts_lookup)
        dep_load = compute_dependency_load(cdata, convo_to_clusters, total_cluster_count)
        tag, market = compute_revenue_tag(cdata, texts_lookup, exec_ratio, reusability)
        composite = compute_composite_leverage(tightness, exec_ratio, reusability, dep_load, market)

        user_count = sum(1 for r in cdata["roles"] if r == "user")
        user_pct = round(100 * user_count / n_msgs, 1)

        asset_vector = classify_asset_vector(
            tag, exec_ratio, reusability, dep_load, tightness, composite, user_pct
        )

        central, peripheral = get_central_peripheral(
            cdata["indices"], embeddings, cdata, texts_lookup
        )
        frag = compute_fragmentation(cdata)

        results.append({
            "cluster_id": cluster_id,
            "size": n_msgs,
            "conversations": len(cdata["unique_convos"]),
            "user_pct": user_pct,
            "tightness": round(tightness, 4),
            "execution_ratio": round(exec_ratio, 4),
            "reusability_index": round(reusability, 4),
            "dependency_load": round(dep_load, 4),
            "revenue_tag": tag,
            "market_score": market,
            "raw_composite": composite,
            "asset_vector": asset_vector,
            "top_ngrams": top_ngrams[:15],
            "central_messages": central,
            "peripheral_messages": peripheral,
            "fragmentation_ratio": round(frag, 4),
        })

        print(f" lev={composite:.1f} vec={asset_vector} tag={tag}")

    # ── Normalized Leverage (min-max across the 15 clusters) ──
    raw_scores = [r["raw_composite"] for r in results]
    min_score = min(raw_scores)
    max_score = max(raw_scores)
    score_range = max_score - min_score if max_score > min_score else 1.0

    for r in results:
        r["normalized_leverage"] = round(
            ((r["raw_composite"] - min_score) / score_range) * 10, 2
        )

    # Sort by normalized leverage
    results.sort(key=lambda x: x["normalized_leverage"], reverse=True)

    # ── Output ──
    print(f"\n[6/6] Writing output files...")

    leverage_map = {
        "generated": datetime.now().isoformat(),
        "clusters_analyzed": len(results),
        "total_messages": n_embeds,
        "scoring": {
            "raw_min": round(min_score, 2),
            "raw_max": round(max_score, 2),
            "normalization": "min-max scaled to 0-10 across analyzed clusters",
        },
        "clusters": results,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(leverage_map, f, indent=2, ensure_ascii=False)
    print(f"  {OUT_JSON.name} ({OUT_JSON.stat().st_size / 1024:.0f} KB)")

    md_report = generate_markdown(leverage_map)
    OUT_MD.write_text(md_report, encoding="utf-8")
    print(f"  {OUT_MD.name} ({OUT_MD.stat().st_size / 1024:.0f} KB)")

    total = (datetime.now() - t0).total_seconds()
    print(f"\nDone in {total:.1f}s")

    # ── Print Top 5 Summary ──
    print("\n" + "=" * 60)
    print("TOP 5 CLUSTERS BY NORMALIZED LEVERAGE")
    print("=" * 60)
    print(f"{'Cluster':>8} {'Vector':<18} {'Exec':>6} {'Reuse':>6} {'Dep':>6} {'Tag':<24} {'Norm':>6}")
    print("-" * 60)
    for r in results[:5]:
        print(
            f"  C{r['cluster_id']:<5} {r['asset_vector']:<18} "
            f"{r['execution_ratio']:>5.2f} {r['reusability_index']:>6.2f} "
            f"{r['dependency_load']:>5.2f} {r['revenue_tag']:<24} "
            f"{r['normalized_leverage']:>5.1f}"
        )


if __name__ == "__main__":
    main()

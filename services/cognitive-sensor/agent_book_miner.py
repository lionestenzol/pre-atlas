"""
Agent: Book Miner
Scans all 1,397 conversations for power dynamics content and extracts
raw material for the Power Dynamics Mastery Guide.

Extracts USER messages only — the book is your voice, not the AI's.

Uses semantic similarity against power dynamics signature vectors
+ keyword detection to find relevant content.
Clusters extracted passages into natural chapter themes.
Outputs structured raw material + a generated book outline.

Input:  memory_db.json, results.db (for dates/titles)
Output: book_raw_material.json, BOOK_OUTLINE.md
"""

import json, re, sqlite3, base64
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from numpy.linalg import norm
from model_cache import get_model

BASE = Path(__file__).parent.resolve()

# --- Configuration ---

MIN_CONVO_WORDS = 30
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
SEMANTIC_THRESHOLD = 0.38
MIN_PASSAGE_WORDS = 15
MAX_PASSAGES_PER_CONVO = 10

# --- Power dynamics semantic signatures ---
# These define what "power dynamics content" means for embedding comparison.
POWER_DYNAMICS_SIGNATURES = [
    # Core power dynamics
    "power dynamics control manipulation dominance hierarchy social status",
    "someone trying to control me gaslight me put me down tear me apart",
    "people ganging up on me social exclusion bullying intimidation pressure",
    "standing my ground holding boundaries not letting people push me around",
    "social hierarchy food chain who has power who has access status games",

    # Interpersonal strategy
    "how to handle disrespect confrontation standing up for yourself",
    "people testing your boundaries seeing what they can get away with",
    "narcissism manipulation tactics gaslighting emotional abuse control",
    "reading people seeing through their games understanding their motives",
    "why people treat you differently when you have confidence and presence",

    # Workplace dynamics
    "office politics workplace power dynamics dealing with bad managers",
    "coworkers trying to undermine you workplace sabotage competition",
    "setting boundaries at work protecting your peace professional survival",

    # Relationship dynamics
    "relationship power imbalance who has leverage who needs who more",
    "attraction jealousy comparison envy someone wanting what you have",
    "people treating you differently based on your appearance confidence status",
    "family dynamics sibling rivalry generational patterns toxic family",

    # Self-awareness and frameworks
    "understanding why people behave the way they do social psychology",
    "patterns I keep seeing in how people interact with power and control",
    "the game everyone plays but nobody talks about unspoken social rules",
    "how society programs you to accept disrespect and stay small",
]

# --- Keyword patterns for power dynamics ---
POWER_KEYWORDS = [
    re.compile(r"\b(?:power\s+dynamic|social\s+dynamic|group\s+dynamic)", re.I),
    re.compile(r"\b(?:control|controlling|manipulat|gaslight|dominat)", re.I),
    re.compile(r"\b(?:hierarchy|pecking\s+order|food\s+chain|status)", re.I),
    re.compile(r"\b(?:disrespect|betray|backstab|undermine|sabotag)", re.I),
    re.compile(r"\b(?:boundar|stand\s+(?:my|your|his|her)\s+ground)", re.I),
    re.compile(r"\b(?:intimidat|bully|pressure|coerce|threaten)", re.I),
    re.compile(r"\b(?:narcissi|toxic|abusi|exploit)", re.I),
    re.compile(r"\b(?:jealous|envy|compet|rival)", re.I),
    re.compile(r"\b(?:leverage|advantage|upper\s+hand|power\s+move)", re.I),
    re.compile(r"\b(?:assert|confront|stand\s+up|push\s+back|fight\s+back)", re.I),
    re.compile(r"\b(?:access|gatekeep|exclude|shut\s+out|cut\s+off)", re.I),
    re.compile(r"\b(?:validate|validation|approval|seek\s+approval)", re.I),
    re.compile(r"\b(?:weak|strong|alpha|submissive|passive|aggressive)", re.I),
    re.compile(r"\b(?:respect|earn\s+respect|demand\s+respect|lose\s+respect)", re.I),
    re.compile(r"\b(?:test|testing\s+(?:me|you|him|her|them|boundaries))", re.I),
    re.compile(r"\b(?:game|play(?:ing)?\s+games|unspoken\s+rules)", re.I),
    re.compile(r"\b(?:confidence|presence|energy|aura|vibe)", re.I),
    re.compile(r"\b(?:program|deprogram|unprogram|condition|brainwash)", re.I),
]

# --- Chapter theme signatures ---
# These seed the clustering. Each becomes a potential chapter topic.
CHAPTER_THEMES = {
    "the_hierarchy": {
        "signature": "social hierarchy status levels food chain who is above who below power structure pecking order ranking",
        "label": "The Hierarchy Nobody Talks About",
    },
    "control_games": {
        "signature": "control manipulation gaslighting someone trying to control you tactics games people play to dominate",
        "label": "Control Games People Play",
    },
    "boundaries": {
        "signature": "setting boundaries holding your ground standing up for yourself saying no protecting your peace",
        "label": "Boundaries as Power",
    },
    "disrespect_patterns": {
        "signature": "disrespect betrayal backstabbing people tearing you down talking behind your back undermining",
        "label": "The Anatomy of Disrespect",
    },
    "attraction_and_jealousy": {
        "signature": "attraction jealousy envy comparison someone wanting what you have appearance confidence status dating",
        "label": "When Your Presence Threatens People",
    },
    "workplace_warfare": {
        "signature": "workplace dynamics office politics coworkers manager boss job career professional boundaries work",
        "label": "Workplace Power Dynamics",
    },
    "family_dynamics": {
        "signature": "family dynamics parents siblings generational patterns toxic family control guilt obligation blood",
        "label": "Family as the First Power Structure",
    },
    "the_deprogramming": {
        "signature": "deprogramming conditioning society programs you to accept less to be small to not fight back waking up seeing clearly",
        "label": "Deprogramming: Seeing the Game",
    },
    "isolation_strategy": {
        "signature": "choosing to be alone solitude isolation not engaging refusing to play the game walking away",
        "label": "The Power of Walking Away",
    },
    "reading_people": {
        "signature": "reading people seeing through them understanding motives patterns recognizing types predicting behavior",
        "label": "Reading People Like Code",
    },
    "validation_trap": {
        "signature": "seeking approval validation needing others to confirm your worth external validation trap people pleasing",
        "label": "The Validation Trap",
    },
    "confidence_presence": {
        "signature": "confidence presence energy masculine feminine aura how you carry yourself intimidation without trying",
        "label": "Confidence as a Weapon",
    },
}

# --- Noise filter: skip these conversations entirely ---
NOISE_TITLES = {
    "what i can do", "can you hear me", "i'm here for you",
    "hello", "hi there", "hey", "test", "testing",
    "help me", "new chat", "untitled", "(untitled)",
}


def load_conversations():
    """Load all conversations from memory_db.json."""
    path = BASE / "memory_db.json"
    print(f"Loading conversations from {path.name}...")
    with open(path, "r", encoding="utf-8") as f:
        convos = json.load(f)
    print(f"Loaded {len(convos)} conversations")
    return convos


def load_metadata():
    """Load dates and titles from results.db."""
    db_path = BASE / "results.db"
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    titles = {}
    for row in cur.execute("SELECT convo_id, title FROM convo_titles").fetchall():
        titles[row[0]] = row[1]

    dates = {}
    for row in cur.execute("SELECT convo_id, date FROM convo_time").fetchall():
        dates[row[0]] = row[1]

    con.close()
    return titles, dates


def extract_user_messages(convo):
    """Extract individual user messages (not concatenated — we want passage-level)."""
    messages = []
    for m in convo.get("messages", []):
        if m.get("role") == "user":
            text = m.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            text = text.strip()
            if text and len(text.split()) >= MIN_PASSAGE_WORDS:
                messages.append(text)
    return messages


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split long messages into overlapping word chunks."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap
    return chunks


def count_keyword_hits(text):
    """Count how many power dynamics keyword patterns match."""
    return sum(1 for pat in POWER_KEYWORDS if pat.search(text))


def cosine_sim(a, b):
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (norm(a) * norm(b) + 1e-10))


def extract_best_sentences(text, max_sentences=3):
    """Pull out the strongest individual sentences from a passage."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    scored = []
    for sent in sentences:
        words = sent.split()
        if len(words) < 8:
            continue
        score = count_keyword_hits(sent)
        # Boost first-person statements — these are the book's voice
        if re.search(r'\b(?:I|my|me)\b', sent, re.I):
            score += 1
        # Boost insight language
        if re.search(r'\b(?:because|that\'s why|realize|see now|understand|pattern|always|never)\b', sent, re.I):
            score += 1
        scored.append((score, sent.strip()))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:max_sentences] if _ > 0]


def main():
    print("=" * 60)
    print("AGENT: BOOK MINER")
    print("Mining conversations for Power Dynamics content")
    print("=" * 60)

    model = get_model()

    # Encode power dynamics signatures
    print("\nEncoding power dynamics signatures...")
    pd_signature_vecs = [
        model.encode(sig, show_progress_bar=False)
        for sig in POWER_DYNAMICS_SIGNATURES
    ]

    # Encode chapter theme signatures
    print("Encoding chapter theme signatures...")
    chapter_vecs = {}
    for theme_id, theme in CHAPTER_THEMES.items():
        chapter_vecs[theme_id] = model.encode(theme["signature"], show_progress_bar=False)

    # Load data
    convos = load_conversations()
    titles_db, dates_db = load_metadata()

    passages = []
    convos_with_content = 0
    total_passages = 0
    skipped = 0

    print(f"\nScanning {len(convos)} conversations...\n")

    for idx, convo in enumerate(convos):
        convo_id = str(idx)
        title = convo.get("title", "(untitled)")
        date = dates_db.get(convo_id, "unknown")

        if title.lower().strip() in NOISE_TITLES:
            skipped += 1
            continue

        user_messages = extract_user_messages(convo)
        if not user_messages:
            skipped += 1
            continue

        convo_passages = []

        for msg in user_messages:
            chunks = chunk_text(msg)

            for chunk in chunks:
                # Keyword check
                keyword_hits = count_keyword_hits(chunk)

                # Semantic check against power dynamics signatures
                chunk_vec = model.encode(chunk[:2000], show_progress_bar=False)
                max_pd_sim = max(cosine_sim(chunk_vec, sv) for sv in pd_signature_vecs)

                # Must pass at least one gate
                has_keywords = keyword_hits >= 2
                has_semantic = max_pd_sim >= SEMANTIC_THRESHOLD

                if not has_keywords and not has_semantic:
                    continue

                # Combined score: semantic weight + keyword boost
                relevance_score = max_pd_sim * 0.6 + min(keyword_hits / 10, 0.4)

                # Assign to best chapter theme
                theme_scores = {}
                for theme_id, theme_vec in chapter_vecs.items():
                    theme_scores[theme_id] = cosine_sim(chunk_vec, theme_vec)
                best_theme = max(theme_scores, key=theme_scores.get)
                best_theme_sim = theme_scores[best_theme]

                # Extract best sentences
                best_sentences = extract_best_sentences(chunk)

                convo_passages.append({
                    "convo_id": convo_id,
                    "convo_title": title,
                    "convo_date": date,
                    "passage": chunk.strip()[:3000],
                    "best_sentences": best_sentences,
                    "relevance_score": round(relevance_score, 4),
                    "semantic_similarity": round(max_pd_sim, 4),
                    "keyword_hits": keyword_hits,
                    "chapter_theme": best_theme,
                    "chapter_theme_label": CHAPTER_THEMES[best_theme]["label"],
                    "chapter_theme_score": round(best_theme_sim, 4),
                })

        if convo_passages:
            convos_with_content += 1
            # Cap per conversation
            convo_passages.sort(key=lambda x: x["relevance_score"], reverse=True)
            passages.extend(convo_passages[:MAX_PASSAGES_PER_CONVO])

        if (idx + 1) % 200 == 0:
            print(f"  Scanned {idx + 1}/{len(convos)}, {len(passages)} passages found...")

    total_passages = len(passages)

    # Sort all passages by relevance
    passages.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Group by chapter theme
    chapters = defaultdict(list)
    for p in passages:
        chapters[p["chapter_theme"]].append(p)

    # Build chapter summaries
    chapter_summaries = []
    for theme_id, theme in CHAPTER_THEMES.items():
        theme_passages = chapters.get(theme_id, [])
        if not theme_passages:
            continue

        # Sort by relevance within chapter
        theme_passages.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Collect unique conversation sources
        sources = list({p["convo_title"] for p in theme_passages})

        # Collect best sentences across the chapter
        all_sentences = []
        for p in theme_passages[:20]:  # Top 20 passages per chapter
            all_sentences.extend(p["best_sentences"])

        chapter_summaries.append({
            "theme_id": theme_id,
            "chapter_title": theme["label"],
            "passage_count": len(theme_passages),
            "avg_relevance": round(
                sum(p["relevance_score"] for p in theme_passages) / max(len(theme_passages), 1), 4
            ),
            "top_relevance": theme_passages[0]["relevance_score"] if theme_passages else 0,
            "source_conversations": len(sources),
            "top_quotes": all_sentences[:10],
            "passages": theme_passages,
        })

    # Sort chapters by total passage count (depth of coverage)
    chapter_summaries.sort(key=lambda x: x["passage_count"], reverse=True)

    # --- Build output JSON ---
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "book_title": "Power Dynamics Mastery Guide",
            "total_conversations_scanned": len(convos),
            "conversations_with_power_content": convos_with_content,
            "total_passages_extracted": total_passages,
            "chapters_with_content": len(chapter_summaries),
            "skipped_conversations": skipped,
        },
        "chapters": [
            {
                "theme_id": ch["theme_id"],
                "chapter_title": ch["chapter_title"],
                "passage_count": ch["passage_count"],
                "avg_relevance": ch["avg_relevance"],
                "source_conversations": ch["source_conversations"],
                "top_quotes": ch["top_quotes"],
                "passages": ch["passages"],
            }
            for ch in chapter_summaries
        ],
    }

    # Write JSON
    out_json = BASE / "book_raw_material.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {out_json.name}")

    # --- Generate BOOK_OUTLINE.md ---
    outline = []
    outline.append(f"# Power Dynamics Mastery Guide — Book Outline")
    outline.append(f"")
    outline.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by Atlas Book Miner*")
    outline.append(f"")
    outline.append(f"## Source Statistics")
    outline.append(f"")
    outline.append(f"- Conversations scanned: **{len(convos)}**")
    outline.append(f"- Conversations with power dynamics content: **{convos_with_content}**")
    outline.append(f"- Total passages extracted: **{total_passages}**")
    outline.append(f"- Chapters with material: **{len(chapter_summaries)}** / {len(CHAPTER_THEMES)}")
    outline.append(f"")
    outline.append(f"---")
    outline.append(f"")

    # Chapter listing
    outline.append(f"## Chapters (ranked by depth of coverage)")
    outline.append(f"")
    outline.append(f"| # | Chapter | Passages | Sources | Avg Relevance |")
    outline.append(f"|---|---------|----------|---------|---------------|")
    for i, ch in enumerate(chapter_summaries, 1):
        outline.append(
            f"| {i} | {ch['chapter_title']} | {ch['passage_count']} | "
            f"{ch['source_conversations']} convos | {ch['avg_relevance']:.3f} |"
        )
    outline.append(f"")
    outline.append(f"---")
    outline.append(f"")

    # Per-chapter detail
    for i, ch in enumerate(chapter_summaries, 1):
        outline.append(f"## Chapter {i}: {ch['chapter_title']}")
        outline.append(f"")
        outline.append(f"**Coverage:** {ch['passage_count']} passages from {ch['source_conversations']} conversations")
        outline.append(f"**Avg relevance:** {ch['avg_relevance']:.3f}")
        outline.append(f"")

        if ch["top_quotes"]:
            outline.append(f"**Your strongest lines:**")
            outline.append(f"")
            for q in ch["top_quotes"][:5]:
                # Truncate long quotes
                display = q[:200] + "..." if len(q) > 200 else q
                outline.append(f"> {display}")
                outline.append(f"")

        # Top source conversations
        top_passages = ch["passages"][:5]
        if top_passages:
            outline.append(f"**Top source conversations:**")
            outline.append(f"")
            seen_titles = set()
            for p in top_passages:
                t = p["convo_title"]
                if t not in seen_titles:
                    seen_titles.add(t)
                    outline.append(f"- \"{t}\" ({p['convo_date']}) — relevance {p['relevance_score']:.3f}")
            outline.append(f"")

        outline.append(f"---")
        outline.append(f"")

    # Recommendations
    outline.append(f"## Recommendations")
    outline.append(f"")

    if chapter_summaries:
        top_ch = chapter_summaries[0]
        outline.append(f"1. **Start with Chapter 1: {top_ch['chapter_title']}** — deepest coverage "
                       f"({top_ch['passage_count']} passages). This is where your voice is strongest.")
    if len(chapter_summaries) >= 3:
        thin = chapter_summaries[-1]
        outline.append(f"2. **{thin['chapter_title']}** has the least material ({thin['passage_count']} passages). "
                       f"Consider merging with a related chapter or writing new content for it.")
    outline.append(f"3. **Next step:** Review `book_raw_material.json` for each chapter's passages. "
                   f"Edit and connect your own words into flowing prose.")
    outline.append(f"4. **Target:** 12-15 of your best passages per chapter = ~2,000-3,000 words per chapter.")
    outline.append(f"")

    outline_text = "\n".join(outline)

    out_md = BASE / "BOOK_OUTLINE.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(outline_text)
    print(f"Wrote {out_md.name}")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print(f"BOOK MINING COMPLETE")
    print(f"{'=' * 60}")
    print(f"Conversations scanned:       {len(convos)}")
    print(f"Conversations with content:  {convos_with_content}")
    print(f"Total passages extracted:     {total_passages}")
    print(f"Chapters with material:      {len(chapter_summaries)} / {len(CHAPTER_THEMES)}")
    print()

    print("Chapter breakdown:")
    for i, ch in enumerate(chapter_summaries, 1):
        print(f"  {i:>2}. {ch['chapter_title']:<40} {ch['passage_count']:>4} passages  "
              f"({ch['source_conversations']} convos, relevance {ch['avg_relevance']:.3f})")

    print(f"\nOutputs:")
    print(f"  book_raw_material.json  — full passages grouped by chapter")
    print(f"  BOOK_OUTLINE.md         — chapter outline with your best quotes")


if __name__ == "__main__":
    main()

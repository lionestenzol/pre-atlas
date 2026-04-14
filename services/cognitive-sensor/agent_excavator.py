"""
Agent 1: Excavator
Extracts every idea, project, intention, plan, blueprint, and business concept
from all 1,397 conversations in memory_db.json.

Uses regex pattern matching + semantic similarity against idea signature vectors
to detect idea-bearing content. Filters out emotional venting.

Input:  memory_db.json, results.db (for dates/titles)
Output: excavated_ideas_raw.json
"""

import json, re, sqlite3, base64
import numpy as np
from pathlib import Path
from numpy.linalg import norm
from model_cache import get_model
from validate import require_valid

BASE = Path(__file__).parent.resolve()

# --- Configuration ---

# Minimum words in user text to consider a conversation
MIN_CONVO_WORDS = 50

# Semantic similarity threshold for idea detection
IDEA_SIM_THRESHOLD = 0.40

# Chunk size (words) for processing long conversations
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

# --- Intent patterns (regex) ---
INTENT_PATTERNS = [
    re.compile(r"\bi\s+(?:want|wanna)\s+to\s+(?:build|create|make|start|launch|develop|design)", re.I),
    re.compile(r"\bwhat\s+if\s+(?:we|i)\s+(?:could|built|made|created|designed)", re.I),
    re.compile(r"\bthe\s+idea\s+is\b", re.I),
    re.compile(r"\bmy\s+(?:plan|vision|goal|dream)\s+is\b", re.I),
    re.compile(r"\bi(?:'m|\s+am)\s+(?:going\s+to|gonna)\s+(?:build|create|start|launch|make)", re.I),
    re.compile(r"\bi(?:'ve|\s+have)\s+been\s+(?:thinking|planning)\s+about\b", re.I),
    re.compile(r"\b(?:blueprint|roadmap|strategy)\s+for\b", re.I),
    re.compile(r"\bbusiness\s+(?:idea|concept|model|plan)\b", re.I),
    re.compile(r"\b(?:saas|app|tool|platform|product)\s+(?:idea|concept|for|that)\b", re.I),
    re.compile(r"\b(?:consulting|freelance|agency)\s+(?:business|offering|service)\b", re.I),
    re.compile(r"\b(?:automate|automation)\s+(?:system|workflow|process|tool)\b", re.I),
    re.compile(r"\bframework\s+for\b", re.I),
    re.compile(r"\bsystem\s+(?:to|for|that)\s+(?:track|manage|handle|automate|organize)", re.I),
    re.compile(r"\bside\s+hustle\b", re.I),
    re.compile(r"\bpassive\s+income\b", re.I),
    re.compile(r"\brecurring\s+revenue\b", re.I),
    re.compile(r"\bsubscription\s+(?:model|service|business)\b", re.I),
    re.compile(r"\bi\s+(?:could|should)\s+(?:build|create|sell|offer|start)", re.I),
    re.compile(r"\bhere(?:'s|\s+is)\s+(?:my|the)\s+(?:plan|idea|concept|strategy)", re.I),
    re.compile(r"\bmonetize\b", re.I),
    re.compile(r"\bno[- ]code\s+(?:app|tool|platform)", re.I),
    re.compile(r"\bcustom\s+gpt\b", re.I),
]

# --- Noise title filter (conversations unlikely to contain real ideas) ---
NOISE_TITLES = {
    "what i can do", "can you hear me", "i'm here for you",
    "hello", "hi there", "hey", "test", "testing",
    "help me", "new chat", "untitled", "(untitled)",
}

# --- Venting / non-idea filters ---
VENT_PATTERNS = [
    re.compile(r"\bi\s+(?:hate|can't stand|am sick of|am tired of)\b", re.I),
    re.compile(r"\bwhy\s+(?:does|do|is|are)\s+(?:everything|life|people|this)\b", re.I),
    re.compile(r"\bi\s+(?:feel|felt)\s+(?:like shit|terrible|horrible|awful|depressed|anxious)\b", re.I),
]

# --- Category keywords ---
CATEGORIES = {
    "saas_product": ["saas", "subscription", "platform", "recurring revenue", "monthly", "users"],
    "consulting_service": ["consulting", "freelance", "agency", "clients", "service", "hourly"],
    "ai_automation": ["ai", "automation", "agent", "workflow", "gpt", "prompt", "llm", "model"],
    "content_media": ["content", "youtube", "course", "creator", "audience", "views", "followers"],
    "framework_system": ["framework", "system", "method", "process", "protocol", "methodology"],
    "career_job": ["job", "career", "position", "role", "salary", "employer", "resume"],
    "big_vision": ["conglomerate", "empire", "million", "domination", "scale", "global"],
    "side_hustle": ["hustle", "gig", "quick money", "earn", "extra income", "cash"],
    "ecommerce": ["ecommerce", "dropship", "amazon", "store", "product", "shop"],
    "crypto_trading": ["crypto", "bitcoin", "trading", "blockchain", "token", "coin"],
    "technical_project": ["code", "script", "api", "database", "deploy", "app", "tool", "build"],
    "education_learning": ["learn", "course", "study", "certification", "skill", "training"],
}

# --- Idea semantic signatures ---
IDEA_SIGNATURE_TEXTS = [
    "I want to build a business product service startup company",
    "project plan blueprint roadmap strategy vision goal action steps",
    "create develop launch ship deploy release build make",
    "automation system framework tool platform workflow pipeline",
    "consulting freelance side hustle income revenue money earning",
    "SaaS subscription recurring revenue software application users",
]


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


def extract_user_text(convo):
    """Extract only user messages from a conversation, concatenated."""
    parts = []
    for m in convo.get("messages", []):
        if m.get("role") == "user":
            text = m.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            if text.strip():
                parts.append(str(text))
    return " ".join(parts)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping word chunks."""
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


def detect_regex_signals(text):
    """Check text against intent patterns. Returns list of matched pattern strings."""
    matches = []
    for pat in INTENT_PATTERNS:
        found = pat.search(text)
        if found:
            matches.append(found.group(0))
    return matches


def is_venting(text):
    """Check if text is primarily emotional venting rather than an idea."""
    vent_count = sum(1 for pat in VENT_PATTERNS if pat.search(text))
    intent_count = len(detect_regex_signals(text))
    # If venting signals dominate and no intent signals, it's venting
    return vent_count > 0 and intent_count == 0


def categorize_idea(text):
    """Assign preliminary category based on keyword frequency."""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in CATEGORIES.items():
        score = sum(text_lower.count(kw) for kw in keywords)
        if score > 0:
            scores[cat] = score

    if not scores:
        return "uncategorized"
    return max(scores, key=scores.get)


def extract_key_quotes(text, max_quotes=3):
    """Extract sentences most likely to contain the core idea."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if not sentences:
        return []

    scored = []
    for sent in sentences:
        if len(sent.split()) < 5:
            continue
        score = 0
        # Boost for intent language
        score += len(detect_regex_signals(sent)) * 3
        # Boost for action verbs
        action_words = ["build", "create", "launch", "start", "make", "develop",
                        "automate", "sell", "monetize", "ship", "deploy", "design"]
        score += sum(1 for w in action_words if w in sent.lower())
        # Boost for first-person agency
        if re.search(r'\bi\s+(want|will|am going|plan|need)\b', sent, re.I):
            score += 2
        scored.append((score, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s.strip() for _, s in scored[:max_quotes] if _ > 0]


def main():
    print("=" * 60)
    print("AGENT 1: EXCAVATOR")
    print("Extracting ideas from all conversations")
    print("=" * 60)

    # Load model and generate idea signatures
    model = get_model()
    print("\nEncoding idea signatures...")
    idea_signatures = [
        model.encode(sig, show_progress_bar=False)
        for sig in IDEA_SIGNATURE_TEXTS
    ]

    # Load data
    convos = load_conversations()
    titles_db, dates_db = load_metadata()

    ideas = []
    idea_counter = 0
    convos_with_ideas = 0
    skipped_short = 0
    skipped_vent = 0

    print(f"\nScanning {len(convos)} conversations...\n")

    for idx, convo in enumerate(convos):
        convo_id = str(idx)
        title = convo.get("title", "(untitled)")
        date = dates_db.get(convo_id, "unknown")

        # Skip noise conversations
        if title.lower().strip() in NOISE_TITLES:
            skipped_short += 1
            continue

        # Extract user text
        user_text = extract_user_text(convo)
        word_count = len(user_text.split())

        if word_count < MIN_CONVO_WORDS:
            skipped_short += 1
            continue

        # Check if entire conversation is venting
        if is_venting(user_text[:2000]):
            # Still check for ideas — some convos mix venting with ideas
            pass

        # Chunk the text
        chunks = chunk_text(user_text)
        convo_ideas = []

        for chunk in chunks:
            # Signal detection
            regex_matches = detect_regex_signals(chunk)
            has_regex = len(regex_matches) > 0

            # Semantic similarity against idea signatures
            chunk_embedding = model.encode(chunk[:2000], show_progress_bar=False)
            max_sim = 0.0
            for sig_vec in idea_signatures:
                sim = np.dot(chunk_embedding, sig_vec) / (norm(chunk_embedding) * norm(sig_vec))
                max_sim = max(max_sim, float(sim))

            has_semantic = max_sim >= IDEA_SIM_THRESHOLD

            # Must have at least one signal
            if not has_regex and not has_semantic:
                continue

            # Filter pure venting chunks
            if is_venting(chunk) and not has_regex:
                skipped_vent += 1
                continue

            # This chunk contains an idea
            idea_counter += 1
            idea_text = chunk.strip()
            key_quotes = extract_key_quotes(idea_text)
            category = categorize_idea(idea_text)

            # Generate embedding for the idea itself (for deduplication)
            # Use key quotes if available, otherwise truncated idea text
            embed_text = " ".join(key_quotes) if key_quotes else idea_text[:1000]
            idea_embedding = model.encode(embed_text, show_progress_bar=False)

            convo_ideas.append({
                "idea_id": f"idea_{idea_counter:04d}",
                "convo_id": convo_id,
                "convo_title": title,
                "convo_date": date,
                "category_guess": category,
                "idea_text": idea_text[:3000],  # Cap text length
                "key_quotes": key_quotes,
                "extraction_signals": {
                    "regex_matches": regex_matches,
                    "semantic_similarity": round(max_sim, 4),
                    "has_regex": has_regex,
                    "has_semantic": has_semantic,
                },
                "embedding": base64.b64encode(idea_embedding.tobytes()).decode("ascii"),
            })

        if convo_ideas:
            convos_with_ideas += 1
            ideas.extend(convo_ideas)

        # Progress reporting
        if (idx + 1) % 200 == 0:
            print(f"  Scanned {idx + 1}/{len(convos)} conversations, {len(ideas)} ideas found so far...")

    # Build output
    output = {
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "total_conversations_scanned": len(convos),
            "conversations_with_ideas": convos_with_ideas,
            "total_ideas_extracted": len(ideas),
            "skipped_short": skipped_short,
            "skipped_vent": skipped_vent,
        },
        "ideas": ideas,
    }

    # Validate before write
    require_valid(output, "ExcavatedIdeas.v1.json", "excavator")

    # Write output
    out_path = BASE / "excavated_ideas_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"EXCAVATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Conversations scanned:    {len(convos)}")
    print(f"Conversations with ideas: {convos_with_ideas}")
    print(f"Total ideas extracted:    {len(ideas)}")
    print(f"Skipped (too short):      {skipped_short}")
    print(f"Skipped (venting):        {skipped_vent}")
    print()

    # Category breakdown
    cat_counts = {}
    for idea in ideas:
        cat = idea["category_guess"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print("Category breakdown:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:<25} {count:>4}")

    print(f"\nWrote {out_path.name}")


if __name__ == "__main__":
    main()

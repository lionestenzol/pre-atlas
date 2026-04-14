"""
Conversation Classifier Agent
Tags every conversation in memory_db.json with:
  - domain (personal, business, technical, processing, execution, learning)
  - outcome (produced, resolved, looped, abandoned)
  - emotional_trajectory (positive_arc, negative_arc, spiral, neutral, mixed)
  - intensity (low, medium, high)

Uses semantic signatures + keyword signals (same hybrid approach as semantic_loops.py).

Input:  memory_db.json, results.db
Output: conversation_classifications.json
"""

import json, re, sqlite3
import numpy as np
from pathlib import Path
from numpy.linalg import norm
from model_cache import get_model

BASE = Path(__file__).parent.resolve()

# --- Domain signatures (semantic) ---
DOMAIN_SIGNATURES = {
    "personal": "relationships family emotions feelings stress anxiety love hurt betrayal trust anger lonely friends parents children partner",
    "business": "business money income revenue startup clients customers sales marketing profit side hustle consulting freelance SaaS product pricing",
    "technical": "code python javascript API database build deploy app tool script framework server docker git react programming software architecture",
    "processing": "I feel like I think that I don't know why does this always happen to me venting frustrated confused overwhelmed processing emotions",
    "execution": "I built I created I finished I shipped I launched I completed I deployed I solved I fixed working on progress update done",
    "learning": "learn study course class quiz exam homework assignment tutorial how does what is explain teach me understand concept theory",
}

# --- Domain keywords (keyword layer) ---
DOMAIN_KEYWORDS = {
    "personal": {"feel", "feelings", "relationship", "family", "hurt", "love", "trust", "angry", "lonely", "scared", "mom", "dad", "brother", "sister", "girlfriend", "boyfriend", "wife", "husband", "friend", "betrayal", "abuse", "trauma"},
    "business": {"business", "money", "income", "revenue", "startup", "clients", "customers", "sales", "marketing", "profit", "hustle", "consulting", "freelance", "saas", "product", "pricing", "subscription", "monetize", "sell", "offer"},
    "technical": {"code", "python", "javascript", "api", "database", "deploy", "app", "script", "framework", "server", "docker", "git", "react", "json", "html", "css", "function", "class", "variable", "debug", "error", "npm", "pip"},
    "processing": {"feel like", "dont know", "why does", "always", "never", "confused", "overwhelmed", "stuck", "hate", "cant", "frustrated", "whatever", "idk", "smh", "honestly", "literally"},
    "execution": {"built", "created", "finished", "shipped", "launched", "completed", "deployed", "solved", "fixed", "working on", "progress", "update", "done", "implemented", "tested", "released"},
    "learning": {"learn", "study", "course", "class", "quiz", "exam", "homework", "assignment", "tutorial", "explain", "understand", "concept", "theory", "chapter", "module", "lesson", "textbook", "professor", "student", "grade"},
}

# --- Outcome signatures ---
OUTCOME_SIGNATURES = {
    "produced": "I built I created I shipped I deployed here is the result it works I made this finished product output deliverable",
    "resolved": "I figured it out I solved it I understand now I decided I chose I committed the answer is fixed resolved",
    "looped": "I keep coming back to I still don't know same thing again going in circles repeating myself stuck again",
    "abandoned": "forget it whatever nevermind I give up not worth it moving on doesn't matter fuck it",
}

OUTCOME_KEYWORDS = {
    "produced": {"built", "created", "shipped", "deployed", "launched", "published", "released", "finished", "completed", "made", "implemented"},
    "resolved": {"figured", "solved", "understand", "decided", "chose", "committed", "answer", "fixed", "resolved", "conclusion", "settled"},
    "looped": {"again", "still", "keep", "same", "circles", "repeating", "stuck", "loop", "over and over", "back to"},
    "abandoned": {"forget", "whatever", "nevermind", "give up", "not worth", "moving on", "doesnt matter", "fuck it", "scrap", "drop it"},
}

# --- Emotional trajectory detection ---
POSITIVE_WORDS = {"good", "great", "better", "happy", "excited", "confident", "free", "safe", "proud", "strong", "motivated", "grateful", "hopeful", "calm", "relieved", "amazing", "awesome", "blessed", "powerful"}
NEGATIVE_WORDS = {"bad", "terrible", "worse", "sad", "angry", "frustrated", "scared", "stressed", "anxious", "depressed", "hopeless", "tired", "exhausted", "overwhelmed", "hurt", "stupid", "worthless", "pissed", "miserable", "fucked"}


def load_conversations():
    path = BASE / "memory_db.json"
    print(f"Loading conversations from {path.name}...")
    with open(path, "r", encoding="utf-8") as f:
        convos = json.load(f)
    print(f"Loaded {len(convos)} conversations")
    return convos


def load_metadata():
    db_path = BASE / "results.db"
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()

    titles = {}
    for row in cur.execute("SELECT convo_id, title FROM convo_titles").fetchall():
        titles[row[0]] = row[1]

    dates = {}
    for row in cur.execute("SELECT convo_id, date FROM convo_time").fetchall():
        dates[row[0]] = row[1]

    # Load topics
    topics = {}
    for row in cur.execute("SELECT convo_id, topic, weight FROM topics").fetchall():
        if row[0] not in topics:
            topics[row[0]] = []
        topics[row[0]].append((row[1], row[2]))

    # Load word counts
    word_counts = {}
    for row in cur.execute("SELECT convo_id, SUM(words) FROM messages WHERE role='user' GROUP BY convo_id").fetchall():
        word_counts[row[0]] = row[1]

    con.close()
    return titles, dates, topics, word_counts


def extract_user_text(convo, max_chars=5000):
    """Extract user messages, capped for embedding."""
    parts = []
    total = 0
    for m in convo.get("messages", []):
        if m.get("role") == "user":
            text = m.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            if text.strip():
                parts.append(str(text))
                total += len(text)
                if total > max_chars:
                    break
    return " ".join(parts)


def extract_messages_by_role(convo):
    """Extract user messages in order for trajectory analysis."""
    user_msgs = []
    for m in convo.get("messages", []):
        if m.get("role") == "user":
            text = m.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            if text.strip():
                user_msgs.append(str(text))
    return user_msgs


def classify_domain_semantic(text_embedding, domain_embeddings):
    """Classify domain using cosine similarity against signatures."""
    scores = {}
    for domain, sig_emb in domain_embeddings.items():
        sim = np.dot(text_embedding, sig_emb) / (norm(text_embedding) * norm(sig_emb) + 1e-8)
        scores[domain] = float(sim)
    return scores


def classify_domain_keyword(text_lower, convo_topics):
    """Classify domain using keyword matching."""
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        for kw in keywords:
            score += text_lower.count(kw)
        # Also check topic weights
        if convo_topics:
            for topic, weight in convo_topics:
                if topic in keywords:
                    score += weight * 2
        scores[domain] = score
    return scores


def classify_domain(text, text_embedding, domain_embeddings, convo_topics):
    """Hybrid domain classification: 60% semantic + 40% keyword."""
    text_lower = text.lower()
    sem_scores = classify_domain_semantic(text_embedding, domain_embeddings)
    kw_scores = classify_domain_keyword(text_lower, convo_topics)

    # Normalize keyword scores
    max_kw = max(kw_scores.values()) if kw_scores and max(kw_scores.values()) > 0 else 1
    kw_normalized = {k: v / max_kw for k, v in kw_scores.items()}

    # Combine
    combined = {}
    for domain in DOMAIN_SIGNATURES:
        combined[domain] = sem_scores.get(domain, 0) * 0.6 + kw_normalized.get(domain, 0) * 0.4

    primary = max(combined, key=combined.get)
    # Secondary if close enough
    sorted_domains = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    secondary = sorted_domains[1][0] if len(sorted_domains) > 1 and sorted_domains[1][1] > sorted_domains[0][1] * 0.7 else None

    return primary, secondary, combined


def classify_outcome(text, text_embedding, outcome_embeddings):
    """Classify conversation outcome."""
    text_lower = text.lower()

    # Semantic scores
    sem_scores = {}
    for outcome, sig_emb in outcome_embeddings.items():
        sim = np.dot(text_embedding, sig_emb) / (norm(text_embedding) * norm(sig_emb) + 1e-8)
        sem_scores[outcome] = float(sim)

    # Keyword scores
    kw_scores = {}
    for outcome, keywords in OUTCOME_KEYWORDS.items():
        score = sum(text_lower.count(kw) for kw in keywords)
        kw_scores[outcome] = score

    max_kw = max(kw_scores.values()) if kw_scores and max(kw_scores.values()) > 0 else 1
    kw_normalized = {k: v / max_kw for k, v in kw_scores.items()}

    combined = {}
    for outcome in OUTCOME_SIGNATURES:
        combined[outcome] = sem_scores.get(outcome, 0) * 0.6 + kw_normalized.get(outcome, 0) * 0.4

    primary = max(combined, key=combined.get)
    return primary, combined


def compute_emotional_trajectory(user_messages):
    """Analyze emotional arc across conversation messages."""
    if not user_messages:
        return "neutral", {"positive_count": 0, "negative_count": 0}

    # Split conversation into thirds
    n = len(user_messages)
    if n < 3:
        # Too short for trajectory, just measure overall tone
        all_text = " ".join(user_messages).lower()
        pos = sum(all_text.count(w) for w in POSITIVE_WORDS)
        neg = sum(all_text.count(w) for w in NEGATIVE_WORDS)
        if pos > neg * 1.5:
            return "positive_arc", {"positive_count": pos, "negative_count": neg}
        elif neg > pos * 1.5:
            return "negative_arc", {"positive_count": pos, "negative_count": neg}
        else:
            return "neutral", {"positive_count": pos, "negative_count": neg}

    third = max(n // 3, 1)
    sections = [
        " ".join(user_messages[:third]).lower(),
        " ".join(user_messages[third:2*third]).lower(),
        " ".join(user_messages[2*third:]).lower(),
    ]

    section_scores = []
    total_pos = 0
    total_neg = 0
    for section in sections:
        pos = sum(section.count(w) for w in POSITIVE_WORDS)
        neg = sum(section.count(w) for w in NEGATIVE_WORDS)
        total_pos += pos
        total_neg += neg
        # Net sentiment (positive = positive, negative = negative)
        if pos + neg == 0:
            section_scores.append(0)
        else:
            section_scores.append((pos - neg) / (pos + neg))

    # Classify trajectory
    start, mid, end = section_scores

    if end > start + 0.3:
        trajectory = "positive_arc"  # Started bad, ended better
    elif end < start - 0.3:
        trajectory = "negative_arc"  # Started ok, ended worse
    elif all(s < -0.2 for s in section_scores):
        trajectory = "spiral"  # Consistently negative throughout
    elif abs(start - end) < 0.2 and abs(start) < 0.3:
        trajectory = "neutral"  # Flat, neither positive nor negative
    else:
        trajectory = "mixed"  # No clear pattern

    return trajectory, {"positive_count": total_pos, "negative_count": total_neg, "section_scores": [round(s, 3) for s in section_scores]}


def compute_intensity(user_text, word_count):
    """Estimate conversation intensity."""
    if not word_count or word_count == 0:
        return "low"

    text_lower = user_text.lower()

    # Intensity signals
    profanity = len(re.findall(r'\b(?:fuck|shit|damn|hell|ass|bitch|crap)\b', text_lower))
    exclamations = text_lower.count("!")
    caps_words = len(re.findall(r'\b[A-Z]{2,}\b', user_text))
    intensifiers = len(re.findall(r'\b(?:very|really|extremely|absolutely|completely|totally|literally|seriously|honestly)\b', text_lower))

    # Normalize by word count
    intensity_score = (profanity * 3 + exclamations * 2 + caps_words + intensifiers) / max(word_count / 100, 1)

    if intensity_score > 8:
        return "high"
    elif intensity_score > 3:
        return "medium"
    else:
        return "low"


def main():
    print("=" * 60)
    print("CONVERSATION CLASSIFIER")
    print("Tagging all conversations by domain, outcome, trajectory")
    print("=" * 60)

    # Load model and generate signatures
    model = get_model()

    print("\nEncoding domain signatures...")
    domain_embeddings = {
        domain: model.encode(text, show_progress_bar=False)
        for domain, text in DOMAIN_SIGNATURES.items()
    }

    print("Encoding outcome signatures...")
    outcome_embeddings = {
        outcome: model.encode(text, show_progress_bar=False)
        for outcome, text in OUTCOME_SIGNATURES.items()
    }

    # Load data
    convos = load_conversations()
    titles_db, dates_db, topics_db, word_counts_db = load_metadata()

    classifications = []
    domain_counts = {}
    outcome_counts = {}
    trajectory_counts = {}
    intensity_counts = {}

    print(f"\nClassifying {len(convos)} conversations...\n")

    for idx, convo in enumerate(convos):
        convo_id = str(idx)
        title = convo.get("title", titles_db.get(convo_id, "(untitled)"))
        date = dates_db.get(convo_id, "unknown")
        user_text = extract_user_text(convo)
        user_messages = extract_messages_by_role(convo)
        word_count = word_counts_db.get(convo_id, len(user_text.split()))
        convo_topics = topics_db.get(convo_id, [])

        # Skip very short conversations
        if word_count < 20:
            classifications.append({
                "convo_id": convo_id,
                "title": title,
                "date": date,
                "word_count": word_count,
                "domain": "unclassified",
                "domain_secondary": None,
                "outcome": "abandoned",
                "emotional_trajectory": "neutral",
                "intensity": "low",
                "skipped": True,
            })
            continue

        # Encode user text
        text_embedding = model.encode(user_text[:3000], show_progress_bar=False)

        # Classify domain
        domain, domain_secondary, domain_scores = classify_domain(
            user_text, text_embedding, domain_embeddings, convo_topics
        )

        # Classify outcome
        outcome, outcome_scores = classify_outcome(
            user_text, text_embedding, outcome_embeddings
        )

        # Emotional trajectory
        trajectory, trajectory_detail = compute_emotional_trajectory(user_messages)

        # Intensity
        intensity = compute_intensity(user_text, word_count)

        entry = {
            "convo_id": convo_id,
            "title": title,
            "date": date,
            "word_count": word_count,
            "domain": domain,
            "domain_secondary": domain_secondary,
            "domain_scores": {k: round(v, 4) for k, v in domain_scores.items()},
            "outcome": outcome,
            "outcome_scores": {k: round(v, 4) for k, v in outcome_scores.items()},
            "emotional_trajectory": trajectory,
            "trajectory_detail": trajectory_detail,
            "intensity": intensity,
            "skipped": False,
        }

        classifications.append(entry)

        # Count
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        trajectory_counts[trajectory] = trajectory_counts.get(trajectory, 0) + 1
        intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

        if (idx + 1) % 200 == 0:
            print(f"  Classified {idx + 1}/{len(convos)}...")

    # Aggregate statistics
    stats = {
        "total_classified": len([c for c in classifications if not c.get("skipped")]),
        "total_skipped": len([c for c in classifications if c.get("skipped")]),
        "domain_breakdown": dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)),
        "outcome_breakdown": dict(sorted(outcome_counts.items(), key=lambda x: x[1], reverse=True)),
        "trajectory_breakdown": dict(sorted(trajectory_counts.items(), key=lambda x: x[1], reverse=True)),
        "intensity_breakdown": dict(sorted(intensity_counts.items(), key=lambda x: x[1], reverse=True)),
    }

    # Cross-tabulations
    domain_outcome = {}
    domain_trajectory = {}
    for c in classifications:
        if c.get("skipped"):
            continue
        d = c["domain"]
        o = c["outcome"]
        t = c["emotional_trajectory"]
        key_do = f"{d}_{o}"
        key_dt = f"{d}_{t}"
        domain_outcome[key_do] = domain_outcome.get(key_do, 0) + 1
        domain_trajectory[key_dt] = domain_trajectory.get(key_dt, 0) + 1

    stats["domain_x_outcome"] = dict(sorted(domain_outcome.items(), key=lambda x: x[1], reverse=True)[:30])
    stats["domain_x_trajectory"] = dict(sorted(domain_trajectory.items(), key=lambda x: x[1], reverse=True)[:30])

    # Build output
    output = {
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "total_conversations": len(convos),
            "model_used": "all-MiniLM-L6-v2",
        },
        "statistics": stats,
        "classifications": classifications,
    }

    # Write
    out_path = BASE / "conversation_classifications.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"CLASSIFICATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total conversations: {len(convos)}")
    print(f"Classified: {stats['total_classified']}")
    print(f"Skipped (too short): {stats['total_skipped']}")
    print()

    print("Domain breakdown:")
    for domain, count in stats["domain_breakdown"].items():
        pct = count / max(stats["total_classified"], 1) * 100
        print(f"  {domain:<15} {count:>5}  ({pct:.1f}%)")
    print()

    print("Outcome breakdown:")
    for outcome, count in stats["outcome_breakdown"].items():
        pct = count / max(stats["total_classified"], 1) * 100
        print(f"  {outcome:<15} {count:>5}  ({pct:.1f}%)")
    print()

    print("Emotional trajectory:")
    for traj, count in stats["trajectory_breakdown"].items():
        pct = count / max(stats["total_classified"], 1) * 100
        print(f"  {traj:<15} {count:>5}  ({pct:.1f}%)")
    print()

    print("Intensity:")
    for intensity, count in stats["intensity_breakdown"].items():
        pct = count / max(stats["total_classified"], 1) * 100
        print(f"  {intensity:<10} {count:>5}  ({pct:.1f}%)")

    print(f"\nWrote {out_path.name}")


if __name__ == "__main__":
    main()

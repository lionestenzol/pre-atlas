import sqlite3, json, numpy as np
from pathlib import Path
from model_cache import get_model, get_model_name

print("Loading sentence-transformers model...")
model = get_model()

# Connect to database
con = sqlite3.connect("results.db")
cur = con.cursor()

# Check if embeddings exist
count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
if count == 0:
    print("\nERROR: No embeddings found in database.")
    print("Run: python init_embeddings.py first")
    exit(1)

print(f"Found {count} conversation embeddings\n")

# Load all embeddings
print("Loading embeddings from database...")
rows = cur.execute("""
    SELECT convo_id, embedding FROM embeddings
""").fetchall()

embeddings = {}
for cid, emb_blob in rows:
    embeddings[cid] = np.frombuffer(emb_blob, dtype=np.float32)

# Define semantic signatures for intent and completion
print("Generating semantic signatures...")
intent_signature = model.encode(
    "want to build plan create start trying working on incomplete unfinished need help",
    show_progress_bar=False
)
done_signature = model.encode(
    "finished completed solved shipped accomplished done resolved fixed successful",
    show_progress_bar=False
)

# Calculate semantic similarity scores
print("Scoring conversations...\n")
results = []

for cid, emb in embeddings.items():
    # Cosine similarity = dot product / (norm1 * norm2)
    from numpy.linalg import norm

    intent_sim = np.dot(emb, intent_signature) / (norm(emb) * norm(intent_signature))
    done_sim = np.dot(emb, done_signature) / (norm(emb) * norm(done_signature))

    # Also get keyword-based metrics for comparison
    trows = cur.execute("SELECT topic, weight FROM topics WHERE convo_id=?", (cid,)).fetchall()

    INTENT_TOPICS = set("want need should plan going gonna start try trying build create make learn begin".split())
    DONE_TOPICS = set("did done finished completed solved shipped fixed achieved".split())

    intent_kw = sum(w for t, w in trows if t in INTENT_TOPICS)
    done_kw = sum(w for t, w in trows if t in DONE_TOPICS)

    # Get user word count
    user_words = cur.execute(
        "SELECT SUM(words) FROM messages WHERE convo_id=? AND role='user'",
        (cid,)
    ).fetchone()[0] or 0

    # Hybrid score: combine semantic + keyword signals
    # Semantic component (scaled to 0-100)
    semantic_score = (intent_sim * 100) - (done_sim * 100)

    # Keyword component (original algorithm)
    keyword_score = user_words + (intent_kw * 30) - (done_kw * 50)

    # Weighted combination (60% semantic, 40% keyword)
    final_score = (semantic_score * 0.6) + (keyword_score * 0.4)

    # Get title
    title = cur.execute("SELECT title FROM convo_titles WHERE convo_id=?", (cid,)).fetchone()
    title = title[0] if title else "(untitled)"

    results.append({
        "convo_id": cid,
        "title": title,
        "score": float(round(final_score, 2)),
        "semantic_score": float(round(semantic_score, 2)),
        "keyword_score": float(round(keyword_score, 2)),
        "intent_similarity": float(round(intent_sim, 3)),
        "done_similarity": float(round(done_sim, 3))
    })

# Sort by final score
results.sort(key=lambda x: x["score"], reverse=True)

# Filter by quality threshold - only show meaningful open loops
MIN_SCORE_THRESHOLD = 50  # Minimum score to be considered a real open loop
quality_results = [r for r in results if r["score"] > MIN_SCORE_THRESHOLD]

if len(quality_results) == 0:
    print("No strong open loops detected (all scores below threshold).")
    print(f"Showing top 15 anyway for reference:\n")
    top = results[:15]
else:
    top = quality_results[:15]

# Export to JSON
with open("semantic_loops.json", "w", encoding="utf-8") as f:
    json.dump(top, f, indent=2)

# Display results
print("=== SEMANTIC OPEN LOOPS (Top 15) ===\n")
for i, item in enumerate(top, 1):
    print(f"{i:2}. {item['title'][:50]:<50}")
    print(f"    Score: {item['score']:8.1f}  (semantic: {item['semantic_score']:6.1f}, keyword: {item['keyword_score']:6.1f})")
    print(f"    Intent: {item['intent_similarity']:.3f}  Done: {item['done_similarity']:.3f}")
    print()

# Compare with keyword-only loops
print("\n=== COMPARISON WITH KEYWORD-ONLY LOOPS ===\n")
keyword_only = sorted(results, key=lambda x: x["keyword_score"], reverse=True)[:15]
keyword_ids = set(x["convo_id"] for x in keyword_only)
semantic_ids = set(x["convo_id"] for x in top)

only_semantic = semantic_ids - keyword_ids
only_keyword = keyword_ids - semantic_ids

if only_semantic:
    print(f"Found by SEMANTIC but not KEYWORD ({len(only_semantic)} loops):")
    for cid in only_semantic:
        item = next(x for x in results if x["convo_id"] == cid)
        print(f"  - {item['title'][:60]}")
    print()

if only_keyword:
    print(f"Found by KEYWORD but not SEMANTIC ({len(only_keyword)} loops):")
    for cid in only_keyword:
        item = next(x for x in results if x["convo_id"] == cid)
        print(f"  - {item['title'][:60]}")
    print()

print(f"Overlap: {len(semantic_ids & keyword_ids)}/15 loops match")

con.close()
print("\nWrote semantic_loops.json")

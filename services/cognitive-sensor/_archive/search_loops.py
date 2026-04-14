import sys, sqlite3, numpy as np
from model_cache import get_model

if len(sys.argv) < 2:
    print("\nUsage: python search_loops.py <query>")
    print("\nExamples:")
    print("  python search_loops.py career decisions")
    print("  python search_loops.py \"productivity systems\"")
    print("  python search_loops.py python programming")
    print("  python search_loops.py relationships")
    exit(1)

query = " ".join(sys.argv[1:])

# Validate query
if len(query.strip()) < 2:
    print("ERROR: Query too short. Please provide at least 2 characters.")
    exit(1)

# Check for meaningful content (not just stop words)
STOP_WORDS = {"a", "an", "the", "is", "it", "to", "of", "and", "or", "in", "on", "at", "for", "with", "by"}
words = query.lower().split()
meaningful_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
if len(meaningful_words) == 0:
    print("WARNING: Query contains only common words. Results may not be relevant.")
    print("Try more specific terms.\n")

print(f"Searching for: \"{query}\"\n")

# Load model
model = get_model()

# Encode query
print("Encoding query...")
query_vec = model.encode(query, show_progress_bar=False)

# Load all conversation embeddings
con = sqlite3.connect("results.db")
cur = con.cursor()

count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
if count == 0:
    print("\nERROR: No embeddings found.")
    print("Run: python init_embeddings.py first")
    exit(1)

print(f"Searching {count} conversations...\n")

rows = cur.execute("""
    SELECT e.convo_id, e.embedding, ct.title, c.date
    FROM embeddings e
    LEFT JOIN convo_titles ct ON e.convo_id = ct.convo_id
    LEFT JOIN convo_time c ON e.convo_id = c.convo_id
""").fetchall()

# Extract data into parallel arrays for batch processing
convo_ids = []
titles = []
dates = []
emb_list = []

for cid, emb_blob, title, date in rows:
    convo_ids.append(cid)
    titles.append(title if title else "(untitled)")
    dates.append(date if date else "unknown")
    emb_list.append(np.frombuffer(emb_blob, dtype=np.float32))

# Batch cosine similarity calculation
from numpy.linalg import norm

embeddings_matrix = np.array(emb_list)
norms = np.linalg.norm(embeddings_matrix, axis=1)
query_norm = np.linalg.norm(query_vec)
similarity_scores = np.dot(embeddings_matrix, query_vec) / (norms * query_norm)

# Combine results
similarities = list(zip(convo_ids, titles, dates, similarity_scores.tolist()))

# Sort by similarity (highest first)
similarities.sort(key=lambda x: x[3], reverse=True)

# Display top 15 results
print("=== SEARCH RESULTS ===\n")
for i, (cid, title, date, sim) in enumerate(similarities[:15], 1):
    # Color code by relevance
    if sim > 0.5:
        relevance = "STRONG"
    elif sim > 0.3:
        relevance = "MEDIUM"
    else:
        relevance = "WEAK"

    print(f"{i:2}. [{sim:5.1%}] {relevance:6} | {title[:55]}")
    print(f"    Date: {date}  ConvoID: {cid}")
    print()

# Statistics
avg_similarity = sum(x[3] for x in similarities) / len(similarities)
strong_matches = sum(1 for x in similarities if x[3] > 0.5)
medium_matches = sum(1 for x in similarities if 0.3 < x[3] <= 0.5)

print(f"\n=== STATISTICS ===")
print(f"Average similarity: {avg_similarity:.1%}")
print(f"Strong matches (>50%): {strong_matches}")
print(f"Medium matches (30-50%): {medium_matches}")
print(f"Weak matches (<30%): {len(similarities) - strong_matches - medium_matches}")

# Export top results as JSON
import json
top_results = [
    {
        "convo_id": cid,
        "title": title,
        "date": date,
        "similarity": round(sim, 4)
    }
    for cid, title, date, sim in similarities[:15]
]

with open("search_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "query": query,
        "results": top_results
    }, f, indent=2)

print(f"\nWrote search_results.json")

con.close()

import sqlite3, numpy as np, json
from collections import Counter

print("Loading dependencies...")
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
except ImportError:
    print("\nERROR: Required packages not installed.")
    print("Install with: pip install -r requirements.txt")
    exit(1)

# Configuration
NUM_CLUSTERS = 10  # Number of topic clusters to discover
MIN_CLUSTER_SIZE = 3  # Ignore clusters with fewer conversations

con = sqlite3.connect("results.db")
cur = con.cursor()

# Check if embeddings exist
count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
if count == 0:
    print("\nERROR: No embeddings found in database.")
    print("Run: python init_embeddings.py first")
    exit(1)

print(f"Found {count} conversation embeddings")
print(f"Clustering into {NUM_CLUSTERS} topic groups...\n")

# Load all embeddings and metadata
rows = cur.execute("""
    SELECT e.convo_id, e.embedding, ct.title, c.date
    FROM embeddings e
    LEFT JOIN convo_titles ct ON e.convo_id = ct.convo_id
    LEFT JOIN convo_time c ON e.convo_id = c.convo_id
""").fetchall()

# Prepare data
convo_ids = []
titles = []
dates = []
embeddings_matrix = []

for cid, emb_blob, title, date in rows:
    convo_ids.append(cid)
    titles.append(title if title else "(untitled)")
    dates.append(date if date else "unknown")
    embeddings_matrix.append(np.frombuffer(emb_blob, dtype=np.float32))

embeddings_matrix = np.array(embeddings_matrix)

# Perform K-means clustering
print("Running K-means clustering...")
kmeans = KMeans(n_clusters=NUM_CLUSTERS, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(embeddings_matrix)

# Organize conversations by cluster
clusters = {}
for i, cluster_id in enumerate(cluster_labels):
    if cluster_id not in clusters:
        clusters[cluster_id] = []
    clusters[cluster_id].append({
        "convo_id": convo_ids[i],
        "title": titles[i],
        "date": dates[i]
    })

# For each cluster, find most representative keywords
print("\n=== DISCOVERED TOPIC CLUSTERS ===\n")

cluster_summaries = []

for cluster_id in sorted(clusters.keys()):
    convos = clusters[cluster_id]

    if len(convos) < MIN_CLUSTER_SIZE:
        continue  # Skip tiny clusters

    print(f"CLUSTER {cluster_id + 1} ({len(convos)} conversations)")
    print("-" * 70)

    # Get all topics for conversations in this cluster
    all_topics = []
    for convo in convos:
        cid = convo["convo_id"]
        topic_rows = cur.execute(
            "SELECT topic, weight FROM topics WHERE convo_id=?",
            (cid,)
        ).fetchall()
        for topic, weight in topic_rows:
            all_topics.extend([topic] * weight)  # Repeat by weight

    # Find most common topics
    topic_counts = Counter(all_topics)
    top_keywords = [t for t, _ in topic_counts.most_common(5)]

    print(f"Keywords: {', '.join(top_keywords)}")
    print()

    # Show sample conversations
    print("Sample conversations:")
    for convo in convos[:5]:  # Show first 5
        print(f"  • {convo['title'][:60]}  ({convo['date']})")

    print()

    cluster_summaries.append({
        "cluster_id": int(cluster_id + 1),
        "size": int(len(convos)),
        "keywords": top_keywords,
        "conversations": convos
    })

# Export to JSON
with open("topic_clusters.json", "w", encoding="utf-8") as f:
    json.dump(cluster_summaries, f, indent=2)

# Summary statistics
print("\n=== CLUSTER STATISTICS ===")
print(f"Total clusters: {NUM_CLUSTERS}")
print(f"Clusters with >={MIN_CLUSTER_SIZE} conversations: {len(cluster_summaries)}")
print(f"Average cluster size: {count / NUM_CLUSTERS:.1f} conversations")

largest_cluster = max(cluster_summaries, key=lambda x: x["size"])
print(f"Largest cluster: #{largest_cluster['cluster_id']} with {largest_cluster['size']} conversations")
print(f"Keywords: {', '.join(largest_cluster['keywords'])}")

print(f"\nWrote topic_clusters.json")

con.close()

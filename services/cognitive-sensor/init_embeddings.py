import json, sqlite3, numpy as np
from pathlib import Path
from datetime import datetime
from model_cache import get_model, get_model_name

# Configuration
DB_JSON = Path("memory_db.json")
OUT_DB = Path("results.db")
MAX_TEXT_LENGTH = 5000  # Truncate long conversations

# Load model (downloads on first run, ~80MB)
print("Loading sentence-transformers model...")
print(f"Initializing model: {get_model_name()}")
model = get_model()

# Create embeddings table
con = sqlite3.connect(OUT_DB)
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS embeddings (
    convo_id TEXT PRIMARY KEY,
    embedding BLOB,
    model TEXT,
    created_at TEXT,
    text_length INTEGER
)
""")

# Check if embeddings already exist
existing = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
if existing > 0:
    response = input(f"\nFound {existing} existing embeddings. Regenerate all? (y/n): ")
    if response.lower() != 'y':
        print("Aborted.")
        exit(0)
    cur.execute("DELETE FROM embeddings")
    con.commit()

# Load conversations
print(f"Loading {DB_JSON}...")
data = json.load(open(DB_JSON, encoding="utf-8"))
total = len(data)

print(f"Generating embeddings for {total} conversations...")
print("(This may take 2-3 minutes on first run)\n")

rows = []
for idx, convo in enumerate(data):
    cid = str(idx)

    # Concatenate all messages in conversation
    text_parts = []
    for m in convo.get("messages", []):
        msg_text = m.get("text", "")
        if isinstance(msg_text, dict):
            msg_text = str(msg_text)
        text_parts.append(str(msg_text))

    full_text = " ".join(text_parts)

    # Truncate if too long
    text_for_embedding = full_text[:MAX_TEXT_LENGTH]

    # Generate embedding
    embedding = model.encode(text_for_embedding, show_progress_bar=False)

    # Store as binary blob
    rows.append((
        cid,
        embedding.tobytes(),
        get_model_name(),
        datetime.now().isoformat(),
        len(full_text)
    ))

    # Progress indicator
    if (idx + 1) % 50 == 0:
        print(f"  {idx + 1}/{total} conversations embedded...")

# Insert all at once
print("\nSaving to database...")
cur.executemany("INSERT INTO embeddings VALUES (?,?,?,?,?)", rows)
con.commit()
con.close()

print(f"\n✓ Successfully generated {len(rows)} embeddings")
print(f"  Model: {get_model_name()}")
print(f"  Dimensions: 384")
print(f"  Database size increase: ~{len(rows) * 384 * 4 / 1024 / 1024:.1f} MB")
print("\nNext steps:")
print("  - Run: python semantic_loops.py")
print("  - Run: python search_loops.py <query>")
print("  - Run: python cluster_topics.py")

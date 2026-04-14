"""
init_message_embeddings.py — Phase 2: Message-Level Embeddings

Reads memory_db.json, generates one 384-dim embedding per eligible message,
stores in message_embeddings table within results.db.

Eligibility: role != 'system' AND word_count >= 3
Skip: system messages (0 words), empty frames, sub-3-word messages
Truncate: 2000 chars max per message (~512 tokens for MiniLM)

Usage:
    python init_message_embeddings.py
"""

import json, sqlite3, numpy as np
from pathlib import Path
from datetime import datetime
from model_cache import get_model, get_model_name

BASE = Path(__file__).parent.resolve()
DB_JSON = BASE / "memory_db.json"
DB_FILE = BASE / "results.db"

MIN_WORDS = 3
BATCH_SIZE = 256
MAX_TEXT_CHARS = 2000


def main():
    # Load model
    print("Loading sentence-transformers model...")
    model = get_model()
    model_name = get_model_name()
    print(f"  Model: {model_name}")

    # Connect to database
    con = sqlite3.connect(str(DB_FILE))
    cur = con.cursor()

    # Create table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS message_embeddings (
        msg_id TEXT PRIMARY KEY,
        convo_id TEXT NOT NULL,
        msg_index INTEGER NOT NULL,
        role TEXT NOT NULL,
        embedding BLOB NOT NULL,
        model TEXT NOT NULL,
        text_length INTEGER NOT NULL,
        word_count INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    # Check for existing data
    existing = cur.execute("SELECT COUNT(*) FROM message_embeddings").fetchone()[0]
    if existing > 0:
        response = input(f"\nFound {existing} existing message embeddings. Regenerate all? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            con.close()
            return
        cur.execute("DELETE FROM message_embeddings")
        con.commit()
        print("Cleared existing embeddings.")

    # Load conversations
    print(f"Loading {DB_JSON.name}...")
    data = json.load(open(DB_JSON, encoding="utf-8"))
    total_convos = len(data)
    print(f"  {total_convos} conversations loaded")

    # Collect eligible messages
    print("Collecting eligible messages...")
    messages = []  # list of (msg_id, convo_id, msg_index, role, text, text_length, word_count)
    skip_system = 0
    skip_short = 0

    for convo_idx, convo in enumerate(data):
        cid = str(convo_idx)
        for msg_idx, msg in enumerate(convo.get("messages", [])):
            role = msg.get("role", "unknown")
            text = msg.get("text", "")
            if isinstance(text, dict):
                text = str(text)
            text = str(text)

            word_count = len(text.split())

            if role == "system":
                skip_system += 1
                continue
            if word_count < MIN_WORDS:
                skip_short += 1
                continue

            msg_id = f"{cid}_{msg_idx}"
            messages.append((msg_id, cid, msg_idx, role, text, len(text), word_count))

    total_eligible = len(messages)
    total_skipped = skip_system + skip_short
    print(f"  Eligible: {total_eligible}")
    print(f"  Skipped:  {total_skipped} (system={skip_system}, <{MIN_WORDS} words={skip_short})")

    # Role breakdown
    role_counts = {}
    for _, _, _, role, _, _, _ in messages:
        role_counts[role] = role_counts.get(role, 0) + 1
    for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
        print(f"    {role}: {count}")

    # Batch encode
    print(f"\nEncoding {total_eligible} messages (batch_size={BATCH_SIZE})...")
    start_time = datetime.now()

    rows = []
    now = datetime.now().isoformat()

    for batch_start in range(0, total_eligible, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_eligible)
        batch = messages[batch_start:batch_end]

        # Extract and truncate texts
        texts = [m[4][:MAX_TEXT_CHARS] for m in batch]

        # Encode batch
        embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False)

        # Build rows
        for i, m in enumerate(batch):
            msg_id, cid, msg_idx, role, _, text_length, word_count = m
            rows.append((
                msg_id,
                cid,
                msg_idx,
                role,
                embeddings[i].tobytes(),
                model_name,
                text_length,
                word_count,
                now,
            ))

        # Progress
        done = batch_end
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = done / elapsed if elapsed > 0 else 0
        remaining = (total_eligible - done) / rate if rate > 0 else 0
        print(f"  {done:>6}/{total_eligible}  ({rate:.0f} msgs/sec, ~{remaining:.0f}s remaining)")

    # Bulk insert
    print("\nSaving to database...")
    cur.executemany(
        "INSERT INTO message_embeddings VALUES (?,?,?,?,?,?,?,?,?)",
        rows
    )
    con.commit()

    # Create indexes
    print("Creating indexes...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_me_convo ON message_embeddings(convo_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_me_role ON message_embeddings(role)")
    con.commit()
    con.close()

    elapsed = (datetime.now() - start_time).total_seconds()
    storage_mb = total_eligible * 384 * 4 / 1024 / 1024

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Embedded: {total_eligible} messages")
    print(f"  Model: {model_name} (384 dimensions)")
    print(f"  Storage: ~{storage_mb:.1f} MB")
    print(f"\nNext: python build_cognitive_atlas.py")


if __name__ == "__main__":
    main()

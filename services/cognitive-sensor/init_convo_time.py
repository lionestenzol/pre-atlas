import json, sqlite3, os
from pathlib import Path
from datetime import datetime

# Base directory is the same folder as this script
BASE = Path(__file__).parent.resolve()

# RAW_JSON: Set via environment variable or place conversations.json in this folder
RAW_JSON = Path(os.environ.get("CONVERSATIONS_JSON", BASE / "conversations.json"))
DB = sqlite3.connect(BASE / "results.db")
cur = DB.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS convo_time (
    convo_id TEXT,
    date TEXT
)
""")

print("Loading raw conversations.json...")
data = json.load(open(RAW_JSON, encoding="utf-8"))

rows = []

def extract_date(c):
    # Try common export fields; fall back to empty if not found
    for k in ("create_time", "created_at", "update_time", "updated_at", "timestamp", "time"):
        if k in c:
            try:
                # If numeric epoch
                if isinstance(c[k], (int, float)):
                    return datetime.fromtimestamp(c[k]).strftime("%Y-%m-%d")
                # If string date
                return str(c[k])[:10]
            except:
                pass
    return None

# Generate simple sequential IDs to match memory_db structure
for idx, c in enumerate(data):
    cid = str(idx)  # Simple index-based ID
    d = extract_date(c)
    if d:
        rows.append((cid, d))

cur.executemany("INSERT INTO convo_time VALUES (?,?)", rows)
DB.commit()
DB.close()

print("Loaded", len(rows), "conversation dates.")

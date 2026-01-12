import json, sqlite3
from pathlib import Path

DB_JSON = Path("memory_db.json")
OUT_DB = Path("results.db")

print("Loading memory_db.json...")
data = json.load(open(DB_JSON, encoding="utf-8"))

con = sqlite3.connect(OUT_DB)
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    convo_id TEXT,
    role TEXT,
    words INTEGER,
    chars INTEGER
)
""")

rows = []
for idx, c in enumerate(data):
    cid = str(idx)  # Use same index-based ID as convo_time and topics
    for m in c["messages"]:
        txt = m.get("text", "")
        if isinstance(txt, dict):
            txt = str(txt)
        words = len(str(txt).split())
        chars = len(str(txt))
        rows.append((cid, m["role"], words, chars))

cur.executemany("INSERT INTO messages VALUES (?,?,?,?)", rows)
con.commit()
con.close()

print("results.db created with", len(rows), "rows.")

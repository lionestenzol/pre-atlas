import json, sqlite3, re
from collections import Counter
from pathlib import Path

DB_JSON = Path("memory_db.json")
DB = sqlite3.connect("results.db")
cur = DB.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS topics (
    convo_id TEXT,
    topic TEXT,
    weight INTEGER
)
""")

print("Loading memory_db.json...")
data = json.load(open(DB_JSON, encoding="utf-8"))

STOP = set("""
the and a to of in for on with is are was were be been being it that this i you he she they we my your our me him her them
""".split())

def normalize(t):
    t = re.sub(r"[^a-zA-Z0-9 ]", " ", str(t).lower())
    return [w for w in t.split() if w not in STOP and len(w) > 2]

rows = []
for idx, c in enumerate(data):
    cid = str(idx)  # Use same index-based ID as convo_time
    words = []
    for m in c["messages"]:
        words += normalize(m.get("text",""))
    counts = Counter(words)
    for w, cnt in counts.most_common(10):
        rows.append((cid, w, cnt))

cur.executemany("INSERT INTO topics VALUES (?,?,?)", rows)
DB.commit()
DB.close()

print("Topics loaded.")

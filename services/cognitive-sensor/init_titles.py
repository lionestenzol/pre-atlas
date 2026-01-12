import json, sqlite3
from pathlib import Path

data = json.load(open("memory_db.json", encoding="utf-8"))

con = sqlite3.connect("results.db")
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS convo_titles (
    convo_id TEXT,
    title TEXT
)
""")

cur.execute("DELETE FROM convo_titles")

rows = []
for idx, c in enumerate(data):
    cid = str(idx)
    title = c.get("title","").strip()
    rows.append((cid, title))

cur.executemany("INSERT INTO convo_titles VALUES (?,?)", rows)
con.commit()
con.close()

print("Loaded", len(rows), "conversation titles.")

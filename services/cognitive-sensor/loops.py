import sqlite3, json
from pathlib import Path
from atlas_config import ROUTING
from atomic_write import atomic_write_json

INTENT_TOPICS = set("want need should plan going gonna start try trying build create make learn begin".split())
DONE_TOPICS   = set("did done finished completed solved shipped fixed achieved".split())
MIN_LOOP_SCORE = ROUTING["min_loop_score"]

con = sqlite3.connect("results.db")
cur = con.cursor()

# Exclude loops already decided (CLOSE or ARCHIVE) via decide.py
try:
    decided = {r[0] for r in cur.execute(
        "SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE','ARCHIVE')"
    ).fetchall()}
except sqlite3.OperationalError:
    decided = set()  # table doesn't exist yet

# Also exclude loops closed via delta-kernel's /api/law/close_loop endpoint.
# This bridges the gap: delta-kernel writes closures to loops_closed.json,
# but loops.py regenerates loops_latest.json from results.db which has no
# record of those closures. Without this, closed loops reappear on next run.
closed_path = Path("loops_closed.json")
if closed_path.exists():
    try:
        closed_entries = json.load(open(closed_path, encoding="utf-8"))
        for entry in closed_entries:
            lid = entry.get("loop_id", "")
            if lid:
                decided.add(lid)
    except (json.JSONDecodeError, KeyError):
        pass  # best-effort — file may be empty or malformed

rows = cur.execute("SELECT convo_id, role, words FROM messages").fetchall()

by_convo = {}
for cid, role, words in rows:
    if cid in decided:
        continue
    by_convo.setdefault(cid, {"user_words": 0})
    if role == "user":
        by_convo[cid]["user_words"] += words

results = []
for cid, info in by_convo.items():
    user_words = info["user_words"]

    trows = cur.execute("SELECT topic, weight FROM topics WHERE convo_id=?", (cid,)).fetchall()
    intent_w = sum(w for t, w in trows if t in INTENT_TOPICS)
    done_w   = sum(w for t, w in trows if t in DONE_TOPICS)

    score = user_words + intent_w * 30 - done_w * 50

    title = cur.execute("SELECT title FROM convo_titles WHERE convo_id=?", (cid,)).fetchone()
    title = title[0] if title else "(untitled)"

    results.append((cid, title, int(score)))

results.sort(key=lambda x: x[2], reverse=True)
top = [r for r in results if r[2] >= MIN_LOOP_SCORE]

payload = [{"convo_id": cid, "title": title, "score": score} for cid, title, score in top]

atomic_write_json(Path("loops_latest.json"), payload)

print("\n=== OPEN LOOPS (Likely Unfinished) ===\n")
for item in payload[:10]:
    print(f'{item["title"]:<45}  score={item["score"]}')

con.close()
print("\nWrote loops_latest.json")

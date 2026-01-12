import sqlite3, json

INTENT_TOPICS = set("want need should plan going gonna start try trying build create make learn begin".split())
DONE_TOPICS   = set("did done finished completed solved shipped fixed achieved".split())

con = sqlite3.connect("results.db")
cur = con.cursor()

rows = cur.execute("SELECT convo_id, role, words FROM messages").fetchall()

by_convo = {}
for cid, role, words in rows:
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
top = results[:15]

payload = [{"convo_id": cid, "title": title, "score": score} for cid, title, score in top]

with open("loops_latest.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

print("\n=== OPEN LOOPS (Likely Unfinished) ===\n")
for item in payload[:10]:
    print(f'{item["title"]:<45}  score={item["score"]}')

con.close()
print("\nWrote loops_latest.json")

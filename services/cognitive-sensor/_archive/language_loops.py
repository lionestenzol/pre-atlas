import json, re
from collections import Counter
from pathlib import Path

DB = Path("memory_db.json")
data = json.load(open(DB, encoding="utf-8"))

def normalize(t):
    if isinstance(t, dict):
        t = json.dumps(t)
    if not isinstance(t, str):
        t = str(t)
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

ngrams = Counter()

for c in data:
    for m in c["messages"]:
        if m["role"] == "user":
            text = normalize(m["text"])
            words = text.split()
            for n in range(3, 7):   # 3–6 word phrases
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i:i+n])
                    ngrams[phrase] += 1

with open("LANGUAGE_LOOPS.md", "w", encoding="utf-8") as f:
    f.write("# YOUR MOST REPEATED PHRASES\n\n")
    for phrase, count in ngrams.most_common(300):
        if count >= 10:
            f.write(f"{count}x — {phrase}\n")

print("LANGUAGE_LOOPS.md generated.")

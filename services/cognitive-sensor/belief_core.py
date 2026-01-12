import json, re
from collections import Counter, defaultdict
from pathlib import Path

DB = Path("memory_db.json")
data = json.load(open(DB, encoding="utf-8"))

def normalize(t):
    if isinstance(t, dict):
        t = json.dumps(t)
    if not isinstance(t, str):
        t = str(t)
    t = t.lower()
    t = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s']", "", t)).strip()
    return t

BELIEF_PATTERNS = [
    r"\bi am\b", r"\bi'm\b", r"\bi am not\b", r"\bi'm not\b",
    r"\bi can\b", r"\bi cant\b", r"\bi cannot\b",
    r"\bi always\b", r"\bi never\b",
    r"\bpeople are\b", r"\blife is\b", r"\bmoney is\b", r"\bwork is\b",
    r"\bsuccess is\b", r"\bfailure is\b", r"\bi deserve\b", r"\bi dont deserve\b"
]

hits = Counter()
examples = defaultdict(list)

for c in data:
    for m in c["messages"]:
        if m["role"] == "user":
            text = normalize(m["text"])
            for pat in BELIEF_PATTERNS:
                if re.search(pat, text):
                    clause = text[:120]
                    hits[clause] += 1
                    if len(examples[clause]) < 3:
                        examples[clause].append(text)

with open("BELIEF_CORE.md", "w", encoding="utf-8") as f:
    f.write("# YOUR CORE BELIEF RULES\n\n")
    for rule, count in hits.most_common(200):
        f.write(f"{count}x — {rule}\n")
        for ex in examples[rule]:
            f.write(f"   • {ex}\n")
        f.write("\n")

print("BELIEF_CORE.md generated.")

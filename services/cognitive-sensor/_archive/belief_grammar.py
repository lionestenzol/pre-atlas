import json, re
from collections import Counter, defaultdict
from pathlib import Path

DB = Path("memory_db.json")
data = json.load(open(DB, encoding="utf-8"))

def norm(t):
    if isinstance(t, dict):
        t = json.dumps(t)
    if not isinstance(t, str):
        t = str(t)
    t = t.lower()
    t = re.sub(r"[^a-z0-9\s']", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

PATTERNS = [
    r"\bi am not\b", r"\bi am\b", r"\bi'm not\b", r"\bi'm\b",
    r"\bi cant\b", r"\bi can\b",
    r"\bi always\b", r"\bi never\b",
    r"\bi shouldnt\b", r"\bi should\b",
    r"\bpeople are\b", r"\blife is\b", r"\bmoney is\b", r"\bwork is\b"
]

hits = Counter()
examples = defaultdict(list)

for c in data:
    for m in c["messages"]:
        if m["role"] == "user":
            text = norm(m["text"])
            for pat in PATTERNS:
                if re.search(pat, text):
                    # capture the clause up to ~120 chars for readability
                    snippet = text[:120]
                    hits[snippet] += 1
                    if len(examples[snippet]) < 3:
                        examples[snippet].append(text)

with open("BELIEF_RULES.md", "w", encoding="utf-8") as f:
    f.write("# BELIEF GRAMMAR — YOUR QUIET RULES\n\n")
    for rule, count in hits.most_common(200):
        f.write(f"{count}x — {rule}\n")
        for ex in examples[rule]:
            f.write(f"   • {ex}\n")
        f.write("\n")

print("BELIEF_RULES.md generated.")

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
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

# Phrase groups
INTENT = re.compile(r"\b(i want to|i need to|i plan to|my goal is|im trying to)\b")
RESOLUTION = re.compile(r"\b(i did|i finished|i solved|it worked|im done|completed)\b")
STALL = re.compile(r"\b(im stuck|im confused|overwhelmed|burned out|i cant|i don t know what to do)\b")
ACCEL = re.compile(r"\b(lets do|im going to|im committing|decided to|shipping|launching|final)\b")

intent_hits = Counter()
resolution_hits = Counter()
stall_hits = Counter()
accel_hits = Counter()

latencies = []  # number of messages between intent and resolution within same convo

for c in data:
    msgs = [normalize(m["text"]) for m in c["messages"] if m["role"] == "user"]

    last_intent_idx = None
    for i, txt in enumerate(msgs):
        if INTENT.search(txt):
            last_intent_idx = i
            intent_hits[txt[:80]] += 1

        if last_intent_idx is not None and RESOLUTION.search(txt):
            latencies.append(i - last_intent_idx)
            resolution_hits[txt[:80]] += 1
            last_intent_idx = None

        if STALL.search(txt):
            stall_hits[txt[:80]] += 1

        if ACCEL.search(txt):
            accel_hits[txt[:80]] += 1

def write_ranked(fname, title, counter, min_count=5):
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        for k, v in counter.most_common(200):
            if v >= min_count:
                f.write(f"{v}x — {k}\n")

# Write outputs
write_ranked("STALL_SIGNATURES.md", "STALL SIGNATURES (predictors of looping / burnout)", stall_hits, min_count=5)
write_ranked("ACCELERATION_PHRASES.md", "ACCELERATION PHRASES (predictors of commitment)", accel_hits, min_count=5)
write_ranked("DECISION_ENGINE.md", "INTENT / RESOLUTION PHRASES (decision flow)", intent_hits, min_count=5)

# Append latency stats
with open("DECISION_ENGINE.md", "a", encoding="utf-8") as f:
    if latencies:
        avg_lat = round(sum(latencies)/len(latencies), 2)
        f.write(f"\n\nAverage messages from intent → resolution: {avg_lat}\n")
        f.write(f"Min latency: {min(latencies)}\n")
        f.write(f"Max latency: {max(latencies)}\n")
    else:
        f.write("\n\nNo intent→resolution pairs detected.\n")

print("Generated: DECISION_ENGINE.md, STALL_SIGNATURES.md, ACCELERATION_PHRASES.md")


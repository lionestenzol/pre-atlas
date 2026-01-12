import json, re
from collections import Counter
from pathlib import Path

DB = Path("memory_db.json")

print("Loading memory_db.json...")

data = json.load(open(DB, encoding="utf-8"))

def normalize_text(t):
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        return json.dumps(t)
    return str(t)

total_convos = len(data)
message_counts = []
user_word_counts = []
assistant_word_counts = []
all_user_text = []

for c in data:
    msgs = c["messages"]
    message_counts.append(len(msgs))

    for m in msgs:
        text = normalize_text(m["text"])
        words = len(text.split())

        if m["role"] == "user":
            user_word_counts.append(words)
            all_user_text.append(text)
        else:
            assistant_word_counts.append(words)

avg_msgs = round(sum(message_counts)/len(message_counts),2)
longest = max(message_counts)
shortest = min(message_counts)

avg_user_words = round(sum(user_word_counts)/len(user_word_counts),2)
avg_assistant_words = round(sum(assistant_word_counts)/len(assistant_word_counts),2)

verbs = Counter(re.findall(r"\b(want|need|should|plan|think|feel|learn|realize|build|create|make|fix)\b"," ".join(all_user_text).lower()))
topics = Counter(re.findall(r"\b(ai|money|school|business|relationship|project|idea|code|life|health)\b"," ".join(all_user_text).lower()))

report = f"""
# MY COGNITIVE PROFILE

Total conversations: {total_convos}
Average messages per conversation: {avg_msgs}
Longest conversation: {longest} messages
Shortest conversation: {shortest} messages

Average user message length (words): {avg_user_words}
Average assistant message length (words): {avg_assistant_words}

## Your most common action verbs
{verbs.most_common(10)}

## Your most common topic words
{topics.most_common(10)}
"""

Path("MY_COGNITIVE_PROFILE.md").write_text(report, encoding="utf-8")

print("MY_COGNITIVE_PROFILE.md generated.")

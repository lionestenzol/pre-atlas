import sqlite3, json
from datetime import datetime, timedelta

DB = sqlite3.connect("results.db")
cur = DB.cursor()

# Load current open loops
try:
    loops = json.load(open("loops_latest.json", encoding="utf-8"))
except:
    print("Run loops.py first.")
    exit()

# Filter out closed/archived loops
closed = {r[0] for r in cur.execute("SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE', 'ARCHIVE')")}
loops = [l for l in loops if l["convo_id"] not in closed]

if not loops:
    print("No open loops found.")
    exit()

# Pick the *oldest* high-score loop
cid = loops[0]["convo_id"]
title = loops[0]["title"]
score = loops[0]["score"]

# Get last activity date
row = cur.execute("SELECT date FROM convo_time WHERE convo_id=?", (cid,)).fetchone()
last = row[0] if row else "unknown"

message = f"""
WEEKLY RESURFACER — {datetime.now().strftime('%Y-%m-%d')}

UNRESOLVED LOOP:
{title}

Score: {score}
Last active: {last}

Choose ONE:
[ ] CLOSE
[ ] CONTINUE
[ ] ARCHIVE
"""

with open("RESURFACER_LOG.md", "a", encoding="utf-8") as f:
    f.write("\n\n" + message)

print("Resurfacer logged:", title)

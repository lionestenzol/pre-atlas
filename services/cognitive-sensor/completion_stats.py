import sqlite3
from datetime import datetime, timedelta

con = sqlite3.connect("results.db")
cur = con.cursor()

today = datetime.now().strftime("%Y-%m-%d")
week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

week = cur.execute("""
SELECT decision, COUNT(*) FROM loop_decisions
WHERE date >= ?
GROUP BY decision
""", (week_ago,)).fetchall()

lifetime = cur.execute("""
SELECT decision, COUNT(*) FROM loop_decisions
GROUP BY decision
""").fetchall()

week = dict(week)
life = dict(lifetime)

closed_week = week.get("CLOSE",0)
arch_week   = week.get("ARCHIVE",0)
closed_life = life.get("CLOSE",0)
arch_life   = life.get("ARCHIVE",0)

ratio = round(closed_life / max(1,(closed_life+arch_life)) * 100, 1)

payload = {
    "closed_week": closed_week,
    "archived_week": arch_week,
    "closed_life": closed_life,
    "archived_life": arch_life,
    "closure_ratio": ratio
}

import json
open("completion_stats.json","w").write(json.dumps(payload,indent=2))

print("completion_stats.json updated.")

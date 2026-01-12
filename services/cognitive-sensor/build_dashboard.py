import json, sqlite3, html
from pathlib import Path

STATE_FILE = Path("STATE_HISTORY.md")
LOOPS_FILE = Path("loops_latest.json")
STATS_FILE = Path("completion_stats.json")
DB_FILE = Path("results.db")
OUT_FILE = Path("dashboard.html")

def latest_state_md():
    if not STATE_FILE.exists():
        return "STATE_HISTORY.md not found. Run: python reporter.py"
    text = STATE_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return "STATE_HISTORY.md is empty. Run: python reporter.py"
    # show the last snapshot block (last heading)
    parts = text.split("\n## ")
    if len(parts) == 1:
        return text[-4000:]
    last = "## " + parts[-1]
    return last[-6000:]  # cap for sanity

def load_loops():
    if not LOOPS_FILE.exists():
        return []
    try:
        return json.loads(LOOPS_FILE.read_text(encoding="utf-8"))
    except:
        return []

def load_stats():
    if not STATS_FILE.exists():
        return None
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except:
        return None

def stable_topics(limit=15):
    # Stop words to filter out
    STOP = set("""
        like can just what not but how their have when because about could might his her him them
        that this there then than more some very will would should may also even now get got make
        made going way back down out over only other into through where which been being all any
        both each few many most much such same too well say said did had has does done
    """.split())

    con = sqlite3.connect(str(DB_FILE))
    cur = con.cursor()
    rows = cur.execute("""
        SELECT topic, SUM(weight) AS total
        FROM topics
        GROUP BY topic
        ORDER BY total DESC
        LIMIT ?
    """, (limit * 3,)).fetchall()  # Fetch more to account for filtering
    con.close()

    # Filter out stop words and return top N
    filtered = [(t, total) for t, total in rows if t not in STOP]
    return filtered[:limit]

state = latest_state_md()
loops = load_loops()
stats = load_stats()
anchors = stable_topics(15)

# Minimal HTML
def pre(s):  # preserve formatting
    return f"<pre>{html.escape(s)}</pre>"

loops_lines = []
if loops:
    for i, item in enumerate(loops[:10], 1):
        title = item.get("title", "(untitled)")
        score = item.get("score", 0)
        loops_lines.append(f'{i:>2}. {title:<45}  score={score}')
else:
    loops_lines.append("No loops_latest.json found. Run: python loops.py")

stats_lines = []
if stats:
    stats_lines = [
        f"Closed this week:   {stats['closed_week']}",
        f"Archived this week: {stats['archived_week']}",
        f"Closed lifetime:    {stats['closed_life']}",
        f"Archived lifetime:  {stats['archived_life']}",
        f"Closure ratio:      {stats['closure_ratio']}%"
    ]
else:
    stats_lines = ["Run: python completion_stats.py"]

anchors_lines = [f"{t:<18} {total}" for t, total in anchors] if anchors else ["No topics found."]

page = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>My Cognitive Dashboard</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; color: #111; }}
    h1 {{ font-size: 20px; margin: 0 0 12px; }}
    h2 {{ font-size: 14px; margin: 22px 0 8px; }}
    .box {{ border: 1px solid #ddd; border-radius: 10px; padding: 12px; background: #fff; }}
    pre {{ margin: 0; white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; line-height: 1.35; }}
    .muted {{ color: #666; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>My Cognitive Dashboard</h1>
  <div class="muted">Generated from results.db + STATE_HISTORY.md</div>

  <h2>Latest State Snapshot</h2>
  <div class="box">{pre(state)}</div>

  <h2>Open Loops (Top 10)</h2>
  <div class="box">{pre("\\n".join(loops_lines))}</div>

  <h2>Completion Analytics</h2>
  <div class="box">{pre("\\n".join(stats_lines))}</div>

  <h2>Lifetime Anchors (Top 15 Topics)</h2>
  <div class="box">{pre("\\n".join(anchors_lines))}</div>

  <div class="muted" style="margin-top:18px;">
    To refresh: run <b>python loops.py</b>, <b>python reporter.py</b>, then <b>python build_dashboard.py</b>.
  </div>
</body>
</html>
"""

OUT_FILE.write_text(page, encoding="utf-8")
print("Built dashboard.html")

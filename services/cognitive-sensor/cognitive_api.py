import sqlite3, json
from datetime import datetime, timedelta

DB = sqlite3.connect("results.db")
cur = DB.cursor()

def query(q, args=()):
    return cur.execute(q, args).fetchall()

def get_state():
    row = query("SELECT MIN(date), MAX(date) FROM convo_time")[0]
    return {
        "first_activity": row[0],
        "last_activity": row[1],
        "total_convos": query("SELECT COUNT(*) FROM convo_time")[0][0]
    }

def get_open_loops(limit=5):
    try:
        loops = json.load(open("loops_latest.json", encoding="utf-8"))
        # Filter out closed/archived
        closed = {r[0] for r in query("SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE', 'ARCHIVE')")}
        loops = [l for l in loops if l["convo_id"] not in closed]
        return loops[:limit]
    except:
        return []

def get_closure_backlog():
    try:
        loops = json.load(open("loops_latest.json", encoding="utf-8"))
        closed_ids = {r[0] for r in query("SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE','ARCHIVE')")}
        open_loops = len([l for l in loops if l["convo_id"] not in closed_ids])
    except:
        open_loops = 0

    truly_closed = query("SELECT COUNT(*) FROM loop_decisions WHERE decision = 'CLOSE'")[0][0]
    archived = query("SELECT COUNT(*) FROM loop_decisions WHERE decision = 'ARCHIVE'")[0][0]
    decided = truly_closed + archived

    # decision_ratio: how much of the backlog has been triaged (CLOSE + ARCHIVE vs open)
    decision_ratio = round((decided / max(open_loops + decided, 1)) * 100, 2)

    # closure_quality: of the ones you "finished," how many actually got CLOSED vs just ARCHIVED
    # This is the honest metric — archiving is avoidance, not closure
    closure_quality = round((truly_closed / max(decided, 1)) * 100, 2)

    return {
        "open": open_loops,
        "closed": decided,              # total decisions (backward compat)
        "truly_closed": truly_closed,   # real closures only
        "archived": archived,           # parked, not done
        "ratio": decision_ratio,        # backward compat: % of backlog triaged
        "closure_quality": closure_quality,  # NEW: % of finished that are truly closed
    }

def get_drift():
    recent = query("""
        SELECT topic, SUM(weight) FROM topics t
        JOIN convo_time c ON t.convo_id = c.convo_id
        WHERE c.date >= (SELECT date(MAX(date), '-90 day') FROM convo_time)
        GROUP BY topic ORDER BY SUM(weight) DESC LIMIT 10
    """)
    return dict(recent)

if __name__ == "__main__":
    print(json.dumps({
        "state": get_state(),
        "loops": get_open_loops(),
        "drift": get_drift(),
        "closure": get_closure_backlog()
    }, indent=2))

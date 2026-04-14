"""
close_loop.py -- The system helps you close loops, not just track them.

Usage:
  python close_loop.py                     # Triage all open loops one by one
  python close_loop.py 143                 # Analyze loop 143, recommend action
  python close_loop.py 143 CLOSE           # Skip analysis, just close it
  python close_loop.py 143 ARCHIVE         # Skip analysis, just archive it
  python close_loop.py --list              # Show all open loops
"""

import sqlite3
import subprocess
import urllib.request
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.resolve()
DB_PATH = BASE / "results.db"
MEMORY_PATH = BASE / "memory_db.json"
CLASSIFICATIONS_PATH = BASE / "conversation_classifications.json"

# Lazy-loaded conversation data
_memory_db = None
_classifications = None


def load_memory_db():
    """Load full conversation text (lazy, cached)."""
    global _memory_db
    if _memory_db is None:
        if MEMORY_PATH.exists():
            _memory_db = json.load(open(MEMORY_PATH, encoding="utf-8"))
        else:
            _memory_db = []
    return _memory_db


def load_classifications():
    """Load conversation classifications (lazy, cached)."""
    global _classifications
    if _classifications is None:
        if CLASSIFICATIONS_PATH.exists():
            data = json.load(open(CLASSIFICATIONS_PATH, encoding="utf-8"))
            convos = data.get("conversations", data) if isinstance(data, dict) else data
            _classifications = {str(c.get("convo_id", i)): c for i, c in enumerate(convos)} if isinstance(convos, list) else {}
        else:
            _classifications = {}
    return _classifications


def get_db():
    return sqlite3.connect(str(DB_PATH))


def get_open_loops():
    """Get all open loops (not yet decided)."""
    con = get_db()
    cur = con.cursor()
    decided = {r[0] for r in cur.execute(
        "SELECT convo_id FROM loop_decisions WHERE decision IN ('CLOSE','ARCHIVE')"
    ).fetchall()}
    con.close()

    loops_path = BASE / "loops_latest.json"
    if not loops_path.exists():
        return []
    loops = json.load(open(loops_path, encoding="utf-8"))
    return [l for l in loops if l["convo_id"] not in decided]


def get_topics(convo_id):
    """Get weighted topics for a conversation."""
    con = get_db()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT topic, weight FROM topics WHERE convo_id=? ORDER BY weight DESC LIMIT 10",
        (convo_id,)
    ).fetchall()
    con.close()
    return rows


def get_conversation_text(convo_id):
    """Get the last few user messages from a conversation."""
    memory = load_memory_db()
    idx = int(convo_id)
    if idx < 0 or idx >= len(memory):
        return None, None

    convo = memory[idx]
    messages = convo.get("messages", [])

    # Get user messages (the things YOU said)
    user_msgs = [m for m in messages if m.get("role") == "user"]

    # First 2 user messages = what started the conversation
    first_msgs = user_msgs[:2]

    # Last 3 user messages = where it ended / what's unfinished
    last_msgs = user_msgs[-3:] if len(user_msgs) > 3 else user_msgs

    return first_msgs, last_msgs


def truncate(text, max_len=200):
    """Truncate text to max length."""
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def analyze_loop(convo_id, title, score):
    """Analyze a loop and recommend an action."""
    print(f"\n  {'='*60}")
    print(f"  LOOP #{convo_id}: {title}")
    print(f"  Score: {score} | ", end="")

    # Classification data
    classifications = load_classifications()
    cls = classifications.get(str(convo_id), {})

    domain = cls.get("domain", "unknown")
    outcome = cls.get("outcome", "unknown")
    trajectory = cls.get("emotional_trajectory", "unknown")
    intensity = cls.get("intensity", "unknown")

    print(f"Domain: {domain} | Outcome: {outcome} | Arc: {trajectory}")

    # Topics
    topics = get_topics(convo_id)
    if topics:
        top_topics = [f"{t[0]} ({t[1]:.0f})" for t in topics[:5]]
        print(f"  Topics: {', '.join(top_topics)}")

    # Conversation excerpts
    first_msgs, last_msgs = get_conversation_text(convo_id)

    if first_msgs:
        print(f"\n  STARTED WITH:")
        for m in first_msgs:
            print(f"    > {truncate(m.get('text', ''), 150)}")

    if last_msgs:
        print(f"\n  ENDED WITH:")
        for m in last_msgs:
            print(f"    > {truncate(m.get('text', ''), 150)}")

    # Recommendation
    print(f"\n  {'- '*30}")
    recommendation, reason = compute_recommendation(outcome, trajectory, intensity, score, topics)
    print(f"  RECOMMENDATION: {recommendation}")
    print(f"  WHY: {reason}")
    print(f"  {'='*60}")

    return recommendation


def compute_recommendation(outcome, trajectory, intensity, score, topics):
    """Compute what to do with this loop."""

    # Strong archive signals
    if outcome == "abandoned":
        return "ARCHIVE", "You abandoned this conversation. It's dead weight."
    if outcome == "looped" and trajectory in ("spiral", "negative_arc"):
        return "ARCHIVE", "This conversation spiraled without resolution. Kill it."
    if intensity == "low" and outcome == "looped":
        return "ARCHIVE", "Low intensity, no resolution. Not worth revisiting."

    # Strong close signals
    if outcome == "resolved":
        return "CLOSE", "This conversation reached resolution. Mark it done."
    if outcome == "produced":
        return "CLOSE", "This produced output. Acknowledge and close."

    # Check for intent signals in topics
    intent_topics = {"want", "need", "should", "plan", "going", "build", "create", "make", "learn", "try"}
    done_topics = {"did", "done", "finished", "completed", "solved", "shipped", "fixed"}
    topic_names = {t[0].lower() for t in topics} if topics else set()

    has_intent = bool(topic_names & intent_topics)
    has_done = bool(topic_names & done_topics)

    if has_done and not has_intent:
        return "CLOSE", "Done signals present. Finish line crossed."
    if has_intent and not has_done:
        return "ARCHIVE", "Intent without completion. You wanted to but didn't. Park it or it'll haunt you."

    # Default for looped/unknown
    if outcome == "looped":
        return "ARCHIVE", "Looped without resolution. 51% of your conversations do this. Break the pattern."

    return "ARCHIVE", "No clear resolution signal. Archive and move on."


def record_decision(convo_id, decision):
    """Record decision in DB."""
    con = get_db()
    cur = con.cursor()

    existing = cur.execute(
        "SELECT decision, date FROM loop_decisions WHERE convo_id=?",
        (convo_id,)
    ).fetchone()
    if existing:
        print(f"  Already decided: {existing[0]} on {existing[1]}")
        con.close()
        return False

    title_row = cur.execute(
        "SELECT title FROM convo_titles WHERE convo_id=?", (convo_id,)
    ).fetchone()
    title = title_row[0] if title_row else "(untitled)"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute(
        "INSERT INTO loop_decisions (convo_id, decision, date) VALUES (?, ?, ?)",
        (convo_id, decision, now)
    )
    con.commit()
    con.close()

    verb = "CLOSED" if decision == "CLOSE" else "ARCHIVED"
    print(f"\n  >> {verb}: {title} (#{convo_id})")

    # Notify delta-kernel
    try:
        req = urllib.request.Request(
            "http://localhost:3001/api/law/close_loop",
            data=json.dumps({
                "loop_id": convo_id,
                "title": title,
                "outcome": "closed" if decision == "CLOSE" else "archived"
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    return True


def refresh_pipeline():
    """Rerun the critical pipeline scripts."""
    print("\n  Refreshing pipeline...")
    scripts = [
        ("loops.py", "Detecting loops"),
        ("completion_stats.py", "Counting closures"),
        ("export_cognitive_state.py", "Exporting state"),
        ("route_today.py", "Computing mode"),
        ("governor_daily.py", "Generating brief"),
    ]
    for script, desc in scripts:
        script_path = BASE / script
        if script_path.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    cwd=str(BASE), capture_output=True, text=True, timeout=30
                )
                status = "OK" if result.returncode == 0 else "!!"
                print(f"    [{status}] {desc}")
            except subprocess.TimeoutExpired:
                print(f"    [!!] {desc}: timeout")


def show_state():
    """Show current system state."""
    state_path = BASE / "cognitive_state.json"
    if state_path.exists():
        state = json.load(open(state_path, encoding="utf-8"))
        closure = state.get("closure", {})
        print(f"\n  {'='*50}")
        print(f"  Open loops:      {closure.get('open', '?')}")
        print(f"  Truly closed:    {closure.get('truly_closed', '?')}")
        print(f"  Archived:        {closure.get('archived', '?')}")
        print(f"  Closure quality: {closure.get('closure_quality', '?')}%")
        print(f"  {'='*50}")

    directive_path = BASE / "daily_directive.txt"
    if directive_path.exists():
        print(directive_path.read_text(encoding="utf-8").strip())


def triage_all():
    """Walk through every open loop, analyze it, get a decision."""
    loops = get_open_loops()
    if not loops:
        print("\n  No open loops. You're clean.")
        return

    print(f"\n  TRIAGE MODE: {len(loops)} open loops")
    print(f"  For each loop: read the analysis, then type CLOSE, ARCHIVE, or SKIP")
    print()

    decided_count = 0

    for loop in loops:
        cid = loop["convo_id"]
        title = loop["title"]
        score = loop["score"]

        recommendation = analyze_loop(cid, title, score)

        # Ask for decision
        print(f"\n  [{recommendation} recommended] Enter: CLOSE / ARCHIVE / SKIP")
        try:
            choice = input("  > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  Triage interrupted.")
            break

        if choice in ("CLOSE", "ARCHIVE"):
            if record_decision(cid, choice):
                decided_count += 1
        elif choice == "SKIP" or choice == "":
            print("  Skipped.")
        else:
            print(f"  Unknown: '{choice}'. Skipping.")

    if decided_count > 0:
        refresh_pipeline()
        show_state()
        print(f"\n  Decided {decided_count} loop(s) this session.")
    else:
        print("\n  No decisions made.")


def analyze_single(convo_id):
    """Analyze one loop and ask for decision."""
    con = get_db()
    cur = con.cursor()
    title_row = cur.execute(
        "SELECT title FROM convo_titles WHERE convo_id=?", (convo_id,)
    ).fetchone()
    con.close()
    title = title_row[0] if title_row else "(untitled)"

    # Find score from loops
    loops = get_open_loops()
    score = 0
    for l in loops:
        if l["convo_id"] == convo_id:
            score = l["score"]
            break

    recommendation = analyze_loop(convo_id, title, score)

    print(f"\n  [{recommendation} recommended] Enter: CLOSE / ARCHIVE / SKIP")
    try:
        choice = input("  > ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return

    if choice in ("CLOSE", "ARCHIVE"):
        if record_decision(convo_id, choice):
            refresh_pipeline()
            show_state()
    elif choice == "SKIP" or choice == "":
        print("  Skipped.")
    else:
        print(f"  Unknown: '{choice}'.")


# ── Entry Point ──

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No args: full triage mode
        triage_all()

    elif len(sys.argv) == 2:
        arg = sys.argv[1]
        if arg == "--list" or arg == "all":
            loops = get_open_loops()
            if not loops:
                print("\n  No open loops.")
            else:
                print(f"\n  OPEN LOOPS ({len(loops)})")
                print(f"  {'ID':>6}  {'Score':>6}  Title")
                print(f"  {'-'*6}  {'-'*6}  {'-'*40}")
                for l in loops:
                    print(f"  {l['convo_id']:>6}  {l['score']:>6}  {l['title']}")
                print(f"\n  Run: python close_loop.py          # triage all")
                print(f"  Run: python close_loop.py <ID>     # analyze one")
        else:
            # Analyze a single loop
            analyze_single(arg)

    elif len(sys.argv) >= 3:
        # Direct close: python close_loop.py 143 CLOSE
        convo_id = sys.argv[1]
        decision = sys.argv[2].upper()
        if decision not in ("CLOSE", "ARCHIVE"):
            print(f"Decision must be CLOSE or ARCHIVE, got '{decision}'")
            sys.exit(1)
        if record_decision(convo_id, decision):
            refresh_pipeline()
            show_state()

    else:
        print("Usage:")
        print("  python close_loop.py              # triage all open loops")
        print("  python close_loop.py --list       # show open loops")
        print("  python close_loop.py <ID>         # analyze one loop")
        print("  python close_loop.py <ID> CLOSE   # close a loop")
        print("  python close_loop.py <ID> ARCHIVE # archive a loop")

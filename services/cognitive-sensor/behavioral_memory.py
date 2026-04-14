"""
Behavioral Memory — snapshot today's state, assess yesterday's compliance.

Tables created here (no separate migration script):
  daily_snapshots — one row per day, tracks what happened and whether directive was followed
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).parent.resolve()
DB = BASE / "results.db"


def _get_conn():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            date                TEXT PRIMARY KEY,
            mode                TEXT,
            closure_ratio       REAL,
            closure_quality     REAL,
            open_loops          INTEGER,
            closures_today      INTEGER DEFAULT 0,
            archives_today      INTEGER DEFAULT 0,
            directive_text      TEXT,
            directive_followed  TEXT,
            override_count      INTEGER DEFAULT 0,
            created_at          TEXT,
            energy_level        INTEGER,
            mental_load         INTEGER,
            burnout_risk        INTEGER DEFAULT 0,
            runway_months       REAL,
            skills_utilization  REAL,
            network_score       INTEGER,
            life_phase          INTEGER DEFAULT 1
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(date)")
    # Add columns if they don't exist (safe migration for existing tables)
    for col, typ in [
        ("energy_level", "INTEGER"),
        ("mental_load", "INTEGER"),
        ("burnout_risk", "INTEGER DEFAULT 0"),
        ("runway_months", "REAL"),
        ("skills_utilization", "REAL"),
        ("network_score", "INTEGER"),
        ("life_phase", "INTEGER DEFAULT 1"),
    ]:
        try:
            conn.execute(f"ALTER TABLE daily_snapshots ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def snapshot_today():
    """Read current system state and INSERT OR REPLACE into daily_snapshots."""
    _ensure_table()

    today = datetime.now().strftime("%Y-%m-%d")

    # Load cognitive state
    cog_path = BASE / "cognitive_state.json"
    cog = json.loads(cog_path.read_text(encoding="utf-8")) if cog_path.exists() else {}
    closure = cog.get("closure", {})

    # Load directive
    directive_path = BASE / "daily_directive.txt"
    directive_text = directive_path.read_text(encoding="utf-8").strip() if directive_path.exists() else ""

    # Load governance state for mode
    gov_path = BASE / "governance_state.json"
    gov = json.loads(gov_path.read_text(encoding="utf-8")) if gov_path.exists() else {}
    mode = gov.get("mode", closure.get("mode", "UNKNOWN"))

    # Count today's closures and archives from loop_decisions
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT decision, COUNT(*) FROM loop_decisions WHERE date LIKE ? GROUP BY decision",
            (f"{today}%",)
        ).fetchall()
        decision_counts = {r[0]: r[1] for r in rows}
    except sqlite3.OperationalError:
        decision_counts = {}
    conn.close()

    closures_today = decision_counts.get("CLOSE", 0)
    archives_today = decision_counts.get("ARCHIVE", 0)

    # Load life signals (if available)
    life_path = BASE / "life_signals.json"
    life = json.loads(life_path.read_text(encoding="utf-8")) if life_path.exists() else {}
    energy = life.get("energy", {})
    finance = life.get("finance", {})
    skills = life.get("skills", {})
    network = life.get("network", {})

    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO daily_snapshots
            (date, mode, closure_ratio, closure_quality, open_loops,
             closures_today, archives_today, directive_text, created_at,
             energy_level, mental_load, burnout_risk,
             runway_months, skills_utilization, network_score, life_phase)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        today,
        mode,
        closure.get("ratio", 0.0),
        closure.get("closure_quality", 100.0),
        closure.get("open", 0),
        closures_today,
        archives_today,
        directive_text[:500],  # cap length
        datetime.now().isoformat(),
        energy.get("energy_level"),
        energy.get("mental_load"),
        1 if energy.get("burnout_risk") else 0,
        finance.get("runway_months"),
        skills.get("utilization_pct"),
        network.get("collaboration_score"),
        life.get("life_phase", 1),
    ))
    conn.commit()
    conn.close()
    print(f"[behavioral_memory] Snapshotted {today}: mode={mode}, closures={closures_today}, archives={archives_today}, energy={energy.get('energy_level', 'N/A')}")


def assess_yesterday():
    """
    Look at yesterday's snapshot and assess whether the directive was followed.
    Updates directive_followed: 'followed' / 'partial' / 'ignored'
    """
    _ensure_table()

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM daily_snapshots WHERE date = ?", (yesterday,)
    ).fetchone()

    if not row:
        conn.close()
        print(f"[behavioral_memory] No snapshot for {yesterday} — nothing to assess.")
        return

    # Already assessed
    if row["directive_followed"] is not None:
        conn.close()
        print(f"[behavioral_memory] {yesterday} already assessed: {row['directive_followed']}")
        return

    mode = row["mode"] or "UNKNOWN"
    closures = row["closures_today"] or 0
    archives = row["archives_today"] or 0

    # Assessment logic
    if closures > 0:
        outcome = "followed"
    elif archives > 0:
        outcome = "partial"   # archived but didn't truly close
    else:
        outcome = "ignored"

    conn.execute(
        "UPDATE daily_snapshots SET directive_followed = ? WHERE date = ?",
        (outcome, yesterday)
    )
    conn.commit()
    conn.close()
    print(f"[behavioral_memory] Assessed {yesterday}: {outcome} (closures={closures}, archives={archives}, mode={mode})")


def get_rolling_context(days=14):
    """Return last N days of snapshots as list of dicts, oldest first."""
    _ensure_table()

    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM daily_snapshots WHERE date >= ? ORDER BY date ASC",
        (since,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_compliance_rate(days=30):
    """
    Fraction of assessed days (non-null directive_followed) where outcome was 'followed'.
    Returns float 0.0–1.0, or None if no assessed days exist yet.
    """
    _ensure_table()

    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT directive_followed FROM daily_snapshots WHERE date >= ? AND directive_followed IS NOT NULL",
        (since,)
    ).fetchall()
    conn.close()

    if not rows:
        return None

    followed = sum(1 for r in rows if r[0] == "followed")
    return followed / len(rows)


if __name__ == "__main__":
    print("Running snapshot_today()...")
    snapshot_today()
    print()
    print("Running assess_yesterday()...")
    assess_yesterday()
    print()
    rate = get_compliance_rate(30)
    if rate is not None:
        print(f"30-day compliance rate: {rate*100:.0f}%")
    else:
        print("No compliance data yet (need 2+ days of snapshots).")
    ctx = get_rolling_context(14)
    print(f"Rolling context: {len(ctx)} days of snapshots available.")

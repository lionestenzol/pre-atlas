"""Workflow execution log + auto-recovery — port of conversation #522
"AI Strategy Execution Plan" (2025-02-07), Pre Atlas harvest pipeline.

The source thread sketched an "AI automation" pipeline (scheduled jobs
calling out to `generate_blog.py`, `publish_to_wordpress.php`, etc. via
subprocess) with two real, reusable pieces underneath the specific
subprocess calls:
  1. every run gets logged to a table (workflow_name, status, error) —
     block 18/19 in the source, a Postgres schema + psycopg2 insert.
  2. a failed API check triggers a recovery callback (block 14).

This ports those two pieces as one reusable primitive -- `run_with_recovery`
logs success/failure and calls a recovery function on failure -- backed
by sqlite (stdlib, no external DB service needed) instead of Postgres.
The scheduling loop itself (`schedule.every().day.at(...)`) and the
actual subprocess calls were pipeline-specific glue, not logic, so they
weren't ported.
"""
import sqlite3


def init_log_db(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS workflow_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT DEFAULT '',
            execution_time TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.commit()
    return conn


def log_execution(conn, workflow_name, status, error_message=""):
    conn.execute(
        "INSERT INTO workflow_logs (workflow_name, status, error_message) VALUES (?, ?, ?)",
        (workflow_name, status, error_message),
    )
    conn.commit()


def get_logs(conn, workflow_name=None):
    if workflow_name is None:
        rows = conn.execute("SELECT workflow_name, status, error_message FROM workflow_logs").fetchall()
    else:
        rows = conn.execute(
            "SELECT workflow_name, status, error_message FROM workflow_logs WHERE workflow_name = ?",
            (workflow_name,),
        ).fetchall()
    return [{"workflow_name": r[0], "status": r[1], "error_message": r[2]} for r in rows]


def run_with_recovery(conn, workflow_name, func, recovery_func=None):
    """Run `func()`, logging success/failure. On failure, call `recovery_func()`
    (if given) and re-log whether the recovery attempt itself succeeded."""
    try:
        func()
        log_execution(conn, workflow_name, "success")
        return True
    except Exception as e:
        log_execution(conn, workflow_name, "failed", str(e))
        if recovery_func is not None:
            try:
                recovery_func()
                log_execution(conn, f"{workflow_name}:recovery", "success")
            except Exception as recovery_error:
                log_execution(conn, f"{workflow_name}:recovery", "failed", str(recovery_error))
        return False

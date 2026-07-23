# Workflow Execution Log

Extracted from conversation #522 "AI Strategy Execution Plan" (2025-02-07), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/522_ai-strategy-execution-plan/`), verdict MINE, decided 2026-04-21.

## What this is

The source thread sketched a scheduled "AI automation" pipeline (content generation, WordPress publishing, CRM updates, all invoked via `subprocess`) with two reusable pieces underneath the pipeline-specific subprocess calls: every run got logged to a table (workflow name/status/error), and a failed API health check triggered a recovery callback. `workflow_log.py` ports those two pieces as one primitive, `run_with_recovery(conn, name, func, recovery_func)`, backed by sqlite instead of the source's Postgres (no external DB service needed to run or test it). 5/5 tests passing, covering success, failure-with-recovery, failure-when-recovery-also-fails, and no-recovery-given.

## What was changed from the source

The source's DB helper (`log_execution` in block 19) connected with a literal `psycopg2.connect("... password=securepassword")` — a hardcoded credential, even as an obvious placeholder, which `~/.claude/rules/common/security.md` exists to prevent. Swapped to sqlite, which needs no credentials at all for this use case.

## What was left out

The scheduling loop (`schedule.every().day.at("08:00").do(...)`) and the actual subprocess calls (`generate_blog.py`, `publish_to_wordpress.php`, etc.) were pipeline-specific wiring around files that don't exist in this repo, not logic — nothing to port there. The source already reached for the `schedule` library rather than hand-rolling a scheduler, which was the right call.

## Run the tests

```
python -m pytest test_workflow_log.py -v
```

# DropList Ship — Autopilot Kickoff (paste into a FRESH session)

Copy everything in the code block below into a new Claude Code session (cwd = `C:\Users\bruke\Pre Atlas`).
It is self-contained — assumes no memory of the audit session.

```
/groundwork ship DropList to "product" per DROPLIST_SHIP_SPEC_2026-06-25.md, then /autopilot the build.

Context: a verified 36-agent audit (SHIP_READINESS_AND_MARKET_2026-06-25.md) picked DropList as the
ship target. Task A (serve the UI front door) is ALREADY DONE + verified this session:
services/droplist/droplist/server.py now serves GET / -> ui/line.html, GET /chain -> ui/chain.html,
and GET /api/dag/sample; test_server.py gate is 10/10 and pytest is 67/67. DO NOT redo Task A.

Drive the REMAINING 3 tasks from DROPLIST_SHIP_SPEC_2026-06-25.md, each proof-gated:

  Task B (harden the write API) — services/droplist/droplist/server.py:79-85
    - Replace CORS allow_origins=["*"] with an allowlist (127.0.0.1/localhost + a configurable
      deploy origin via env).
    - Add a shared-secret token guard on the POST routes: /api/drop (server.py:198),
      /api/dag/{id}/node/{id}/complete (:347), /reopen (:393). Mirror services/atlas-map-api auth.py
      (X-Atlas-Token, gitignored token file/env).
    - Add a server-side proxy route for the Anthropic calls and repoint ui/line.html's 5
      api.anthropic.com fetches (line.html:826,1466,1517,1540,1567) at it, so NO key ships to the browser.
    - DoD: unauthenticated POST -> 401/403 (new test in test_server.py); UI works with token;
      `grep -ri "api.anthropic.com\|sk-ant" services/droplist/ui` shows no client-side key path.

  Task C (a11y pass) — ui/line.html, ui/chain.html
    - aria-live="polite" on the live NOW/status region; label/role/aria-label on the touch buttons
      and color-only state dots (--done/--stuck/--skip/--carry); keyboard mark-off (Enter/Space);
      contrast check on --muted #8b918c / --faint #5c635e vs --bg #0c0e0d.
    - DoD: code-recon audit a11y grade >= fair; keyboard-only can capture a drop and mark a node done.

  Task D (always-on + commit + merge) — after B and C
    - Add a droplist-ui entry to autostart/.claude/launch.json running the server with
      DROPLIST_DAEMON=1 (self-advancing daemon, server.py:51-67).
    - Commit branch experiment/droplist-remediation-2026-06-15; merge to main.
    - DoD: service starts on boot + daemon thread alive; `git status` clean on services/droplist; merged.

Parallelism: B runs now (independent of C); C needs the served UI (already shipped) so it can start
immediately too; D waits for B+C. Verify every DoD with code-recon/tests BEFORE marking a task done —
no "done" without tool-verified proof. Run pytest + test_server.py green at the end.

Definition of Shipped: a stranger on the LAN opens http://<host>:3073/, captures a thought, watches it
become a DAG, marks nodes done by keyboard/touch, the daemon advances it — over an authenticated write
API with no secrets in the browser — and it starts on boot. Built != Official = Merged + Running + Used.
```

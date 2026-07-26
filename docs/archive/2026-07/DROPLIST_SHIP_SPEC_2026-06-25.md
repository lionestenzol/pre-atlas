# DropList → Ship Spec (autopilot-ready) — 2026-06-25

Target chosen from the ship-readiness audit (`SHIP_READINESS_AND_MARKET_2026-06-25.md`):
**droplist** — verified 45% ready, but the only-two-with-a-real-market-wedge product whose
*hard part is already done* (engine: 67 tests pass, DAG, scheduler, tool-verified done-condition).
Its #1 gap is the buildable thing: **a UI front door**.

Branch: `experiment/droplist-remediation-2026-06-15`. Service: `services/droplist`, port 3073.

Run with: `/autopilot` after `fest create` from this spec, **in a fresh session** (this one is at WRAP).

---

## Ground truth (verified this session, file:line)

- `server.py:78` FastAPI app is titled "read-only API" but already has **mutation routes**:
  `POST /api/drop` (server.py:198), `POST /api/dag/{id}/node/{id}/complete` (server.py:347),
  `GET /api/dag/{id}/checklist` (server.py:368), `POST /api/dag/{id}/node/{id}/reopen` (server.py:393).
- **UI exists but is never served:** `ui/line.html` (NOW screen) + `ui/chain.html` (DAG view).
  No `StaticFiles`/`HTMLResponse` mount anywhere in `server.py`.
- **UI self-wires same-origin** — no base-URL config needed once served:
  `line.html:1614` → `window.location.origin + '/api/now'`; `chain.html:323` → `/api/dag/sample`.
- **Security holes:** `server.py:79-85` CORS `allow_origins=["*"]`, no auth on the POST routes.
  `line.html` calls **`api.anthropic.com` directly from the browser** (line.html:826, 1466, 1517,
  1540, 1567) → an API key would ship to the client.
- **Daemon already wired** (gated): `server.py:51-67` `_maybe_start_daemon()` via lifespan,
  spawns `daemon.run_loop` when `DROPLIST_DAEMON=1`.
- Tests: 16 files / 67 pass (`pytest -q` ~20s). a11y graded **poor**.

---

## Tasks (sequence number = parallel group)

### seq 01 · Task A — Serve the UI front door
- **Touch:** `server.py` (after app init, ~line 85). Mount the UI so a browser can use it.
- **Do:** add `from fastapi.staticfiles import StaticFiles` + `from fastapi.responses import HTMLResponse`;
  serve `ui/line.html` at `GET /` and `ui/chain.html` at `GET /chain` (FileResponse), and mount
  `ui/` static if needed. Confirm `/api/dag/sample` exists (chain.html:323 expects it) — if not, add it
  (alias to a sample/most-recent DAG via `storage`/`dag_update`).
- **DoD (provable):** `curl -s localhost:3073/ | grep DropList` returns the page; opening it in a
  browser shows live `/api/now` data; clicking a node fires `POST /api/dag/{id}/node/{id}/complete`
  (server.py:347) and the UI reflects the new state. New test in `test_server.py` asserts `GET /` is 200 + HTML.

### seq 01 · Task B — Harden the write API (parallel with A)
- **Touch:** `server.py:79-85` (CORS) + the POST handlers (198/347/393) + a new proxy route.
- **Do:** (1) replace `allow_origins=["*"]` with an allowlist (`127.0.0.1`/`localhost` + a configurable
  deploy origin via env). (2) Add a shared-secret guard on all POST routes — mirror the pattern in
  `services/atlas-map-api/.../auth.py` (`X-Atlas-Token`); read from a gitignored token file/env.
  (3) Add a server-side proxy route for the Anthropic calls so **no key ships to the browser**;
  repoint `line.html`'s 5 `api.anthropic.com` fetches at the proxy.
- **DoD:** unauthenticated `POST /api/drop` → 401/403 (new test); UI works with the token;
  `grep -ri "api.anthropic.com\|sk-ant" ui/` returns no client-side key path.

### seq 02 · Task C — a11y pass on the served UI (after A)
- **Touch:** `ui/line.html`, `ui/chain.html`.
- **Do:** `aria-live="polite"` on the live status/now region; `<label>`/`role`/`aria-label` on the
  touch buttons and color-only state dots (`--done/--stuck/--skip/--carry`); keyboard operability for
  node mark-off (Enter/Space); contrast check on `--muted #8b918c` / `--faint #5c635e` against `--bg #0c0e0d`.
- **DoD:** `code-recon audit` a11y grade ≥ **fair**; keyboard-only flow can capture a drop and mark a node done.

### seq 03 · Task D — Always-on + commit + merge (after A,B,C)
- **Do:** add a `droplist-ui` entry to autostart/`launch.json` running the server with
  `DROPLIST_DAEMON=1` (self-advancing, server.py:58); commit the branch; merge to `main`.
- **DoD:** service starts on boot and self-advances (daemon thread alive); `git status` clean on the
  droplist tree; branch merged.

---

## Parallelism
```
seq 01:  [A serve UI]   [B harden]      ← independent, run together
seq 02:  [C a11y]                       ← needs A's served UI
seq 03:  [D deploy+merge]               ← needs A+B+C
```

## Definition of Shipped (the product bar)
A stranger on the LAN opens `http://<host>:3073/`, captures a thought, watches it become a DAG,
marks nodes done with keyboard or touch, the daemon advances it — over an authenticated write API
with no secrets in the browser — and the whole thing starts on boot. Built ≠ Official = Merged + Running + Used.

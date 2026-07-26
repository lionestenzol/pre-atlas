# DropList → Market-Ready (local-first, installable, swappable-LLM) — Ship Spec

**Status:** autopilot-ready. Verified by a 17-agent adversarial audit (2026-06-26), every
load-bearing claim re-checked file:line. Supersedes the UI-front-door half of
`DROPLIST_SHIP_SPEC_2026-06-25.md` (which assumed the served UI was a real client of the
engine — it is **not**; see seq 01).

**Service:** `services/droplist`, FastAPI, port **3073**. Branch: `feat/atlas-setup-ui`.
**Run with:** `/groundwork` to build the festival from this spec, then `/autopilot` in a fresh
session (this planning session is at WRAP).

---

## Scope decision (locked)

**Target = local-first installable app that hits all 4 user bars** — NOT hosted multi-tenant SaaS.

- Bar 1: click-and-invoke like an app
- Bar 2: installable, icon, "everything" (PWA)
- Bar 3: standalone app **and/or** web app
- Bar 4: interchangeable LLM models

**SaaS hedge (constraint, not a task):** keep all state behind `storage.py` and all writes behind
`auth.py`. Do not inline JSONL reads or token checks elsewhere. Then a future hosted/multi-tenant
upgrade = swap those two module implementations (JSONL→Postgres+`tenant_id`; shared-token→per-user
JWT), not a rewrite. **Do not build multi-tenancy now.**

---

## Verified ground truth (file:line — trust this, re-verify before editing)

**The engine is real and works.** `POST /api/drop` ([server.py:321]), node-complete
([server.py:471]), reopen ([server.py:518]), `storage.save_dag`, `DAG_EVENTS` audit log. The hard
logic exists.

**🔴 THE KEYSTONE BUG — the UI is a disconnected localStorage twin, not a client of the engine:**
- `line.html` keeps ALL state in browser `localStorage` under `droplist:state:v1` ([line.html:357],
  `save()` [line.html:379]).
- Every user write mutates only that local `S` object: mark-done `completeActive` ([line.html:402],
  wired to the Done button ~[line.html:961]), add `minAdd` ([line.html:527]), fire-to-board
  `lineFire` ([line.html:1583]). **Not one `fetch()` to the engine's write routes.**
- The one bridge is dead: `GET /api/now` is fetched at [line.html:1614], then handed to
  `tryWireLive(data)` at [line.html:1618] — **a function never defined anywhere in the file** — and
  the fallback scans for `[data-bind]` elements, of which there are **zero**. The server response is
  parsed and thrown away. The rendered UI is 100% localStorage-driven.
- Net: a full day completed in the UI never reaches the DAG/packet engine the daemon, autopilot, and
  Atlas item-backbone read. **Everything else is decoration until this wire is real.**

**PWA installability = 0.** No `<link rel="manifest">`, service worker, icons, or `theme-color` in
[line.html:3-9] or [chain.html:3-9]; no static-asset route in `server.py` to serve them.

**LLM = Anthropic-hardcoded at every layer.** `llm.py` SDK ([llm.py:78-95]) only branches
`heuristic|anthropic` ([llm.py:20-21]); proxy POSTs `api.anthropic.com` with `x-api-key`/
`anthropic-version` ([server.py:164-178]); `line.html` hardcodes `claude-sonnet-4-20250514` at 5
fetch sites (828, 1468, 1519, 1542, 1569) → all hit `/api/ai/anthropic`. No provider abstraction, no
user picker. Sonnet pricing hardcoded ([llm.py:93-94]).

**Invocation = dev command.** `launch.json` "droplist" runs uvicorn :3073 ([launch.json:376],
`DROPLIST_DAEMON=1`); `droplist-ui` console script ([pyproject.toml:24]); `run()` binds
`127.0.0.1:3073` ([server.py:565-571]). No `.lnk`, no one-click. The `PreAtlas-DropList-Daemon` Task
Scheduler job only runs `droplist.daemon --once` (advances DAGs) — it does **not** stand up the web
server. README still says "No UI" ([README.md:7]) — stale.

**Already hardened (keep, do not rebuild):** server-side key custody (key never ships to browser,
[server.py:170], UI sends only `X-Atlas-Token` [line.html:826-827]); constant-time token guard
([auth.py:118-129]); CORS narrowed off `*` ([server.py:93-103]); 74 test funcs (~65 pass).

---

## Tasks (seq number = parallel group; `/autopilot` executes the DAG)

### seq 01 · Task A — Wire the UI to the engine  *(L — the keystone, do first)*
- **Touch:** `ui/line.html` (the dead [1610-1636] block + the mutation sites 402/527/1583),
  `droplist/server.py` (reuse existing routes; add a `GET /api/dags`/`/api/brief` read if the queue
  needs more than the single `/api/now` job).
- **Do:** Define a real `tryWireLive(data)` that hydrates `S.jobs` from `GET /api/now` (+ full queue
  read) so the UI renders **server** state on boot. Convert each mutation to a server write, then
  re-hydrate+re-render instead of mutating `S`: `completeActive` → `POST /api/dag/{id}/node/{id}/
  complete`; `minAdd`/`adddrops`/`lineFire` → `POST /api/drop` (server builds packet+DAG). Demote
  `localStorage` to an optimistic cache only. Write a small adapter for the field-shape mismatch
  (server node `{status, done_condition, depends_on}` ↔ UI `{status, steps:[{text,done}]}`).
- **Library:** none — wiring existing endpoints. Auth already plumbed (`window.__DL_TOKEN__`
  injected [server.py:135]; UI already sends it for the LLM proxy).
- **DoD (provable):** Complete a job in browser A → reload in browser B → state persists. `DAG_EVENTS`
  shows the completion. `curl localhost:3073/api/now` reflects a UI action. New `test_server.py` case
  asserts a UI-shaped `POST` lands in the store.

### seq 02 · Task B — Swappable LLM models via `litellm`  *(M — after A; shares line.html)*
- **Touch:** `droplist/llm.py`, `droplist/server.py` (replace the Anthropic proxy), `ui/line.html`
  (picker + the 5 hardcoded model strings).
- **Do:** Adopt **`litellm`** (one `completion(model=...)` covers Anthropic/OpenAI/Gemini/OpenRouter/
  Ollama-local). Replace `call_json` ([llm.py]) and `_forward_anthropic` ([server.py:168]) with a
  single `POST /api/ai/complete {provider, model, messages}`. Keep server-side key custody; read
  per-provider keys (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`OPENROUTER_API_KEY` or `OLLAMA_BASE_URL`).
  Add `GET /api/ai/models` returning only providers the server has keys for. Fix hardcoded Sonnet
  pricing → litellm per-model cost. UI: add a `<select>` populated from `/api/ai/models`, persist
  choice to `localStorage`, send selected model in the 5 fetches, POST to `/api/ai/complete`.
  **Port the validated-allowlist plan→confirm UX already shipped in `atlas-setup.html`** — don't
  invent a new one.
- **Library:** `litellm` (assemble-first; do not hand-roll a second per-provider HTTP path).
- **DoD:** With `OPENAI_API_KEY` set, pick "gpt-4o" → triage generates via OpenAI; `llm_calls.jsonl`
  logs the OpenAI model + cost. Switch to "ollama/llama3" → runs local, no external key. Keep
  `Depends(auth.require_write_token)` (still spends money).

### seq 03 · Task C — PWA install (Bars 1+2)  *(M — after A/B; shares line.html head)*
- **Touch:** new `ui/manifest.webmanifest`, `ui/sw.js`, `ui/icons/`; `droplist/server.py` (static +
  manifest/SW routes); `ui/line.html` + `ui/chain.html` `<head>`.
- **Do:** `manifest.webmanifest` (name/short_name "DropList", `start_url:"/"`, `display:"standalone"`,
  `theme_color:"#0c0e0d"`, 192/512/maskable icons). Generate the SW with **Workbox** (`workbox-build`)
  — precache the two HTML shells + fonts + icons; do not hand-roll. Generate icons + apple-touch tags
  with **`pwa-asset-generator`** from one source mark. Add to both heads:
  `<link rel="manifest">`, `<meta name="theme-color">`, `apple-touch-icon`, `icon`. FastAPI:
  `@app.get("/manifest.webmanifest")` (MIME `application/manifest+json`), `@app.get("/sw.js")` (MIME
  `text/javascript`), `app.mount("/icons", StaticFiles(...))`. Register the SW via an inline
  `navigator.serviceWorker.register('/sw.js')` injected the same way `_serve_ui` injects
  `__DL_TOKEN__`.
- **Library:** Workbox, pwa-asset-generator (assemble-first).
- **DoD:** Chrome fires `beforeinstallprompt`; "Install DropList" → standalone window + OS icon;
  offline launch renders the shell. Lighthouse PWA "installable" passes.

### seq 04 · Task D — One-click launcher (finishes Bar 1)  *(S — parallel)*
- **Touch:** new `scripts/start_droplist.ps1` + `.lnk` generator; `.claude/launch.json`;
  `atlas-setup.html`; `README.md:7`.
- **Do:** `start_droplist.ps1` — if `:3073` down, start uvicorn detached, then open
  `http://127.0.0.1:3073`. Generate a Windows `.lnk` (same pattern as `install_atlas_autostart.ps1`).
  Register DropList in `atlas-setup.html` via existing `GET /map/launchables` + `POST /map/halt`. Fix
  stale README "No UI" line (code-as-furniture).
- **DoD:** Double-click the desktop icon on a cold machine → server up + browser open, zero terminal.

### seq 04 · Task E — Standalone desktop binary (completes Bar 3)  *(M — parallel)*
- **Touch:** new `desktop.py`, `[desktop]` extra in `pyproject.toml`, `.ico`; fix hardcoded port
  ([server.py:571]).
- **Do:** **pywebview** wrapper: `desktop.py` starts `server.run` on a daemon thread (dynamic free
  port, not hardcoded 3073), waits for the port, then `webview.create_window('DropList', url);
  webview.start()`. Reuses 100% of `server.py` + both HTMLs (native EdgeWebView2 on Windows). Package
  with **PyInstaller** `--onefile --windowed --add-data 'ui;ui'` + `.ico` → one `DropList.exe` that is
  BOTH a desktop window AND a localhost web app. Defer Tauri unless auto-update is wanted (STRUDEL has
  a toolchain to copy).
- **Library:** pywebview, PyInstaller.
- **DoD:** `DropList.exe` on a Python-free machine opens a native window AND still answers `:PORT` as
  a web app. Two instances don't collide (dynamic port).

### seq 04 · Task F — Quality gate (table stakes)  *(M — parallel)*
- **Touch:** the 9 empty `test_*.py`; new CI workflow; `ui/line.html` (rows/headers); `server.py`
  (`/api/ai/*`).
- **Do:** Fill/delete the 9 zero-function `test_*.py`; add the DOD-flagged break-tests (B6/B10/B13).
  Wire `pytest -q` + `pytest-cov` into GitHub Actions (≥80%). Swap clickable `<div class="row|ln-head">`
  ([line.html:642,467]) for `<button>` (already styled) + `aria-expanded`/`aria-pressed`; add
  `aria-live` to async panels; run `axe-core`/`pa11y` in CI. Add **`slowapi`** rate-limit + daily cost
  ceiling on `/api/ai/*`; fix naive-UTC scheduler with `zoneinfo`.
- **Library:** pytest-cov, GitHub Actions, axe-core/pa11y, slowapi, zoneinfo.
- **DoD:** CI green ≥80% coverage; axe-core zero critical; keyboard-only user can open a job + expand
  a station.

---

## Parallelism
```
seq 01:  [A wire UI↔engine]                         ← keystone, blocks meaningful everything
seq 02:  [B swappable LLM]                           ← after A (shares line.html)
seq 03:  [C PWA install]                             ← after A/B (shares line.html head)
seq 04:  [D launcher] [E desktop] [F quality]        ← independent, run together
```

## Definition of Shipped (the product bar)
You double-click an icon → DropList opens in its own window (and/or installs from the browser with an
OS icon). You capture a thought; it becomes a real DAG **in the engine** (survives reload on another
device); you pick GPT-4o or local Llama from a dropdown and the triage runs on it; nodes mark done
over the authenticated write API with no secret in the browser. **Built ≠ Official = Merged + Running
+ Used.**

## Out of scope (deliberately)
Hosted multi-tenant SaaS (Postgres+`tenant_id`, accounts, Stripe, public TLS). Reachable later by
swapping `storage.py` + `auth.py` behind their existing interfaces — kept clean as a constraint above.

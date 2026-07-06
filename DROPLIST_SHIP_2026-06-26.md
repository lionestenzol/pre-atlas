# DropList → Market-Ready: Ship Summary (2026-06-26)

**Branch:** `feat/atlas-setup-ui` (≈147 commits ahead of `main`, not yet merged)
**Service:** `services/droplist`, FastAPI, port 3073
**Outcome:** ~20-25% → **~95%** of the local-first installable target. All 4 user bars + a quality gate.

Use this as the PR body (`feat/atlas-setup-ui → main`), release notes, or a handoff record.

---

## What DropList is now

Drop a messy thought → it becomes a real DAG **in the engine** (not a browser-only fake), survives reload
on another device, and you work it node-by-node. It runs four ways off one engine and one JSONL data dir:

- **Desktop app** — `DropList.exe` (85 MB, no Python needed): native window + localhost web app in one process
- **Web UI + PWA** — `droplist-ui` → `http://127.0.0.1:3073`; Chrome "Install" pins it with an icon, works offline
- **One-click launcher** — `scripts/start_droplist.ps1` (+ `.lnk` recipe)
- **CLI** — the original zero-dependency `drop` command

You pick the AI model (Anthropic / OpenAI / Gemini / OpenRouter / local Ollama) from a dropdown; keys stay
server-side; spend is capped by a daily ceiling.

## The four bars (audit → done)

| Bar | Was (audit) | Now |
|---|---|---|
| **Click-and-invoke** | dev command, no icon | launcher + PWA install + `.exe` |
| **Installable PWA** | no manifest/SW/icons | manifest + service worker + icons, both screens |
| **Standalone + web** | desktop 0% | `DropList.exe` native window **and** localhost web app |
| **Interchangeable LLM** | Anthropic hardcoded | `litellm` picker, key-gated, server-side |

## Commits (8)

| Commit | What |
|---|---|
| `61f9c83` | Swappable LLM via `litellm` — `/api/ai/models` + `/api/ai/complete`, in-UI model picker |
| `502b167` | PWA install — manifest, service worker, icons; head injection serves both screens |
| `21c0d44` | One-click launcher + native desktop window (`desktop.py`); `server.run(port)` un-hardcoded |
| `cf77029` | AI spend guards — daily cost ceiling + slowapi rate limit on `/api/ai/*` |
| `c3c957e` | Ship-blocker: PWA icons were gitignored (manifest 404'd its own icons) + desktop import fix |
| `930eb4f` | Quality gate — a11y keyboard ops, CI workflow, coverage gate, 9 smoke gates under pytest |
| `5a9d952` | README no longer claims "No UI" |
| `2bcec4c` | Trim PyInstaller bundle (exclude torch/transformers/etc.) — exe 2.8 GB → 85 MB |
| `2082b65` | Product-first README — run-as-app, model picker, config reference |

## Verification

- **93 tests pass** (84 native + 9 script-style smoke gates wrapped under pytest)
- **Coverage 63.8%** — gate floored honestly at 60% (core modules ≥80%: graph_engine 87, state 98,
  scheduler 93, retrieval 97; CLI/inventory scaffolding drags the aggregate). CI: `.github/workflows/droplist-ci.yml`
- **`DropList.exe` run-verified** — 84.7 MB; frozen exe logs `Uvicorn running on http://127.0.0.1:<port>`,
  survives the 15s server-up gate, `import litellm` works without the excluded ML libs
- **Security kept**: server-side key custody, constant-time `X-Atlas-Token` guard, narrowed CORS, daily cost ceiling

## Honest residual (optional — none are bars)

- Coverage 63.8% → 80% (cover `cli`/`inventory`, or scope the gate to business logic)
- axe-core / pa11y wired into CI
- One human **double-click of `DropList.exe`** on an interactive desktop for the final GUI-window confirmation
  (everything up to the window is verified via uvicorn's startup log)

## Scope deliberately NOT built

Hosted multi-tenant SaaS (Postgres + `tenant_id`, accounts, Stripe, public TLS). Reachable later by swapping
`storage.py` + `auth.py` behind their existing interfaces — kept clean as a constraint, not built now.

> **Built ≠ Official = Merged + Running + Used.** This is built and verified on the branch; merging to `main`
> and a human cold-start of the `.exe` are the last two steps to "official."

# Agent Belt — Claude Code Skill Inventory

> **What this is:** the operator's Claude Code **skill belt** — **35 user-global
> skills + 27 slash-commands** that drive work across projects, including this
> `pre-atlas` repo. Distinct from the running system (`CONTEXT_FOR_WEB.md`) and
> from the 13-tool search stack (`docs/repo-search-stack.md`); `repo-search` is
> one skill *in* this belt.
>
> Descriptions below are the authoritative `description:` frontmatter from each
> `SKILL.md`, condensed. Built 2026-06-09 from `~/.claude/skills` on the
> operator's Windows machine.

---

## Why this matters: routers, pairs, and look-alikes

- **Routers pick other tools.** `web-extract-workflow` routes the scraping
  cluster; `search-stack` routes search across surfaces. Start at the router.
- **Three "search" skills are NOT interchangeable:**
  - `repo-search` — *local-repo radar* (the DropList protocol over the 13-tool stack).
  - `search-first` — *external/web research* before writing custom code (invokes the researcher agent).
  - `search-stack` — *multi-surface router* (web/code/files/GitHub/academic/…), backed by a service.
- **`weapon` vs `project-finisher`:** both close projects, but **`weapon`
  executes**, `project-finisher` only **plans**.
- **`*-migrate` pairs:** `three-js`/`three-js-migrate`, `anime-js`/`anime-js-migrate`
  — base skill for new code, `-migrate` for fixing/upgrading existing code.

---

## 1. Search & code orientation
| Skill | Purpose |
|---|---|
| `repo-search` | Search a codebase systematically before reading/editing. Implements the DropList Search Tightening Protocol (es→eza→fd→rg→sg→semgrep→jq/yq→ctags→tests→diff). Local-repo radar. |
| `search-first` | Research-before-coding: find existing tools/libraries/patterns before writing custom code. Invokes the researcher agent. |
| `search-stack` | Route a query across surfaces (web, code, files, GitHub, academic, social, legal, data, local, multimedia, product, memory, extract). Backed by `services/search-stack` :3070 + MCP `search_stack_*`. |

## 2. Code quality, review & patterns
| Skill | Purpose |
|---|---|
| `security-review` | Security checklist + patterns for auth, user input, secrets, API endpoints, payments. |
| `tdd-workflow` | Enforce TDD with 80%+ coverage (unit/integration/E2E). |
| `verification-loop` | Comprehensive verification system to prove a change works before "done". |
| `backend-patterns` | Backend architecture, API design, DB optimization (Node/Express/Next.js API routes). |
| `frontend-patterns` | React/Next.js, state management, performance, UI best practices. |
| `coding-standards` | Universal coding standards for TS/JS/React/Node. |
| `wasp-patterns` | Full-stack **Wasp** framework patterns — `.wasp` DSL, operations, auth, deploy, pitfalls. |

## 3. Project-driving & execution
| Skill | Purpose |
|---|---|
| `weapon` | Autonomous project finisher that **executes**: defines DONE, breaks into steps, runs, validates, closes — zero scope expansion. |
| `project-finisher` | Evaluate/structure/**plan** an unfinished project to completion (spec validation, timeline, closure planning). |
| `mini-ship` | Find and ship the smallest atom you can close right now; self-evolves heuristics from its ship log. |
| `autopilot` | Deterministic **fest** orchestrator — picks next task via decision tree, runs lightweight agents free, escalates heavy/ambiguous work to Claude. No LLM in the loop. |
| `fest` | Manage Festival-methodology projects (festivals, phases, sequences, tasks; validate, progress, next work). |
| `cookbook` | Run agent cookbook tools — scan files, parse logs, validate data, check configs, system status, generate/refactor/test code. |

## 4. Web extraction / scraping  *(router cluster)*
| Skill | Purpose |
|---|---|
| **`web-extract-workflow`** | **Router** — routes scrape/crawl/extract/clone/audit between Scrapling (Python venv), sitepull (Node CLI = local web-audit), and anatomy-extension (Chrome MV3). Encodes the operator's rules (managed-unlock over stealth, paper-beating test, no tool sprawl). |
| `web-audit` | Reverse-engineer a hosted web app and run it locally — probe endpoints, fingerprint bundle, vendor assets, zero-dep local copy with stubbed backend. |
| `scrapling-official` | Scrape with Scrapling: anti-bot bypass (Cloudflare Turnstile), stealth headless, spiders, adaptive scraping, JS rendering. |
| `competitor-monitor` | Track a competitor's site over time (pricing, posts, changelog, comparison-page mentions); weekly intel snapshots + optional briefs. Built on sitepull + monitor.py + synthesize.py. |

## 5. 3D / fractal
| Skill | Purpose |
|---|---|
| `three-js` | 3D graphics in-browser via WebGL/WebGPU (scenes, GLTF, shaders, postprocessing, WebXR, raycasting, instancing). |
| `three-js-migrate` | Diagnose/fix three.js broken by r150's color-space + lighting overhaul and later breaking changes (r152…r171+). |
| `react-three-fiber` | 3D in React with `@react-three/fiber` + `drei` (pmndrs ecosystem). Pinned to R3F 9.6.1 / drei 10.7.7 / three 0.184. |
| `mandelbulb3d` | Operate Mandelbulb3D (MB3D): `.m3p`/`.m3f` params, formula selection/hybrids, render workflow, JIT custom formulas. |
| `mandelbulber2` | CLI surface for Mandelbulber 2 — `.fract` scenes, headless `--nogui` render, parameter-ramp animation. |

## 6. Animation / video
| Skill | Purpose |
|---|---|
| `anime-js` | Anime.js v4 animation — DOM/SVG/CSS/WAAPI, timelines, stagger, spring/elastic/bezier easing. |
| `anime-js-migrate` | Diagnose/translate anime.js between v3 and v4. |
| `remotion` | Programmatic video with Remotion (React → MP4/GIF/WebM); Player embed; project scaffolding. |

## 7. Visualization / spec
| Skill | Purpose |
|---|---|
| `anatomy-map` | Generate an interactive anatomy diagram for a React/Next.js component — self-contained HTML with UI mockup, file:line callouts, backend-chain strip, click-to-code drawers. Relates to repo `anatomy/` + `tools/anatomy-extension`. |

## 8. Meta / learning / handoff
| Skill | Purpose |
|---|---|
| `continuous-learning-v2` | Instinct-based learning — observes sessions via hooks, creates atomic instincts with confidence scoring, evolves them into skills/commands/agents. v2.1 adds project-scoping. |
| `eval-harness` | Formal evaluation framework for CC sessions (eval-driven development). |
| `strategic-compact` | Suggest manual context compaction at logical intervals (vs arbitrary auto-compaction). |
| `handoff-out` | Package CC output as a frontmattered markdown handoff → `<operator-system-repo>/handoff/outbox/` + clipboard, for delivery back to claude.ai. |

## 9. Delegation & niche
| Skill | Purpose |
|---|---|
| `codex-delegate` | Dispatcher to the OpenAI Codex CLI for its 38 specialized skills (deploy, PRs, CI-fix, review, sora, transcribe, figma, security, Linear/Sentry/Notion/Vercel, …). Infers intent from shorthand; has explicit "do NOT delegate" boundaries. |
| `st3gg` | PNG steganography — encode/decode/analyze via the locally patched ST3GG toolkit at `~/tools/ST3GG`. |

---

## Slash-commands (27)

Many are local automations/state commands; some pair with skills above.

**Learning / instinct system:** `/learn` (extract reusable patterns) · `/learn-eval` · `/evolve` · `/prune` · `/instinct-status` · `/instinct-export` · `/instinct-import` — the command surface of `continuous-learning-v2`.

**Build / quality:** `/build-fix` · `/refactor-clean` · `/tdd` · `/test-coverage` · `/verify` · `/code-review` · `/eval` · `/tgt` (Three-Layer Organization Audit).

**Flow / project:** `/goal` · `/plan` · `/status` · `/show` · `/checkpoint` · `/mini-ship` (one round of the mini-ship loop).

**TouchDesigner:** `/td` (natural-language builder) · `/td-ux` (UX cheatsheet) · `/td-experiment` (quick experiment).

**Wasp:** `/wasp-new`.

**Misc:** `/jargonize` · `/jargonize-mark`.

---

## Belt ↔ pre-atlas repo ties

- `anatomy-map`, `web-audit`, `web-extract-workflow` ↔ this repo's `anatomy/`,
  `tools/anatomy-extension/`, and optogon's sitepull adapter. **(present)**
- `wasp-patterns` + `/wasp-new` ↔ a Wasp app somewhere — matches the `.wasp`
  exclusions throughout `docs/search-protocol.md`.
- `search-stack` ↔ `services/search-stack` (port 3070) + MCP `search_stack_*`.
  **Not in this clone** — newer or in another repo.
- `handoff-out` ↔ `<operator-system-repo>/handoff/outbox/`. **Not in this clone**
  — implies a separate "operator-system" repo is the hub for cross-surface handoffs.
- `codex-delegate` ↔ `tools/codex-partner/` here is the repo-local counterpart of
  the Codex delegation pattern.

> If you want `services/search-stack` or the operator-system `handoff/` brought
> into context, point me at the repo/path (or paste them) and I'll wire them in.

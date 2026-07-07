# Repo Forensic Trace — Pre Atlas + sibling pre-atlas
**Generated:** 2026-06-26 · Method: full `git log --all` forensics over both clones + `es` machine-wide repo discovery + memory-corpus cross-reference.
**Ground truth:** git history (deterministic). Narrative/"why" cross-referenced from `~/.claude/.../memory/` and `doctrine/`.

---

## 0. The two repos are ONE upstream, diverged

| | **Pre Atlas** (space) — primary cwd | **pre-atlas** (hyphen) — delta-scp home |
|---|---|---|
| Remote | `github.com/lionestenzol/pre-atlas` | **same remote** |
| Root commit | `b013729` 2026-01-12 | **same root commit** |
| HEAD branch | `feat/atlas-setup-ui` | `feat/delta-scp-v2-graph-memory` |
| Ahead of `origin/main` | **130 commits** (0 behind) | **6 commits** (0 behind) |
| Commits (all branches / HEAD) | 425 / 255 | 178 / 131 |
| Tracked files | 1,948 | 1,450 |
| Authors | Bruke 332 · Claude 65 · lionestenzol 28 | Bruke 125 · Claude 35 · lionestenzol 18 |

**Finding:** these are two working clones of the same GitHub repo. Their file-birth tables are **identical through 2026-04-19**, then diverge. `Pre Atlas` (space) became the *everything-fork* (130 unmerged commits, the live frontier); `pre-atlas` (hyphen) **specialized into delta-scp** and otherwise tracks `main`. Almost nothing has actually merged to `main` — the real work lives on the feature branches.

**Three identities, two humans-of-record + agents:** `Bruke <brukev@gmail.com>` = local Claude Code; `lionestenzol <…@users.noreply.github.com>` = the **same person's GitHub-web/Actions identity** (dominant in the early months); `Claude <noreply@anthropic.com>` = subagents/worktrees. Authorship shifts from lionestenzol (web) → Bruke (local CC) over time.

---

## 1. The timeline — six eras

| Era | Date | What was born | Signal |
|---|---|---|---|
| **Genesis** | 2026-01-12 | `delta-kernel` (state engine), `cognitive-sensor`, `contracts/schemas`+`examples`, `research/uasc-m2m`, `apps/webos-333`, `atlas_boot.html`, planning docs (CONTEXT_PACKET, FILE_MAP, PHASE_ROADMAP, PRE_ATLAS_MAP) | **Contract-first + doc-first from minute one.** 14 commits, ~695 files. First audit (CODEBASE_ANALYSIS.md) 2 days later. |
| **First Deploy** | 2026-02-09 | `public/`, `vercel.json`; "Deploy real CycleBoard app + WebOS simulator", "Deploy ATLAS CORE as main app with embedded WebOS" | Product goes **live on Vercel**. 36 commits Feb, then a March lull (20). |
| **Mosaic federation** | 2026-03-24 → 03-26 | `aegis-fabric`, then `docker-compose.yml` + `mirofish` + `mosaic-dashboard` + `mosaic-orchestrator` + `openclaw` | Single engine → **multi-service docker platform**. |
| **The Big Bang** | 2026-04-14 | `festival-project` structure, ~15 audit/arch docs (BACKEND_AUDIT, FRONTEND_AUDIT, RISK_ANALYSIS, SYSTEM_MANIFEST, COMPONENT_GRAPH, DATAFLOW_GRAPH…), `apps/blueprint-generator`+`code-converter`+`inpact`, `cortex`, `crucix`; the 118k-line "full system state sync" commit | **The watershed.** April added **1,965 files** — biggest month by 5×. Lead-in: `ws-gateway` (04-06), `uasc-executor` (04-10). `doctrine/` codified 04-18 (SEED, ROSETTA_STONE, OPTOGON_SPEC, BUILD_PLAN, FEST_PLAN). `optogon` born 04-19. |
| **Divergence + specialization** | late Apr → May | B forks to become **delta-scp** home (`delta-scp` first commit = "compression queue: repo URL → symbolic JSON"). A absorbs everything: `canvas-engine` (04-26), `png-substrate` (04-30), `minidocs` scale probes (05-04, 125k+20k line data dumps), `droplist`, `lattice`, `shardstate`, `atlas-map`, `hydra` | Last shared birth = optogon 04-19. Repos split here. |
| **Mass-commit sweep / frontier** | 2026-06-25 | 130-commit unmerged body on `feat/atlas-setup-ui` (103 in June alone). Big June-25 commits: fest-reconcile pipeline (56k), audit refresh + **vendored cytoscape** (39k), hydra digestion (22k), droplist spine bricks 1-4 (14k) | "Bank all WIP before main merge" sweep. Frontier earliest commit: `0ec5d67` 2026-05-02 (cortex→optogon wiring). |

**Commits per month** (Pre Atlas space): Jan 14 · Feb 36 · Mar 20 · **Apr 160** · May 65 · Jun 130.
**Files added per month** (space): Jan 695 · Feb 40 · Mar 284 · **Apr 1965** · May 344 · Jun 568.

---

## 2. What got iterated most (scope frequency)

**All-history top scopes (space):** droplist 30 · cognitive-sensor 26 · optogon 20 · shardstate 13 · canvas-engine 13 · lattice 12 · minidocs 8 · delta-scp 8 · atlas-map-api 8 · atlas-map 8 · delta-kernel 7 · anatomy-extension 7.

**The live frontier (130 unmerged commits) is dominated by:** droplist 28 · lattice 12 · cognitive-sensor 11 · atlas-map(-api) 16 · search-stack 4 · hydra 3. → **current active scope = droplist lifecycle + lattice graph + atlas-map GPS.**

---

## 3. Tendencies · idiosyncrasies · fingerprints

- **feat-heavy, test-light-as-a-type:** 192 `feat` vs **2 `test`** commits (space). Tests ride inside feat commits, not their own type. Heavy `docs` (50) and `merge` (41).
- **Doc-saturated codebase:** 389 `.md` + 302 `.json` + 20 `.mermaid` (space). Markdown is the **#2 "language."** Spec-first/contract-first culture; audit docs proliferate.
- **Language mix (space):** Python 584 · md 389 · json 302 · ts 248 · js 68 · html 62 · ps1 37 · svg 25 · tsx 24 · mjs 21 · mermaid 20. **Python-primary, TS for the engines.**
- **Conventional commits w/ precise scopes:** 337/425 conventional; `feat(<subsystem>):` is the house style.
- **Agent-driven parallelism baked in:** dozens of `claude/<adjective>-<scientist>-<hash>` branches + `.claude/worktrees/`. Claude authored 65 commits (space). Codex appears too (`codex/*` branches in B).
- **Renames ≫ deletes (66 renames):** work gets *relocated/reshaped*, rarely thrown away — matches the **"code = furniture, no throwing out"** doctrine.
- **Big "data-dump" commits:** minidocs scale probes (125k / 20k lines) = experiment telemetry committed wholesale; initial commits 128k = vendored OSS.
- **"Bank-before-merge" ritual:** recurring `chore: bank pending WIP … before main merge`.
- **Windows-native fingerprints:** 37 `.ps1`, `atlas.bat`, native `fest.exe`; the `\357\201\234…` mojibake festival paths = the **cp1252 / PUA encoding gotcha** (documented in memory).

---

## 4. Scope trajectory — narrow engine → tool factory

1. **Narrow:** one deterministic state engine (`delta-kernel`) + sensor + contracts. A behavioral-governance core.
2. **Productized:** CycleBoard / ATLAS CORE deployed on Vercel.
3. **Federated:** "Mosaic" multi-service platform (8+ services, docker-compose).
4. **Governed + orchestrated:** `doctrine/`, `festival-project`, `optogon` FSM — a doctrine-driven, festival-orchestrated, multi-agent build machine.
5. **Spawning standalone repos (the monorepo became a factory):**

| Repo | Born | Commits | Seed |
|---|---|---|---|
| everything-claude-code | 2026-01-17 | **1099** | "Complete Claude Code configuration collection" (parallel meta-track of skills/tooling) |
| POLARIS | 2026-02-22 | 6 | "general-purpose agent execution layer" |
| atlas | 2026-04-29 | 20 | "**initial atlas substrate distilled from pre-atlas**" |
| competitor-monitor | 2026-05-04 | 1 | consolidated repo |
| operator-system | 2026-05-05 | 11 | handoff scaffolding |
| anatomy-saas | 2026-06-25 | 1 | deterministic LLM-free anatomy compiler |
| binre | 2026-06-25 | 4 | RE pipeline baseline |

---

## 5. Tools & infra evident in history
Python/FastAPI (services have `.venv`), Node/Express (delta-kernel, crucix, ws-gateway), Vite+React (apps), Vercel (deploy). Infra: docker-compose, NATS (ws-gateway), Supabase (delta-scp v2), libSQL (delta-kernel spine, flag-gated), SQLite. Methodology tooling: Festival methodology (`fest.exe`), delta-scp symbolic compression, Claude Code worktrees + Codex, 49 JSON-Schema contracts (draft-07). Vendored OSS: **cytoscape** (lattice graph — the assemble-first win), firecrawl/browser-use under `tools/anatomy-research`.

---
*Caveat: counts are `--all` (all branches), so shared commits are counted in each clone. "Removed/abandoned" is comparatively rare; the repo prefers rename-over-delete. Identity inference (lionestenzol = Bruke's GitHub side) is high-confidence but not git-provable.*

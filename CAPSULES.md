# CAPSULES · the museum of unmerged versions

**Built:** 2026-06-26 · **Source:** every local branch with commits not on `origin/main`, both clones.

Each unmerged branch is a **time-capsule**: a frozen snapshot of what you were reaching for on a given day. In your own system's language, each is an **open loop with a record**. Nothing here is deleted, nothing is merged in haste. It is parked, dated, and navigable.

**Raw count:** 86 local branches in `Pre Atlas`, ~55 with unique work, collapsing to **~17 distinct capsules** (many are identical agent-worktree mirrors). 2 branches in `pre-atlas`.

**How to open a capsule:** `git log origin/main..<branch>` to read its intent · `git checkout <branch>` to stand inside it · `git checkout -` to come back.
**How to make it permanent (next step, see footer):** `git tag -a capsule/<name>-<date> <branch> -m "what I was reaching for"` freezes the tree forever even if the branch ref is later pruned.

---

## Era 1 · Genesis experiments (2026-01-12 to 01-14)
Small probes on the core engine, by early Codex + Claude agents.

| Capsule | Span | Commits | Reaching for | Status |
|---|---|---|---|---|
| `codex/implement-condition-step-type-in-executor` | 01-12 | 2 | MVP condition branching in the executor | parked |
| `codex/add-websocket-or-sse-support-for-state-updates` | 01-12 | 2 | realtime unified state streaming | parked |
| `codex/add-mode_since-field-to-system-state` | 01-12 | 2 | track mode-transition timestamps | parked |
| `claude/fix-pr-visibility-Ojufp` | 01-12 | 2 | TypeScript build-compat fixes | parked |
| `claude/analyze-codebase-vwqSm` | 01-12..14 | 3 | first comprehensive codebase analysis | parked |

## Era 2 · Deploy (2026-02-09)
| `claude/analyze-breaches-5gDlm` | 01-12..02-09 | 20 | ATLAS CORE dashboard + mobile-friendly deploy era | parked |

## Era 3 · Big Bang ship-wave (late April, 60-100 commits each)
The April explosion, fanned across agent worktrees. Three sub-themes.

**3a · Anatomy capture**
| Capsule | Span | Commits | Reaching for | Status |
|---|---|---|---|---|
| `claude/nostalgic-goldstine-f4830c` | →04-26 | 62 | `AnatomyV1.v1.json` schema — closes the anatomy-capture schema gap | parked |
| `claude/nifty-mclean-1b62c3` | →04-26 | 61 | formal AnatomyV1 JSON Schema + ajv validator | parked |
| `claude/gifted-rosalind-ca8a92` | →04-27 | 67 | anatomy-extension `buildSelector` correctness fix | parked |

**3b · Optogon / inPACT ship targets**
| Capsule | Span | Commits | Reaching for | Status |
|---|---|---|---|---|
| `claude/condescending-lumiere-d300af` | →04-27 | 72 | inPACT Signal ingestion (Ship Target #1) | parked |
| `feat/optogon-sitepull-adapter-ship3` | →04-27 | 72 | sitepull → Optogon ContextPackage adapter (Ship #3) | parked |
| `claude/vigorous-hoover-3db0c2` | →04-27 | 101 | optogon-calibrate: wire profile signals + feedback into delta-kernel `UserPreferenceStore` | parked |
| `claude/flamboyant-gates-54fb9c` | →04-27 | 68 | scraper pipeline audit + Codex second-opinion review | parked |
| `claude/interesting-bassi-26f4a5` | →04-27 | 72 | ws-gateway port move (clear inPACT :3006 collision) | parked |
| `claude/intelligent-payne-6fa7c6` + `claude/pensive-newton-1e606a` | →04-27 | 93 ×2 | gitignore vendored OSS + governor docs (mirror pair) | parked |

**3c · Cortex closed-loop (MAPE-K / BDI), Phases 0-3 (04-28)**
| Capsule | Span | Commits | Reaching for | Status |
|---|---|---|---|---|
| `claude/zealous-mclean-a9b079` | →04-28 | 94 | cortex Phase 0 dispatcher poll loop (D→E) | parked |
| `claude/result-signal-phase-1` | →04-28 | 94 | cortex+delta-kernel Phase 1 result signal (E→M) | parked |
| `claude/goal-wire-phase-2` | →04-28 | 94 | delta-kernel Phase 2 BDI goal wire (A→P) | parked |
| `claude/mode-polish-phase-3` | →04-28 | 94 | Phase 3 mode polish · regime gate | parked |
| `claude/closed-loop-integration` | →04-28 | 101 | integrate all phases into the closed-loop dispatcher | parked |

**3d · The PR #17 convergence (04-28)** — ~15 identical agent-worktree mirror branches, all frozen at the same `Merge pull request #17 from .../zealous-mclean` (95 commits): `bold-franklin`, `busy-haslett`, `clever-gauss`, `clever-goldwasser`, `clever-solomon`, `ecstatic-feistel`, `heuristic-shirley`, `musing-diffie`, `peaceful-wilson`, `pedantic-fermi`, `pensive-newton-d0f9e0`, `silly-thompson`, `stoic-noether`, `trusting-booth`, `wizardly-hellman`. **One capsule, fifteen tombstones.** Prune candidates (all point at the same tree).

## Era 4 · Substrate experiments (2026-05-01)
| Capsule | Span | Commits | Reaching for | Status |
|---|---|---|---|---|
| `claude/shardstate-coordination-ZxEgN` + `claude/magical-jang-7f9762` | →05-01 | 98 / 96 | shardstate formal library spec + purpose | parked |
| `worktree-agent-a96a802a89a795d63` | →05-01 | 98 | shardstate binary wire codec + 2-device sync (Ship 2) | parked |
| `worktree-agent-a4d4c15efb96c268d` | →05-01 | 98 | shardstate deterministic ops layer (Ship 6) | parked |
| `worktree-agent-a3fcd544b9dd3a99b` | →05-01 | 98 | shardstate two-agent demo + MCP client (Ship 5) | parked |
| `claude/trusting-germain-a57cb0` | →05-01 | 97 | png-substrate: integrity.v1 + fsm.v1 + conformance | parked |
| `claude/lucid-bohr-24156a` | →05-01 | 96 | png-substrate: lut.v1 + vm.v1 + alpha-strip mitigation | parked |
| `claude/heuristic-buck-35f73f` | →05-01 | 96 | png-substrate: scale tests + LSH-PNG + swap survey | parked |
| `claude/pensive-sinoussi-eb4d9c` | →05-01 | 96 | carbo-shrink encoder + frame-sidecar + extension wire | parked |
| `claude/elegant-black-71ab26` | →05-02 | 98 | privacy: gitignore `.claude/settings.local.json` | parked |

## Era 5 · Minidocs (2026-05-03)
| `claude/interesting-chaum-2944a8` | 05-03..04 | 8 | glyph page-recognizer + dedup probe | **ABORTED — proved PRECISION-DEGRADES-AT-SCALE** (a closed loop: a finding, not a failure) |

## Era 6 · The live frontier (2026-05-02 to 06-25)
The May→June lineage. **`feat/atlas-setup-ui` is HEAD — this is the live branch, not a capsule.**

| Branch | Span | Commits | What it is | Status |
|---|---|---|---|---|
| `feat/atlas-setup-ui` | 05-02..06-25 | 138 | **HEAD** · droplist lifecycle + atlas-setup + PyInstaller build | **LIVE** |
| `claude/crazy-benz-ff40ad`, `claude/recursing-newton-0d93ce`, `claude/silly-ardinghelli-e57a6d` | →06-25 | 130 ×3 | mirror worktrees of HEAD | prune candidates |
| `experiment/droplist-remediation-2026-06-15` | →06-25 | 102 | droplist per-plan autopilot flag (opt-out auto-advance) | parked |
| `claude/main-triage-26f4a5` | →06-15 | 49 | droplist PKT-010 schema (§17) | parked |
| `chore/droplist-label-len-doc-fix` | →06-15 | 50 | droplist doc fix: label limit 80→140 | parked |
| `chore/droplist-env-var-doc-fix` | →06-15 | 51 | droplist doc fix: signals URL rename | parked |
| `droplist-lifecycle-spine` | 06-25 | 1 | droplist bricks 1-4 (mark-off, headless, cron, daisy-chain) | folded into HEAD |
| `ship/droplist-2026-06-25` | 06-25 | 2 | droplist ship: write-API hardening, a11y, daemon | folded into HEAD |

## `pre-atlas` (hyphen clone)
| `feat/delta-scp-v2-graph-memory` | 06-21..25 | 6 | delta-scp v2: state-aware prune + flue + AST graph + Supabase-free demo gateway | **LIVE** (the specialist) |

---

## What this museum tells you
- Your build pattern is **fan-out then abandon**: late-April and early-May each spawned 8-15 worktree branches around one theme (anatomy, optogon, shardstate, png-substrate), most parked at ~95-100 commits the moment the theme cooled.
- **~18 mirror/tombstone branches** (PR-#17 cluster + HEAD mirrors) are safe prune candidates — they hold no unique tree.
- The one **closed** capsule (`minidocs`) is closed because it produced a *finding* (precision degrades at scale). That is what closure looks like: not "merged," but "resolved with a record."

## Next step (offered, not done)
1. **Tag for permanence** — annotate each distinct capsule as `capsule/<theme>-<date>` so the tree is frozen forever, then the branch refs can be pruned to clear the `git branch` noise. (~17 tags, fully reversible.)
2. **Prune the ~18 tombstone/mirror branches** — zero unique work lost.
3. **Then** re-anchor on the core close (the original autonomous pipeline). See `CAPSULE_self-mirror-saas.md` for the prize at the finish line.

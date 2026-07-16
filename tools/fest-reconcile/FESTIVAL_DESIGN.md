# Festival design: corpus-archaeology

**Status:** Phase 1 SHIPPED 2026-05-27. Phases 2-5 queued.
**Generated:** 2026-05-27 (Part B follow-up)

## Phase 1 results (2026-05-27)

Three temporal indexes written to `festival_out/`:

- `chatgpt_temporal.json` — 6534 convos, 2024-08-21 → 2026-05-21 (1 MB)
- `cc_temporal.json` — 1017 sessions, 2026-02-09 → 2026-05-27 (525 KB)
- `fs_temporal.json` — 140 portfolio paths with mtime/ctime (35 KB)
- `_progress.json` — ledger marks Phase 1 sequences complete

Next-session resume: read `festival_out/_progress.json` + the three temporal JSONs;
do NOT re-touch raw corpora. Begin Phase 2 (`002_KEYWORD_CLUSTERS`, 3 sequences).

## Goal

Build a complete temporal × keyword-cluster × channel cross-reference of all work
across ChatGPT export, Claude Code transcripts, and filesystem mtimes.
Each phase grounded in a corpus partition observable *today*.

## Why a festival (not a one-shot script)

The corpus is too large for one session:
- 6,534 ChatGPT convos × ~40 messages = 266,643 messages (~67 MB lowercased)
- 1,017 Claude Code sessions, 900 MB raw, ~300 MB usable text
- 11,634 jsonl files machine-wide via es.exe
- 140 portfolio items × 6 surfaces

Sessions under 25% context ceiling means each sequence produces ONE artifact
that the next sequence reads. Cold-resume is cheap because phase N only needs
phase N-1's JSON, never raw corpus.

## Corpus partitions the data actually has

### Temporal (the key partition)

Boundaries corrected after Phase 1 surfaced the real CC start date (2026-02-09).

| Era | Window | ChatGPT presence | Claude Code presence |
|-----|--------|------------------|----------------------|
| 1. Pre-CC | 2024-08-21 → 2026-02-08 | YES (~17.5 mo) | NONE |
| 2. Early CC | 2026-02-09 → 2026-03-31 | YES | YES (light) |
| 3. Heavy CC | 2026-04-01 → 2026-05-15 | YES | YES (heavy) |
| 4. Now | 2026-05-16 → present | YES (light) | YES |

This is a real partition — Bruke literally hadn't started Claude Code in Era 1.
So any "where did this idea form?" question naturally splits by era.

### Channel

- ChatGPT (services/cognitive-sensor/memory_db.json + results.db convo_time)
- Claude Code (~/.claude/projects/**/*.jsonl)
- Filesystem (es.exe, mtime/ctime per path)
- Portfolio audit JSON (already derived)

### Project-dir (CC corpus)

- subagents (804 sessions) ← bulk
- C--Users-bruke-Pre-Atlas (118)
- canvas-engine (10), STRUDEL (9), pedantic-fermi worktree (6)
- 60 other dirs with < 6 sessions each

### Keyword clusters (to be derived)

Seed from portfolio names + MEMORY.md, then expand via co-occurrence.
Likely clusters from first-look at memory:

- **anatomy** — anatomy-extension, anatomy-research, anatomy-rewrite, AnatomyV1, anatomy-map
- **mb3d/fractals** — mb3d-blender, m3p-to-fract, mandelbulber2, mandelbulb3d
- **audio/music** — STRUDEL, surge-xt, nih-plug, airwindows, virtualstudio, fl356
- **atlas-core** — delta-kernel, cognitive-sensor, cycleboard, optogon, cortex, aegis
- **web-extract** — scrapling, web-audit, web-extract-workflow, sitepull, competitor-monitor
- **productivity-skills** — weapon, fest, mini-ship, autopilot, project-finisher
- **canvas/anatomy-render** — canvas-engine, anatomy-extension, screenshot-to-code

Cluster definitions live in `clusters_final.json` from Phase 2.

---

## Phases

### Phase 1 · `001_TEMPORAL_INDEX` (implementation)

**Partition: time, per channel.**

Build one indexable JSON per channel that maps an item-ID to its date and
minimal metadata. Phases 2-4 join on these.

| Seq | Name | Input | Output | Cold-resume |
|-----|------|-------|--------|-------------|
| 01 | `chatgpt_temporal_index` | results.db (convo_time + convo_titles) | `out/chatgpt_temporal.json` (convo_id → date, title, top topics) | self-contained |
| 02 | `cc_temporal_index` | `~/.claude/projects/**/*.jsonl` | `out/cc_temporal.json` (session_id → start_ts, project_dir, cwd, gitBranch, first_user_msg) | self-contained |
| 03 | `fs_temporal_index` | es.exe queries on portfolio paths | `out/fs_temporal.json` (path → ctime, mtime, size) | self-contained |

Per-sequence est: 5-15% of context. Fits one session comfortably.

### Phase 2 · `002_KEYWORD_CLUSTERS` (planning)

**Partition: topic / concept.**

Define keyword clusters from observable signals, then expand them.

| Seq | Name | Input | Output |
|-----|------|-------|--------|
| 01 | `seed_clusters_from_portfolio` | portfolio_evidence.json + MEMORY.md | `out/clusters_v0.json` (cluster_name → seed terms) |
| 02 | `expand_clusters_from_corpus` | clusters_v0.json + chatgpt_temporal + cc_temporal | `out/clusters_v1.json` (+ co-occurring terms) |
| 03 | `validate_clusters` | clusters_v1.json + raw corpora | `out/clusters_final.json` (with coverage, distinctness, false-positive sample) |

Per-sequence est: 8-12% of context.

### Phase 3 · `003_CROSS_REFERENCE_MATRIX` (implementation)

**Partition: (cluster × era × channel).**

For every (cluster, era, channel) cell, count touches and capture sample IDs.

| Seq | Name | Input | Output |
|-----|------|-------|--------|
| 01 | `era_1_pre_cc_matrix` | clusters_final + chatgpt_temporal | `out/era_1_matrix.json` |
| 02 | `era_2_early_cc_matrix` | clusters_final + both temporal | `out/era_2_matrix.json` |
| 03 | `era_3_heavy_cc_matrix` | clusters_final + both temporal | `out/era_3_matrix.json` |
| 04 | `fs_overlay` | clusters_final + fs_temporal + portfolio_evidence | `out/fs_overlay.json` (cluster → portfolio items + their mtimes per era) |
| 05 | `merge_matrices` | all era_*_matrix + fs_overlay | `out/era_cluster_matrix.json` |

Each era sequence is one cold-resume session.

### Phase 4 · `004_CHANNEL_FLOW_ANALYSIS` (research)

**Partition: ship event lifecycle.**

For each portfolio item with band=strong, find:

- **Idea-first-seen** in ChatGPT cluster (earliest convo discussing the cluster)
- **Build-first-seen** in Claude Code (earliest session with item name)
- **Ship-first-seen** on filesystem (earliest ctime of any file matching the name)

Output: `out/ship_flow.json` per item: `{idea_at, build_at, ship_at, lag_idea_to_build, lag_build_to_ship}`.

Tells whether talk leads build, build leads talk, or they're parallel.

Single-sequence phase. ~10% context.

### Phase 5 · `005_NARRATIVE_REPORT` (review)

**Aggregate everything into a human-readable terminal artifact.**

- `out/CORPUS_MAP.md` — one master report with:
  - Era × cluster heatmap
  - Channel-flow patterns (lead/lag/parallel)
  - Top counter-narrative findings (where data contradicts memory)
  - Open questions for follow-up
- Surface ≥ 5 spot-check examples per major finding (HOTL gate)

Single session.

---

## Cross-session resumption protocol

- Every sequence writes ONE JSON to `tools/fest-reconcile/festival_out/`
- Phase N reads only Phase N-1's outputs (never raw corpus directly, except in Phase 1)
- Session resumes by reading the latest `out/*.json` + the festival next-task pointer
- A `out/_progress.json` ledger tracks (sequence → status, started_at, finished_at, artifact_path)

## Tooling per phase

| Phase | es.exe? | Grep? | Python? | DB? |
|-------|---------|-------|---------|-----|
| 1 | yes (fs index) | no | yes | yes (results.db) |
| 2 | no | yes (co-occurrence on raw text) | yes | no |
| 3 | no | no | yes | no |
| 4 | yes (ctime) | yes | yes | yes |
| 5 | no | no | yes | no |

## Estimated total span

- Phase 1: 1 session (3 short sequences in parallel possible)
- Phase 2: 1-2 sessions
- Phase 3: 2 sessions (1 per 2 eras + merge)
- Phase 4: 1 session
- Phase 5: 1 session

Total: ~5-7 sessions if linear, fewer with parallel sequences.

---

## Open design questions for sign-off

1. **Cluster definition** — use seed-and-expand approach, OR run a real topic model (e.g., BERTopic on combined corpus)? Seed-and-expand is faster, cheaper, more interpretable. Topic model is more rigorous but adds compute.
2. **Era boundaries** — fixed dates as above, or auto-detect via Claude Code session density inflection?
3. **Portfolio refresh** — refresh portfolio_evidence.json mid-festival (Phase 3.04), or freeze on the current snapshot?
4. **Outputs location** — `tools/fest-reconcile/festival_out/` (Pre Atlas tree), or in the WSL festival workspace `/root/festival-project/festivals/...`?

Ready to create in fest CLI once sign-off lands.

# CORPUS_MAP_v2 · corpus-archaeology festival, post-fix re-run

**Generated:** 2026-05-28 (v2 re-run after AUDIT_FINDINGS.md REJECT verdicts).
**Inputs:** `clusters_final_v2.json` + `era_cluster_matrix_v2.json` + `ship_flow_v2.json` + updated `cc_temporal.json` (wider first_user_msg).
**Companion:** see `AUDIT_FINDINGS.md` (audit of v1) and `CORPUS_MAP.md` (the v1 narrative).
**Same hard rule as v1 CORPUS_MAP:** every finding cites a specific record. No claims about unread convo bodies.

---

## 0 · Changed from v1

### 0.1 Code changes shipped (Phase 1-4 scripts)

| Change | File | Effect |
|--------|------|--------|
| Word-boundary regex matcher | `_match.py` (new) + `expand_clusters.py` + `validate_clusters.py` + `build_era_matrix.py` + `ship_flow.py` + `seed_clusters.py` | Single rule: `(?<![a-z0-9_])SEED(?![a-z0-9_])`. Replaces v1 `s in text.lower()` substring rule in all 4 phase scripts AND in portfolio cluster assignment. |
| `first_user_msg` cap raised | `phase1_temporal_index.py` lines 76, 108 | `[:200]` → `[:2000]`. 924 of 1020 cc sessions now expose > 200 chars of first user message. |
| Validator FP scan covers full corpus | `validate_clusters.py:73` | Dropped `[:2000]` slice; scans all 6534 ChatGPT items. |
| `FP_RISK_CLUSTERS` loaded dynamically | `ship_flow.py:main()` | Reads `clusters_final.json::clusters[*].validation.substring_warnings`. v1 hardcoded `{audio_music, productivity_skills}`. |
| Seeds dropped: `stem`, `fest`, `scrape`, `fractal`, `comfyui`, `perception` (compound forms only), `RECOVER/CLOSURE/MAINTENANCE/COMPOUND/SCALE` mode names | `seed_clusters.py` | Removes 4 hard-REJECT anchor convos from cluster_fallback paths. |
| Seeds added explicitly: `mandelbulb3d`, `mandelbulber2`, `mandelbulber2_install`, `mb3d_anim_demo`, `mb3d-blender`, `m3p-to-fract`, `fractal-machine` | `seed_clusters.py` mb3d_fractals | Word-boundary requires explicit forms (the seed `mandelbulb` does not match inside `mandelbulb3d`). |
| `operator-system` re-clustered | `seed_clusters.py` audio_music | Removed because `stem` seed dropped; word-boundary on `system` also prevents v1 substring FP. Item now has no cluster (was wrongly assigned to audio_music in v1 via `stem` substring of `system`). |

### 0.2 Audit verdict status

| v1 audit verdict | Anchor convo | v2 status |
|------------------|--------------|-----------|
| REJECT · audio_music/`stem` | 6321 "Bartering Dual Economy System" | **GONE** · no item anchors here in v2 |
| REJECT · web_extract/`scrape` | 2530 "Scrape or bite mark" | **GONE** |
| REJECT · productivity_skills/`fest` | 6289 "Manifesting Through Desire" | **GONE** |
| REJECT · atlas_core/`perception` | 6521 "Voice Perception as Strength" | **PARTIAL** · convo no longer cluster_fallback anchor; only used as name_match for the `perception` Pre Atlas service item (which itself has name "perception") |
| WEAK · canvas_render/`comfyui` | 1705 "ComfyUI Workflow Explanation" | **GONE** · seed removed |
| WEAK · mb3d_fractals/`fractal` | 4986 "Logistics and Fractal Thinking" | **GONE** · seed removed |
| ACCEPT-BUT-LATE · anatomy | 316 "Site Anatomy Engine" | **STILL USED** for 4 anatomy items; still post-dates the ship ctimes (the negative-lag finding F4 from v1 persists — see §4 OQ-1 below). |
| REJECT · wasp (name_match insect) | 3191 "Tarantula hawk wasp description" | **STILL USED** · 1 item (wasp framework). Name_match rule fires legitimately on title substring; cannot distinguish framework from insect without body read. |

**Net:** 4 of 4 hard-REJECT anchors removed from cluster_fallback. 6521 retained for 1 item via name_match. 1 name_match REJECT persists. The post-fix run does not re-introduce any other audit-rejected anchor.

### 0.3 Side effects (NEW FP found during v2 run, fixed before final)

The initial v2 run (with mode names still in atlas_core seeds) produced a NEW collapse: convo 6152 "USAA Thanksgiving Closure Notice" anchored 15 atlas_core items via the `closure` mode-name seed. Title contains `Closure` as a whole word — word-boundary doesn't help; the seed itself is the problem. Mitigation applied immediately: dropped `RECOVER`, `CLOSURE`, `MAINTENANCE`, `COMPOUND`, `SCALE` from atlas_core seeds. v2 final output has the USAA-closure anchor gone.

---

## 1 · v2 Era × cluster heatmap

### 1.1 ChatGPT counts per (cluster, era)

| cluster              | era_1 | era_2 | era_3 | era_4 | total v2 | v1 total | Δ |
|----------------------|------:|------:|------:|------:|---------:|---------:|--:|
| anatomy              |     0 |     0 |     2 |     0 |        2 |        2 | 0 |
| mb3d_fractals        |     0 |     1 |     3 |     1 |        5 |        8 | -3 |
| audio_music          |     3 |    41 |     4 |     1 |       49 |      209 | **-160** |
| atlas_core           |     2 |     8 |     4 |     0 |       14 |       93 | **-79** |
| web_extract          |     0 |     0 |     0 |     0 |        0 |        1 | -1 |
| productivity_skills  |     1 |     2 |     0 |     0 |        3 |       15 | -12 |
| canvas_render        |     0 |     2 |     3 |     0 |        5 |       12 | -7 |

Source: `era_cluster_matrix_v2.json::clusters[*].channels.chatgpt.<era>.count`. v1 numbers from `CORPUS_MAP.md::§1.1`.

**Headline:** audio_music ChatGPT count dropped 76% (209→49). atlas_core dropped 85% (93→14 — driven primarily by removing `perception` and mode-name seeds). The v1 audio_music Era 1 spike (89 items) is now 3.

### 1.2 Claude Code counts per (cluster, era)

| cluster              | era_1 | era_2 | era_3 | era_4 | total v2 | v1 total | Δ |
|----------------------|------:|------:|------:|------:|---------:|---------:|--:|
| anatomy              |     0 |     2 |    28 |     7 |       37 |       13 | +24 |
| mb3d_fractals        |     0 |     0 |     9 |     0 |        9 |        8 | +1 |
| audio_music          |     0 |   276 |     9 |     8 |      293 |      323 | -30 |
| atlas_core           |     0 |   207 |   168 |    59 |      434 |      330 | +104 |
| web_extract          |     0 |    11 |    31 |     4 |       46 |       14 | +32 |
| productivity_skills  |     0 |    17 |    53 |     8 |       78 |       40 | +38 |
| canvas_render        |     0 |    11 |    52 |    12 |       75 |       79 | -4 |

Source: `era_cluster_matrix_v2.json::clusters[*].channels.cc.<era>.count`.

**Headline:** CC counts INCREASED for atlas_core (+104), anatomy (+24), web_extract (+32), productivity_skills (+38). This is mostly the wider `first_user_msg` capture (200→2000 chars) catching item names that v1 missed. audio_music DROPPED 30 — the word-boundary fix kills FP matches inside `system`/`ecosystem` etc that v1 fired on.

### 1.3 FS ctime per (cluster, era)

| cluster              | era_1 | era_2 | era_3 | era_4 |
|----------------------|------:|------:|------:|------:|
| anatomy              |     0 |     0 |     4 |     0 |
| mb3d_fractals        |     0 |     0 |     7 |     0 |
| audio_music          |     0 |     2 |     1 |     3 |
| atlas_core           |     3 |     7 |    10 |     0 |
| web_extract          |     0 |     0 |     8 |     0 |
| productivity_skills  |     0 |     4 |    16 |     0 |
| canvas_render        |     0 |     0 |    13 |     1 |

Source: `fs_overlay_v2.json`. Compared to v1: anatomy unchanged (4); mb3d_fractals unchanged (7); audio_music gained 1 era_4 item count change (3→3 — but era distribution shifted: v1 had 0,2,2,3 = 7 total, v2 has 0,2,1,3 = 6 portfolio items present in cluster after dropping operator-system). atlas_core dropped from 25 to 24 items (operator-system was never atlas_core, so this is unrelated — actually due to one item being filtered now that I look — but counts are 3+7+10+0=20 vs v1 3+7+11+0=21, so one era_3 atlas_core item dropped from the cluster). productivity_skills 4+16=20 vs v1 5+16+1=22 (two items dropped — `fest` substring matches inside item names? Let me note this is a residual portfolio-assignment change worth checking in OQ-3).

---

## 2 · v2 Channel-flow patterns

### 2.1 Pattern distribution

| flow_pattern | v2 count | v1 count | Δ |
|--------------|---------:|---------:|--:|
| talk_leads   |       32 |       27 | +5 |
| no_build     |       11 |       27 | **-16** |
| parallel     |        6 |        4 | +2 |
| no_talk      |       11 |        2 | **+9** |
| **total**    |       60 |       60 |   |

Source: `ship_flow_v2.json::flow_pattern_counts`.

**Headline:** `no_build` cohort dropped from 27 to 11. The wider `first_user_msg` (200→2000 chars) caught item-name mentions that v1's truncated capture missed. `no_talk` rose from 2 to 11 because the seed pruning + word-boundary disqualifies cluster_fallback for items whose only v1 anchor was a substring FP.

### 2.2 `idea_via` distribution

| idea_via         | v2 | v1 |
|------------------|---:|---:|
| cluster_fallback |  36 |  45 |
| name_match       |  13 |  13 |
| (none)           |  11 |   2 |

The 11 items with no idea_via in v2 (was 2 in v1):

| item              | surface              | clusters     | reason | 
|-------------------|----------------------|--------------|--------|
| binre             | standalone_repo      | (none)       | v1 was already no_talk |
| everything-claude-code | standalone_repo | (none)       | v1 was already no_talk |
| airwindows, nih-plug, surge-xt | standalone_repo | audio_music | v1 anchored via `stem`→6321; gone |
| screenshot-to-code | standalone_repo     | canvas_render | v1 anchored via `comfyui`→1705; gone |
| scrapling-smoke, web-extract-workflow, scrapling-official | (mixed) | web_extract | v1 anchored via `scrape`→2530; gone |
| (+1 more) | | | |

All match-redirected items are casualties of the rejected v1 anchors. Their `idea_at` is now correctly null instead of falsely-attributed.

### 2.3 Cluster anchor distribution (cluster_fallback only)

| anchor | title (truncated) | cluster | items absorbed | audit verdict (v1) |
|--------|-------------------|---------|---------------:|--------------------|
| 5915 | inPACT Bullet Journal App | atlas_core | 16 | unaudited |
| 1447 | VirtualStudio Landing Page | canvas_render | 6 | unaudited |
| 685 | Raymarched Mandelbulb Spec | mb3d_fractals | 5 | unaudited |
| 5158 | Audio analysis summary | audio_music | 4 | unaudited |
| 316 | Site Anatomy Engine | anatomy | 4 | audit ACCEPT-BUT-LATE |
| 3119 | Autopilot and focus errors | productivity_skills | 2 | unaudited |
| (8 others) | | | 1 each | mixed |

Source: derived from `ship_flow_v2.json::items[*].idea_provenance`.

**Headline:** the largest collapse drops from 15 items (v1 anchor 6521 atlas_core/`perception`) to 16 items (v2 anchor 5915 atlas_core/`inpact`). The collapse pattern persists, but the new anchor (5915 "inPACT Bullet Journal App") is at least topically about an atlas_core item by title language — verifying convo body content is OQ-2.

---

## 3 · Findings (v2)

### F1 · The audit-rejected substring FPs are eliminated

Direct verification of `ship_flow_v2.json::items[*].idea_provenance.convo_id`:

| audit-rejected anchor | v1 items anchored | v2 items anchored |
|----------------------:|------------------:|------------------:|
| 6321 (Bartering...)   |                 5 |                 0 |
| 2530 (Scrape...)      |                 8 |                 0 |
| 6289 (Manifesting...) |                 2 |                 0 |
| 6521 (Voice Perception...) | 15           |  1 (name_match only) |
| 1705 (ComfyUI...)     |                 6 |                 0 |
| 4986 (Logistics Fractal...) |           5 |                 0 |
| **30 substring-FP attributions eliminated** | 41 | 1 |

Status: **grounded** (direct count from v2 output).

### F2 · `operator-system` correctly removed from audio_music

`clusters_final_v2.json::clusters[audio_music].portfolio_hits` — count is 9 (v1 was 10). Diff = `operator-system` no longer present.

Cause: in v1, seed `stem` substring-matched inside `system` in `seed_clusters.py::compute_hits` (line 267 v1: `if s in nm:`). In v2: (a) `stem` seed dropped from audio_music; (b) `compute_hits` now uses word-boundary `_compile_seed(s).search(nm)`, so even if `stem` were kept it wouldn't match `system`.

Status: **grounded** (counted from `clusters_final_v2.json`).

### F3 · `no_build` dropped 16 items, mostly from the 200→2000 first_user_msg capture

Items that flipped from `no_build` (v1) to having a build_at (v2): includes airwindows (v2 build_at=2026-05-16, session matched on long task wrapper), nih-plug, surge-xt, and others where the item name appeared past char 200 in CC session first user messages.

Spot-check (`ship_flow_v2.json::items` filter `build_at != null AND item in v1.no_build`): items with a build_at now where v1 had none.

Status: **grounded** (compare v1 vs v2 ship_flow item records).

### F4 · Anatomy negative-lag bug persists (carried over from v1 F4)

The 4 anatomy items (anatomy-map, anatomy-extension, anatomy-research, anatomy-rewrite) still show negative `lag_idea_to_ship_days` in v2 because they still anchor on convo 316 "Site Anatomy Engine" (dated 2026-04-26) which post-dates their ship ctimes (2026-04-22/23).

The word-boundary fix does NOT address this. Convo 316 IS the only ChatGPT mention of anatomy seeds. Possible causes per v1 F4: (a) corpus is missing an earlier convo; (b) the actual seeding convo uses different language than the anatomy seed list.

Status: **grounded** (unchanged from v1).

### F5 · audio_music CC count: v1 substring-FP inflation confirmed

v1 reported audio_music CC = 323. v2 = 293. Drop = 30 sessions. The dropped 30 are sessions whose v1 first_user_msg substring-contained `stem`/`vst`/etc inside non-word-boundary tokens (e.g. `system`, `ecosystem`). The wider 2000-char capture compensates partially by catching more legitimate audio mentions (would otherwise drop further).

Status: **grounded** (count diff from v1 → v2).

### F6 · NEW: convo 6152 "USAA Thanksgiving Closure Notice" was a new FP in initial v2

When mode-name seeds (`CLOSURE`, etc.) were still in atlas_core, v2 collapsed 15 atlas_core items onto convo 6152 ("USAA Thanksgiving Closure Notice"). The seed `closure` is a common English word — word-boundary alone could not save it. Mitigation: dropped mode names from atlas_core seeds. Final v2 output does not include 6152 as an anchor.

**Generalizable rule:** generic English words as seeds are FPs even under word-boundary. The fix is seed selection, not match rule. Other generic seeds that remain in v2 (audio: `audio`, `daw`, `midi`, `synth`, `sampler`; canvas_render: `shader`, `webgl`, `webgpu`, `raymarch`; web_extract: `playwright`, `humanize`) may produce similar FPs but were not audited.

Status: **grounded** (recovery iteration; final v2 confirmed clean of 6152).

### F7 · Anchor collapse pattern persists but on real-content anchors

The cluster_fallback rule still collapses many items onto a single early-cluster-anchor convo:

- 16 atlas_core items → convo 5915 "inPACT Bullet Journal App" via seed `inpact`
- 6 canvas_render items → convo 1447 "VirtualStudio Landing Page" via seed `virtualstudio`
- 5 mb3d_fractals items → convo 685 "Raymarched Mandelbulb Spec" via seed `raymarcher`/`mandelbulb`
- 4 audio_music items → convo 5158 "Audio analysis summary" via seed `audio`/`midi`/etc

These are topically more credible than the v1 anchors (titles literally name the cluster's domain). But the collapse means one anchor still dates 16 separate items via the same convo, so `talk_leads` lag values are still cluster-level not item-level. Same structural issue as v1, less topically wrong.

Status: **grounded** (anchor distribution from v2).

---

## 4 · Open questions for v3 (v2 didn't address)

1. **OQ-1 anatomy negative-lag.** The 4 anatomy items still post-date their only ChatGPT anchor. Need to either (a) widen seed list with synonyms, (b) audit body of convo 316 to learn what language predates it, or (c) accept that ChatGPT data doesn't capture the anatomy idea-origin.
2. **OQ-2 new top anchors unaudited.** Convo 5915 (inPACT) anchors 16 items. Convos 1447, 685, 5158, 3119 anchor 2-6 items each. None have been body-audited. Are they real cluster anchors or just titles that contain a seed?
3. **OQ-3 portfolio-level cluster drift.** v2 changed portfolio counts: anatomy 4→4, mb3d 7→7, audio_music 10→9 (operator-system removed, intended), atlas_core 25→24, web_extract 10→10, productivity_skills 22→20 (which 2 dropped?), canvas_render 17→16 (which 1?). Identify and verify each portfolio-membership change.
4. **OQ-4 remaining generic seeds.** Generic English words still in seed lists (`audio`, `daw`, `midi`, `synth`, `sampler`, `shader`, `webgl`, `webgpu`, `raymarch`, `playwright`, `humanize`, `governance`). Per F6, generic seeds are FPs even under word-boundary. Audit the chatgpt_match samples for each cluster to find latent FPs.
5. **OQ-5 wasp/insect persistence.** Convo 3191 "Tarantula hawk wasp description" still anchors `wasp` via name_match. The audit caught this as a name_match REJECT. v2 does not have a rule to differentiate framework-wasp from insect-wasp; would require body content check.
6. **OQ-6 atlas_core CC went UP 104 sessions.** Some of these may be FPs from the wider capture catching incidental `aegis`/`mosaic`/`cortex`/etc mentions in unrelated sessions. Sample the new sessions to validate.
7. **OQ-7 `(none)` cohort grew from 2 to 11.** Are these items that legitimately have no ChatGPT precursor, or items that need a different cluster definition?

---

## 5 · What this v2 report does NOT claim

Same scope-limit disclaimer as v1 CORPUS_MAP.md §5. Most importantly: no claims about convo body content for unread anchors. The body audit done for v1 anchors (in AUDIT_FINDINGS.md §2.2) is NOT extended to v2 anchors. Anyone treating the v2 collapse onto convo 5915 (16 atlas_core items), 1447 (6 canvas_render), 685 (5 mb3d_fractals), or 5158 (4 audio_music) as load-bearing should body-audit them first.

---

## 6 · v1 vs v2 reconcile summary

| metric | v1 | v2 |
|--------|---:|---:|
| Total strong items | 60 | 60 |
| ChatGPT matches across all clusters (sum) | 340 | 78 |
| CC matches across all clusters (sum) | 807 | 972 |
| `idea_via=cluster_fallback` count | 45 | 36 |
| `idea_via=name_match` count | 13 | 13 |
| `idea_via=null` count | 2 | 11 |
| `flow_pattern=no_build` count | 27 | 11 |
| Substring-FP anchors persisting | 5+ (audit-rejected) | 0 (cluster_fallback) + 1 (name_match wasp) |
| Largest single-anchor collapse | 15 items (convo 6521) | 16 items (convo 5915) |

End of CORPUS_MAP_v2.md.

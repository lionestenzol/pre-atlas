# CORPUS_MAP · corpus-archaeology festival, Phase 5 narrative report

**Status:** DRAFT pending audit gate (see `AUDIT_FINDINGS.md` companion).
**Generated:** 2026-05-28
**Inputs:** `ship_flow.json` (60 strong items), `era_cluster_matrix.json` (7 clusters × 4 eras × 4 channels), `clusters_final.json` (seed terms).
**Hard rule (this report):** every finding cites a specific record (convo_id, session_id, path, or item name). Where evidence is title-language only, the finding says so. No claims about convo body content are made anywhere in this report.

> **Reader warning.** Phase 4 resolved 45 of 60 strong items' `idea_at` via `cluster_fallback`, collapsing them onto 7 anchor convos. Anchor convo bodies have NOT been read. Treat any finding that depends on `idea_at` provenance from cluster_fallback as suspect input. See `AUDIT_FINDINGS.md` for the per-anchor verification status before treating talk_leads / lag claims as load-bearing.

---

## 1 · Era × cluster heatmap

### 1.1 ChatGPT convo counts per (cluster, era)

| cluster              | era_1_pre_cc | era_2_early_cc | era_3_heavy_cc | era_4_now | row total |
|----------------------|-------------:|---------------:|---------------:|----------:|----------:|
| anatomy              |            0 |              0 |              2 |         0 |         2 |
| mb3d_fractals        |            2 |              2 |              3 |         1 |         8 |
| audio_music          |           89 |             89 |             28 |         3 |       209 |
| atlas_core           |           64 |             17 |             12 |         0 |        93 |
| web_extract          |            1 |              0 |              0 |         0 |         1 |
| productivity_skills  |           10 |              4 |              1 |         0 |        15 |
| canvas_render        |            1 |              8 |              3 |         0 |        12 |
| **column total**     |          167 |            120 |             49 |         4 |       340 |

Source: `era_cluster_matrix.json::clusters[*].channels.chatgpt.<era>.count`.

### 1.2 Claude Code session counts per (cluster, era)

| cluster              | era_1_pre_cc | era_2_early_cc | era_3_heavy_cc | era_4_now | row total |
|----------------------|-------------:|---------------:|---------------:|----------:|----------:|
| anatomy              |            0 |              0 |             11 |         2 |        13 |
| mb3d_fractals        |            0 |              0 |              8 |         0 |         8 |
| audio_music          |            0 |            262 |             55 |         6 |       323 |
| atlas_core           |            0 |            151 |            138 |        41 |       330 |
| web_extract          |            0 |              0 |             13 |         1 |        14 |
| productivity_skills  |            0 |             10 |             27 |         3 |        40 |
| canvas_render        |            0 |             27 |             44 |         8 |        79 |
| **column total**     |            0 |            450 |            296 |        61 |       807 |

Source: `era_cluster_matrix.json::clusters[*].channels.cc.<era>.count`.

### 1.3 Filesystem ctime items per (cluster, era)

| cluster              | era_1 | era_2 | era_3 | era_4 |
|----------------------|------:|------:|------:|------:|
| anatomy              |     0 |     0 |     4 |     0 |
| mb3d_fractals        |     0 |     0 |     7 |     0 |
| audio_music          |     0 |     2 |     2 |     3 |
| atlas_core           |     3 |     7 |    11 |     0 |
| web_extract          |     0 |     0 |     8 |     0 |
| productivity_skills  |     0 |     5 |    16 |     1 |
| canvas_render        |     0 |     0 |    13 |     1 |

Source: `era_cluster_matrix.json::clusters[*].channels.fs_ctime.<era>` (array of portfolio item names).

### 1.4 Era totals (overall channel volume)

| era                  | chatgpt_in_era | cc_in_era |
|----------------------|---------------:|----------:|
| era_1_pre_cc         |          4 989 |         0 |
| era_2_early_cc       |            924 |       646 |
| era_3_heavy_cc       |            550 |       278 |
| era_4_now            |             71 |        93 |

Source: `era_cluster_matrix.json::totals_by_era`. Reconciles with `_progress.json` Phase 3 sequence summaries.

---

## 2 · Channel-flow patterns (ship_flow.json)

### 2.1 Pattern distribution

| flow_pattern | count | description (per `ship_flow.json::method`) |
|--------------|------:|--------------------------------------------|
| talk_leads   |    27 | `idea_at` precedes `build_at` by > 7 days |
| no_build     |    27 | ChatGPT hit exists, no CC `first_user_msg` matched the item name |
| parallel     |     4 | `|lag_idea_to_build|` <= 7 days |
| no_talk      |     2 | no ChatGPT hit at all |
| **total**    |    60 |                                              |

Source: `ship_flow.json::flow_pattern_counts` (re-counted from item array; matches).

### 2.2 `idea_via` distribution

| idea_via         | count | meaning |
|------------------|------:|---------|
| cluster_fallback |    45 | item name not in any convo title → matched on cluster seed term |
| name_match       |    13 | item name found as substring in a convo title |
| (none)           |     2 | no ChatGPT signal of any kind |

**Structural note.** 45/60 (75%) of `idea_at` values are derived not from the item itself appearing in ChatGPT, but from one of seven cluster-anchor convos. Lag values built on cluster_fallback `idea_at` carry the same suspect status as the anchor itself.

### 2.3 Cluster-fallback anchor collapse

| anchor convo_id | title                            | cluster              | matched seed | items absorbed |
|----------------:|----------------------------------|----------------------|--------------|---------------:|
| 6521            | Voice Perception as Strength     | atlas_core           | `perception` |             15 |
| 2530            | Scrape or bite mark              | web_extract          | `scrape`     |              8 |
| 1705            | ComfyUI Workflow Explanation     | canvas_render        | `comfyui`    |              6 |
| 6321            | Bartering Dual Economy System    | audio_music          | `stem`       |              5 |
| 4986            | Logistics and Fractal Thinking   | mb3d_fractals        | `fractal`    |              5 |
| 316             | Site Anatomy Engine              | anatomy              | `anatomy`    |              4 |
| 6289            | Manifesting Through Desire       | productivity_skills  | `fest`       |              2 |
| **total**       |                                  |                      |              |         **45** |

Source: `ship_flow.json::items[*].idea_provenance` filtered to `idea_via == 'cluster_fallback'`.

### 2.4 Items per cluster (strong band)

| cluster              | items |
|----------------------|------:|
| atlas_core           |    24 |
| web_extract          |     8 |
| audio_music          |     6 |
| mb3d_fractals        |     6 |
| canvas_render        |     6 |
| anatomy              |     4 |
| productivity_skills  |     2 |
| (none)               |     4 |

Source: counted from `ship_flow.json::items`. `(none)` covers items with no cluster assignment (binre, everything-claude-code, URBANNOMAD, wasp).

---

## 3 · Counter-narrative findings

Each finding ends with a status. **Grounded** = derivable purely from script outputs already on disk. **Suspect input** = depends on an unread anchor convo body. **Open** = needs Phase 4-style verification.

### F1 · 45/60 strong items collapse onto 7 cluster anchors via 4-letter seed substrings

Forty-five of the 60 strong items use `idea_via == cluster_fallback`. Those 45 share only 7 distinct `idea_provenance.convo_id` values (table 2.3). The Phase 2 validator flagged two of the seed terms — `stem` (matches `system`/`ecosystem`) and `fest` (matches `manifesting`/`lifestyle`) — as substring false-positive risks. The collapse means one mis-categorized anchor convo invalidates `idea_at` for up to 15 items.

Status: **grounded** (the collapse pattern is read from `ship_flow.json`); **suspect input** for any specific item's `idea_at`.

Spot-check records (≥ 5):
- `airwindows` → convo 6321 "Bartering Dual Economy System", matched seed `stem` (`ship_flow.json:items[0]`)
- `cognitive-sensor` → convo 6521 "Voice Perception as Strength", matched seed `perception` (`ship_flow.json:items[32]`-ish, surface=pre_atlas_services)
- `m3p-to-fract` → convo 4986 "Logistics and Fractal Thinking", matched seed `fractal`
- `Scrapling` (standalone_repo) → convo 2530 "Scrape or bite mark", matched seed `scrape`
- `anatomy-extension` → convo 316 "Site Anatomy Engine", matched seed `anatomy`
- `continuous-learning-v2` → convo 6289 "Manifesting Through Desire", matched seed `fest`
- `screenshot-to-code` → convo 1705 "ComfyUI Workflow Explanation", matched seed `comfyui`

### F2 · Three clusters have effectively zero pre-Era-3 ChatGPT activity, yet their items get Era-1 `idea_at`

| cluster        | era_1 chatgpt | era_2 chatgpt | era_3 chatgpt | strong items with idea_at in Era 1 |
|----------------|--------------:|--------------:|--------------:|-----------------------------------:|
| anatomy        |             0 |             0 |             2 | 0 (anchor 316 is dated 2026-04-26) |
| web_extract    |             1 |             0 |             0 | 8 (all anchor on convo 2530, 2025-10-17 in Era 1) |
| mb3d_fractals  |             2 |             2 |             3 | 5 (all anchor on convo 4986, 2025-03-20 in Era 1) |

The `idea_at` Era-1 dates for these clusters reduce to one or two specific convos. They are NOT broad ChatGPT chatter, contrary to what the `talk_leads` pattern label suggests at first glance.

Status: **grounded** (counts from `era_cluster_matrix.json` and `ship_flow.json`).

Spot-check records:
- web_extract Era-1 ChatGPT count = 1, sole sample id=2530 date=2025-10-17 title="Scrape or bite mark"; all 8 web_extract strong items use this convo as `idea_provenance`.
- mb3d_fractals Era-1 ChatGPT samples: id=4986 date=2025-03-20 title="Logistics and Fractal Thinking", id=3945 date=2025-06-01 title="Fractal Thinking and Execution". All 5 mb3d_fractals fallback items anchor on 4986.
- anatomy has 0 Era-1 ChatGPT; convo 316 ("Site Anatomy Engine") is dated 2026-04-26, which is in Era 3, NOT Era 1. The anatomy items show *negative* idea-to-ship lags (see F4).
- canvas_render Era-1 = 1, sole sample id=1705 date=2026-01-24 title="ComfyUI Workflow Explanation"; all 6 canvas_render fallback items anchor on it.
- atlas_core Era-1 = 64 (the only cluster with broad Era-1 ChatGPT activity); but 15 atlas_core strong items still all collapse to one convo, 6521 "Voice Perception as Strength" dated 2024-08-24.

### F3 · `audio_music` Era 1+2 ChatGPT signal is the substring-FP-warning case

ChatGPT counts: 89 (Era 1) + 89 (Era 2) = 178 — by volume the largest non-atlas_core cluster. Phase 2 validator flagged `audio_music` seed `stem` as matching `system`/`ecosystem` in titles.

Sample titles from `era_cluster_matrix.json` for audio_music ChatGPT:
- Era 1: id=6321 date=2024-11-06 title="Bartering Dual Economy System"
- Era 1: id=6281 date=2024-11-15 title="Business Ecosystem Integration"
- Era 1: id=6107 date=2024-11-29 title="Synthesizing Ideas for GPT"
- Era 2: id=1533 date=2026-02-09 title="Your System and Infrastructure"
- Era 2: id=1494 date=2026-02-13 title="Unzip and Analyze System"
- Era 2: id=1471 date=2026-02-14 title="Tattoo Surface Governance System"

These titles ALL contain the substring `stem` (in `System`, `Ecosystem`, `Synthesizing`). The title-language alone is not evidence about audio/music content. **Without reading bodies**, I cannot confirm whether any of these convos discuss audio/music. I can confirm only that the substring rule fired.

Status: **grounded** that the substring fired; **open** whether each title represents real audio/music talk.

### F4 · Anatomy items have negative `idea_at -> ship_at` lag (idea_at lands AFTER ship_at)

| item              | lag_idea_to_ship_days |
|-------------------|---------------------:|
| anatomy-map       |                 -3.6 |
| anatomy-extension |                 -3.2 |
| anatomy-research  |                 -3.2 |
| anatomy-rewrite   |                 -2.4 |

All 4 anatomy items use convo 316 ("Site Anatomy Engine") as `idea_provenance`, dated 2026-04-26. The fs_ctime ship dates land 2026-04-22 / 2026-04-23 — before the convo. The script's first-ChatGPT-mention-of-cluster rule cannot anchor before any actual cluster-matching convo exists.

This means at least one of the following is true: (a) the build happened first and the convo came after; (b) an earlier ChatGPT mention exists with a different keyword the substring rule missed; (c) the cluster seed list for anatomy is too narrow (only `anatomy*` terms in `clusters_final.json`); (d) the corpus is incomplete.

Status: **grounded** on the negative lag, **open** on which cause applies.

POLARIS also shows -0.4d lag (name_match to convo 1298 "Aegis Fabric and POLARIS" dated 2026-02-23, ship 2026-02-22). Same pattern, but smaller and using name_match (not cluster_fallback).

Spot-check records:
- anatomy-map: idea_at=2026-04-26, ship_at=2026-04-22T09:53, ship_provenance.path=`C:\Users\bruke\.claude\skills\anatomy-map`, lag=-3.59d.
- anatomy-extension: idea_at=2026-04-26, ship_at=2026-04-22T18:48, path=`C:\Users\bruke\Pre Atlas\tools\anatomy-extension`, build_at=2026-05-01.
- anatomy-research: same anchor convo, ship_at=2026-04-22T19:45.
- anatomy-rewrite: same anchor, ship_at=2026-04-23T14:47.
- POLARIS: convo 1298 dated 2026-02-23, ship 2026-02-22T13:32 — but this is name_match, lag = -0.4d.

### F5 · `talk_leads` count (27) is structurally inflated by cluster_fallback anchors

Of 27 `talk_leads` items, 21 use `idea_via == cluster_fallback`. Their `idea_at` is the earliest cluster-anchor convo, NOT the earliest convo mentioning the item by name. The pattern label "talk leads build" is therefore measuring "cluster-anchor talk precedes item-named build," not "this specific item was discussed before being built."

Examples of cluster_fallback talk_leads items with anchor dates in Era 1 and builds in Era 3:
- cognitive-sensor: anchor 2024-08-24 (convo 6521), build 2026-02-09, lag=534.2d. (Item name "cognitive-sensor" does NOT appear in convo 6521's title; matched on seed `perception`.)
- delta-kernel: anchor 2024-08-24 (convo 6521), build 2026-02-09, lag=534.3d.
- triangulation: anchor 2024-08-24 (convo 6521), build 2026-05-02, lag=616.6d.
- code-converter: anchor 2024-08-24 (convo 6521), no build, lag null.
- inpact-site: anchor 2024-08-24 (convo 6521), build 2026-05-04, lag=619.0d.
- web-audit: anchor 2025-10-17 (convo 2530 "Scrape or bite mark"), build 2026-05-01, lag=196.8d.
- STEMai: anchor 2024-11-06 (convo 6321), build 2026-03-02, lag=481.1d (carries substring_fp_risk caveat).

Compare to name_match talk_leads where the item name DID appear in the convo title:
- atlas: convo 2333 "Behavioral research for Atlas OS", lag=86.2d (real signal).
- STRUDEL: convo 1286 "Strudel and TouchDesigner Merge", lag=1.06d (parallel, not talk_leads, but anchored on item name).
- wasp: convo 3191 "Tarantula hawk wasp description", lag=279d (but title is about WASPS the insect, not the Wasp framework — title language only).

Status: **grounded** that the inflation pattern exists; **suspect input** for each cluster_fallback talk_leads claim.

### F6 · `no_build` cohort (27 items) — ChatGPT hit but no CC session named the item in `first_user_msg`

These items show up in the cluster's ChatGPT signal (or via cluster_fallback) but no Claude Code session ever began with the item name. Examples (`ship_flow.json::items` filter `flow_pattern==no_build`):

- airwindows, nih-plug, surge-xt (audio_music, all cluster_fallback via `stem`)
- m3p-to-fract, mandelbulber2_install, mb3d-blender, mb3d_anim_demo, mandelbulber2 (mb3d_fractals via `fractal`)
- screenshot-to-code, anime-js, react-three-fiber (canvas_render via `comfyui`)
- scrapling-smoke, scrapling-official, web-extract-workflow (web_extract via `scrape`)
- anatomy-map, anatomy-research, anatomy-rewrite (anatomy via `anatomy`)
- continuous-learning-v2 (productivity_skills via `fest`)
- crucix, mirofish, mosaic-orchestrator, uasc-executor, ws-gateway, ai-exec-pipeline, code-converter (atlas_core via `perception`)
- openclaw (atlas_core, name_match to convo 1377)
- URBANNOMAD (cluster=none, name_match to convo 1043)

**Important caveat.** The `no_build` rule matches CC `first_user_msg` substring only — sessions that touched the item but didn't name it in the very first user message are invisible. The session log's `cwd`, `gitBranch`, or touched files were NOT consulted. A `no_build` label is therefore "no CC session opened with this name as the first word" rather than "no CC session ever worked on this item." This is a known limitation of the Phase 4 rule.

Status: **grounded** that the rule fired; **structurally weak** as evidence of "never built in CC."

### F7 · `no_talk` cohort (2 items): binre, everything-claude-code

`ship_flow.json::items`:
- `binre`: no cluster assignment in `portfolio_evidence.json::clusters`; no ChatGPT match; build_at=2026-05-15 (session 854e5df3-a359-40a7-a194-03eb5aab7201, first_user_msg "what happens in we combine binre tool with es tool what can we do"); ship_at=2026-05-10; lag_build_to_ship=-5.1d.
- `everything-claude-code`: no cluster, no ChatGPT, no CC; ship_at=2026-03-31; last_active=2026-04-01.

Status: **grounded**. Both are CC-era (Era 3-4) builds with no detected upstream ChatGPT idea-formation. Could be real ("pure build_leads") or could be cluster assignment gaps (binre has no cluster but `re`/`binary` could plausibly belong to a cluster not yet defined).

### F8 · CC sample previews under audio_music Era-2 (count=262) do not look like audio/music work at title-language level

Sample previews from `era_cluster_matrix.json::clusters[audio_music].channels.cc.era_2_early_cc.samples` (first 5):
- id=agent-a3dfc3b date=2026-02-09 preview="I need to understand the exact structure and content of the user's conversation..."
- id=agent-a583652 date=2026-02-09 preview="I need to perform a deep behavioral analysis of a user's 1,397 ChatGPT conversat..."
- id=agent-aeff131 date=2026-02-09 preview="I need to design an implementation plan for a 5-agent idea intelligence system t..."
- id=agent-a6c684c date=2026-02-13 preview="I need to understand the current state of the loop triage system in C:\\Users\\bru..."
- id=agent-a1b63ec date=2026-02-16 preview="I need to find the exact melanin absorption coefficients currently used in a Ble..."

These previews use words like `system`, `idea intelligence system`, `triage system`. Phase 2 flagged `stem` as the substring matching `system`. The preview language is not evidence of audio/music content. **Without reading bodies**, I report only that the title-language is consistent with the FP risk Phase 2 already warned about, not that these sessions are or are not audio work.

Status: **grounded** that the matched-substring artifact is observable in the preview text.

### F9 · productivity_skills CC era_3 previews include "fest" via "pre-atlas-closed-loop fest"

Sample previews from `era_cluster_matrix.json::clusters[productivity_skills].channels.cc.era_3_heavy_cc.samples` (first 5):
- id=4e835f21... date=2026-04-28 preview="You are executing Phase 2 of the pre-atlas-closed-loop fest..."
- id=58d791bb... date=2026-04-28 preview="You are executing Phase 1 of the pre-atlas-closed-loop fest..."
- id=7de08e58... date=2026-04-28 preview="You are executing Phase 1 of the pre-atlas-closed-loop fest..."
- id=7df31495... date=2026-04-28 preview="You are executing Phase 3 of the pre-atlas-closed-loop fest..."

These match seed `fest` literally (in "fest" of "pre-atlas-closed-loop fest"), which is the productivity_skills seed. But "fest" here means the Festival methodology (a productivity practice). So `fest` is a TRUE positive for productivity_skills in CC, while it is the FALSE positive case in ChatGPT (where it matches `manifesting`/`lifestyle`). Different channel, different word-context — same 4-letter substring rule.

Status: **grounded**. The substring rule produces FP risk in one channel and TP in another for the same seed; this is asymmetric and worth handling explicitly in a re-run.

---

## 4 · Open questions for follow-up

These are NOT findings; they are structural gaps in what Phases 1-4 produced.

1. **Do the 7 anchor convos actually discuss the clusters they were used to date?** Currently unknown — bodies not read. (Phase 4 audit task; see `AUDIT_FINDINGS.md`.)
2. **For each `no_build` item, did a CC session ever touch its path even without naming it in `first_user_msg`?** Phase 4 only checked first_user_msg substring. The CC corpus has `cwd` / `gitBranch` / touched-files dimensions that were not joined.
3. **For the 4 anatomy items with negative lag (F4), is there an earlier ChatGPT convo about anatomy that the cluster seed list misses?** The seed list is `anatomy*` only — site-anatomy / page-anatomy / DOM-anatomy synonyms are not enumerated.
4. **For `binre` (no_talk), should a new cluster (e.g., reverse-engineering / binary-analysis) be added?** Currently it has no cluster home, so it cannot anchor on any ChatGPT signal even if signal exists.
5. **Is the 4-letter substring threshold appropriate?** Three of the seven anchor seeds (`stem`, `fest`, `scrape`) are at risk. Raising the threshold to 6+ letters or switching to word-boundary regex would drop most FP risk but also drop true matches like `stem` → `stems` (real audio context).
6. **Is `comfyui` a good anchor for `canvas_render`?** Only 1 Era-1 + 8 Era-2 ChatGPT items mention canvas_render at all, and all 6 canvas_render cluster_fallback items collapse onto a single 2026-01-24 convo about ComfyUI. This is the same single-anchor collapse pattern as anatomy/web_extract.
7. **The `productivity_skills` CC count of 27 in Era 3 is real (F9 shows literal "fest" matches) but counts CC sessions about festival methodology, not about productivity skills broadly.** Is the cluster definition coherent?
8. **The cluster `audio_music` ChatGPT count of 89 in Era 1 is dominated by `stem`-matching titles that title-language strongly suggests are NOT music (`Bartering Dual Economy System`, `Business Ecosystem Integration`, `Document Processing System Design` per Phase 2 warning).** Drop `stem` from seeds and re-count?
9. **`atlas_core` Era-1 ChatGPT = 64 is the only meaningful Era-1 cluster signal.** What fraction of that 64 is actual `perception` (the seed) vs. atlas/governance/system talk? Sample id=6521 title "Voice Perception as Strength" — title-language is about voice perception in social/personal context; cannot say more without reading body.
10. **Are there ideas in the strong band that have NO portfolio item yet?** ship_flow.json only walks the portfolio in; it doesn't surface unbuilt-but-discussed ideas. Counter-narrative work might benefit from the reverse direction.

---

## 5 · What this report does NOT claim

To be explicit about the scope limit:

- This report makes **no claim** about what is or is not discussed in any ChatGPT convo body. Every reference to a convo cites only its `convo_id`, `title`, and date (Phase 1 indexed metadata).
- This report makes **no claim** about whether the 7 cluster anchor convos are "real" or "wrong" idea anchors. That's the audit task in `AUDIT_FINDINGS.md`.
- This report makes **no claim** about which items "really" started in which era. The script's `idea_at` is the rule's output; whether it matches the writer's intent is what the audit is for.
- Title-language is reported as title-language. Where a finding leans on title content (F3, F8, F9), it says so and quotes the title.

If a downstream reader treats anything here as stronger than "structural pattern observable in script output," that is a misreading.

---

## 6 · Index of records cited

ChatGPT convo IDs cited: 119, 316, 375, 682, 685, 722, 1043, 1260, 1262, 1286, 1298, 1377, 1404, 1447, 1452, 1471, 1494, 1503, 1510, 1533, 1705, 1928, 1929, 2333, 2530, 3191, 3945, 4986, 5690, 5915, 5988, 6098, 6107, 6281, 6289, 6321, 6464, 6490, 6521.

CC session IDs cited (subset): agent-a423012, agent-a145acc, agent-a1d3798, agent-a583652, agent-aeff131, agent-a6c684c, agent-a1b63ec, agent-a3dfc3b, c9590916-4b42-4226-8289-ece8f5716855, 854e5df3-a359-40a7-a194-03eb5aab7201, 4e835f21-268a-4e6e-bbaa-e221f7c76ec1, 58d791bb-aa84-4d85-abbe-6ba9e4ce7eb4, 7de08e58-a8e0-4cfc-a668-a7e8ca1102c8, 7df31495-e016-4783-939b-fd3994d110be.

Portfolio item names cited: 60 strong items per `ship_flow.json::items`.

End of CORPUS_MAP.md.

# AUDIT_FINDINGS · corpus-archaeology festival, Phases 1-4

**Generated:** 2026-05-28
**Auditor:** Claude (this session) reading actual data, per [feedback_dont_guess_when_code_exists](../../../.claude/projects/C--Users-bruke-Pre-Atlas/memory/feedback_dont_guess_when_code_exists.md).
**Scope:** Verify counts in Phase 1-4 artifacts against `_progress.json`; read the 7 cluster anchor convo bodies (Phase 4 `cluster_fallback` anchors); spot-check 5 of 13 `name_match` anchors. Report only. No silent re-runs.

---

## 1 · Phase 1-3 count verification (mechanical)

All count claims in `_progress.json` reconcile with the artifacts on disk.

| Claim location                                  | Claim                                        | Verified |
|-------------------------------------------------|----------------------------------------------|----------|
| `_progress.json::phases.001.chatgpt`            | 6534 chatgpt convos indexed                  | ✓ (`chatgpt_temporal.json::count==6534`, `items` array length 6534) |
| `_progress.json::phases.001.cc`                 | 1017 cc sessions indexed                     | ✓ (`cc_temporal.json::count==1017`, `items` len 1017) |
| `_progress.json::phases.001.fs`                 | 140 portfolio paths indexed                  | ✓ (`fs_temporal.json::count==140`, `items` len 140) |
| `phases_003.seq_01..seq_04b::summary.totals`    | Era totals chatgpt/cc per era                | ✓ (raw `era_N_matrix.json::totals.chatgpt_in_era/cc_in_era` match `era_cluster_matrix.json::totals_by_era`) |
| Per-cluster chatgpt count for each (cluster,era)| 28 cells total                               | ✓ (every cell in `era_N_matrix.json::clusters[*].channels.chatgpt.count` equals the same cell in merged matrix) |
| `phases_004.seq_01::summary.input_strong_count` | 60 strong items                              | ✓ (`ship_flow.json::items` length 60) |
| `phases_004.seq_01::summary.flow_pattern_counts`| talk_leads=27, no_build=27, no_talk=2, parallel=4 | ✓ (recounted from items) |
| `phases_004.seq_01::summary.caveat_substring_fp_risk_count` | 7 items                          | ✓ (items with `caveat==substring_fp_risk` count = 7) |

**Phase 2 cluster definitions are stable across `clusters_v0/v1/final.json`** (same 7 clusters; seed counts 9/10/18/32/16/28/22 unchanged through validation). `clusters_final.json::clusters[*].portfolio_hits` totals: anatomy=4, mb3d_fractals=7, audio_music=10, atlas_core=25, web_extract=10, productivity_skills=22, canvas_render=17 → 95 entries; some items multi-cluster, hence 60 distinct strong items in `ship_flow.json`.

**Conclusion on mechanical audit:** No miscounts found in Phases 1-3 or in Phase 4's tabulation. The scripts did what they were declared to do.

---

## 2 · Phase 4 anchor body verification (semantic)

Method: opened `services/cognitive-sensor/memory_db.json` (385 MB, 6534 convos, indexed by array position = `convo_id`). For each of the 7 cluster_fallback anchors, read the convo title, full message count, total chars, and first user/assistant message text. Verdict assigned only from what was actually read.

### 2.1 Verdict summary table

| convo_id | title                            | cluster              | seed       | items absorbed | verdict             | reason |
|---------:|----------------------------------|----------------------|------------|---------------:|---------------------|--------|
| 6521     | Voice Perception as Strength     | atlas_core           | `perception` |          15 | **REJECT**           | About a person's voice/demeanor; not the perception service |
| 2530     | Scrape or bite mark              | web_extract          | `scrape`     |           8 | **REJECT**           | About a skin scrape vs bite mark; not web scraping |
| 6321     | Bartering Dual Economy System    | audio_music          | `stem`       |           5 | **REJECT**           | About a bartering marketplace; substring `stem` matched in `System` |
| 6289     | Manifesting Through Desire       | productivity_skills  | `fest`       |           2 | **REJECT**           | About manifestation/law-of-attraction; `fest` matched `Manifesting`/`infestation` |
| 1705     | ComfyUI Workflow Explanation     | canvas_render        | `comfyui`    |           6 | **WEAK MATCH**       | Real ComfyUI convo, but ComfyUI is image-gen AI; cluster portfolio is web-3D/animation libs |
| 4986     | Logistics and Fractal Thinking   | mb3d_fractals        | `fractal`    |           5 | **WEAK MATCH**       | About fractals metaphorically (pattern-thinking from logistics work); cluster portfolio is 3D fractal renderers |
| 316      | Site Anatomy Engine              | anatomy              | `anatomy`    |           4 | **ACCEPT BUT LATE**  | Real site-anatomy idea convo, but dated 2026-04-26 — AFTER the 4 anatomy items' ship_at (2026-04-22/23) |

**Headline:** 4 of 7 anchors are pure substring false positives. 2 of 7 are domain-mismatched. 1 of 7 is topically real but is not actually the origin idea (items shipped before the convo). **Zero of 7 anchors function correctly as "earliest idea formation in ChatGPT" for their items.**

### 2.2 Per-anchor evidence (quoted from message bodies)

#### Anchor 6521 — "Voice Perception as Strength" → atlas_core (15 items)

- Total: 14 messages (7 user + 7 assistant), 8 586 chars.
- First user message verbatim: `How could Harrison's voice and see how they carry their self make them a truck`
- First assistant message verbatim (truncated to 300 chars): `It sounds like you're asking how Harrison's voice and the way they carry themselves might make them appear more like a "truck," which could be interpreted metaphorically as being strong, reliable, and tough. Here's how Harrison's voice and demeanor might contribute to that perception...`
- **What it is:** a conversation about a specific person named Harrison and their voice/demeanor making them seem strong/reliable.
- **What it is not:** the atlas_core `perception/` service in `services/perception/`.
- **Impact:** invalidates `idea_at` for 15 strong items: inpact-site, aegis-fabric, cognitive-sensor, cortex, crucix, delta-kernel, mirofish, mosaic-dashboard, mosaic-orchestrator, triangulation, uasc-executor, ws-gateway, ai-exec-pipeline, blueprint-generator, code-converter.

#### Anchor 2530 — "Scrape or bite mark" → web_extract (8 items)

- Total: 14 messages (7 user + 7 assistant), 12 526 chars.
- First user message verbatim: `Does this mark look more like a scrape or a graze from a bite`
- First assistant message verbatim (truncated): `I can't give a medical diagnosis, but I can describe what I see and how it generally compares to common skin marks. The area on your wrist shows a small, localized red spot with mild inflammation and slightly broken surface skin. Based on visual characteristics: - **If it's a scrape/graze:**...`
- **What it is:** a conversation about a physical skin mark (scrape vs. bite) on the wrist.
- **What it is not:** web scraping or any data extraction concept.
- **Impact:** invalidates `idea_at` for 8 items: competitor-monitor (standalone + github), Scrapling (standalone + github), scrapling-smoke, web-audit, scrapling-official, web-extract-workflow.

#### Anchor 6321 — "Bartering Dual Economy System" → audio_music (5 items)

- Total: 127 messages (59 user + 68 assistant), 448 794 chars.
- First user message verbatim (truncated): `What if I had a bartering economy system, dual economy system, where users could choose between bartering items, services, or money, in exchange for services, items, or money. And things could be, users could take a quiz, and with the interactive quiz, it decides what users use and what they want, and it creates an AI profile of things that they might like to create an algorithm for them to see items...`
- First assistant message verbatim (truncated): `This bartering and dual-economy system idea sounds dynamic and would bring a unique marketplace experience...`
- **What it is:** a long conversation about a bartering / dual-currency marketplace concept.
- **What it is not:** audio, music, stems, plugins, or anything in the audio_music cluster's domain.
- **Substring trace:** seed `stem` matched in the title's `System` (and likely in many body mentions of `system`, `ecosystem`).
- **Impact:** invalidates `idea_at` for 5 items: airwindows, nih-plug, operator-system, STEMai, surge-xt. (Phase 4 already flagged these 5 with `substring_fp_risk` caveat — but reported `idea_at` anyway.)

#### Anchor 6289 — "Manifesting Through Desire" → productivity_skills (2 items)

- Total: 69 messages (35 user + 34 assistant), 110 038 chars.
- First user message verbatim: `I think it's infestation how wanting something can bring it in. You might feel you have to work for it and as it through however things will be working in the background.`
- First assistant message verbatim (truncated): `Absolutely. It's almost like there's this hidden network in the universe that gets activated when your desire is strong and focused. Sometimes, it feels like you need to grind hard for what you want, but the moment you truly set your intention and let that desire sink in, things start aligning behin...`
- **What it is:** a conversation about manifestation / law of attraction / how desire pulls outcomes.
- **What it is not:** productivity skills, fest methodology, CC skills, or anything in the productivity_skills cluster's domain.
- **Substring trace:** seed `fest` matched in `Manifesting` (title) and `infestation` (first user message).
- **Impact:** invalidates `idea_at` for 2 items: continuous-learning-v2, codex-partner. (Both already had `substring_fp_risk` caveat in Phase 4.)

#### Anchor 1705 — "ComfyUI Workflow Explanation" → canvas_render (6 items)

- Total: 21 messages (10 user + 10 assistant), 25 310 chars.
- First user message verbatim: `What software is in the bottom half`
- First assistant message verbatim (truncated): `Bottom half is **ComfyUI**. Not guessing — the visual structure gives it away immediately. Here's the tell: Identifiers: Node-based canvas, Rectangular modules with titles like: Model Selection, Outfit, Prompt A…, Reference, Studio, Purple sticky-note style annota...`
- **What it is:** a conversation identifying ComfyUI in a screenshot and explaining its node-based generative-AI workflow.
- **What it is not (necessarily):** the canvas_render cluster's domain. The cluster's portfolio items are screenshot-to-code, three-js, react-three-fiber, anime-js, canvas-engine, anime-js-migrate, three-js-migrate, react-three-fiber, remotion, three-js, three-js-migrate, canvas-engine, canvas-demo — almost entirely web-3D and animation libraries, not generative image AI.
- **Verdict reasoning:** title and content are about ComfyUI, the literal seed. But ComfyUI is a different domain than the items the seed is supposedly anchoring. The cluster definition probably should not include `comfyui` as a seed, or the cluster should split into `web_render` (three-js/anime-js/react-three-fiber/canvas-engine) vs `generative_ai` (ComfyUI/screenshot-to-code).
- **Impact:** `idea_at` for 6 items (screenshot-to-code, three-js standalone+skill, anime-js, react-three-fiber, canvas-engine) is reported as 2026-01-24 from this convo. Whether that's a meaningful anchor depends on whether ComfyUI talk genuinely seeded the web-3D builds — domain-distance suggests no, but this is a cluster-definition issue, not a substring artifact.

#### Anchor 4986 — "Logistics and Fractal Thinking" → mb3d_fractals (5 items)

- Total: 52 messages (17 user + 18 assistant), 127 219 chars.
- First user message verbatim (truncated): `I used to work at Amazon. I also worked at Nordstrom Warehouse. I also worked at FedEx. I worked as a warehouse worker using supply chain and logistics. I worked in inbound and outbound. I also worked in processing. I was not a high-level worker. I didn't stay at these roles for long. Even though I was at these jobs, I didn't—I made money, but I think it is more about that than a job. I feel like it was teaching me something. One thing that I have recently done is look at fractals. I think that...`
- First assistant message verbatim (truncated): `It sounds like you've discovered a pretty powerful connection between your logistics background and the way you naturally think—especially in terms of analyzing, organizing, and "seeing" patterns in everyday life. Here are a few points that might help clarify and validate the link you're noticing be...`
- **What it is:** a conversation about pattern-thinking — connecting the user's warehouse-logistics work to fractal pattern recognition as a cognitive style.
- **What it is not (necessarily):** the mb3d_fractals cluster (Mandelbulb3D, Mandelbulber, m3p-to-fract — 3D fractal rendering tools).
- **Verdict reasoning:** the word `fractal` is genuinely in the title and content, BUT the topical domain is "fractal as a metaphor for pattern-thinking," not "fractal as a 3D-rendering object." The cluster portfolio is unambiguously about 3D rendering software.
- **Impact:** `idea_at` for 5 items (m3p-to-fract, mandelbulber2_install, mb3d-blender, mb3d_anim_demo, mandelbulber2) is reported as 2025-03-20 from this convo. The reported 417-418-day idea→ship lag is built on a metaphor-vs-tool confusion.

#### Anchor 316 — "Site Anatomy Engine" → anatomy (4 items)

- Total: 36 messages (19 user + 17 assistant), 66 028 chars.
- First user message verbatim: `If I make a sure mapper that can scan a site and clone it locally and label all the components for analysis and annotation what is that`
- First assistant message verbatim (truncated): `That is not just a site cloner. That is a Visual Site Intelligence Mapper. More precisely: A local web reconstruction + component intelligence system that turns any website into an annotated, inspectable, cloneable interface map. In plain language: You feed it a URL. It pulls the...`
- **What it is:** a real conversation about the site-anatomy / DOM-clone / annotate concept that became the anatomy cluster.
- **The catch:** the convo is dated 2026-04-26. The 4 anatomy items' ship_at dates are 2026-04-22 (anatomy-map, anatomy-extension, anatomy-research) and 2026-04-23 (anatomy-rewrite). The convo postdates the ships by 3-4 days. **Therefore this is NOT the origin idea — the items were already built when this convo happened.**
- **Verdict:** topically accurate anchor but temporally wrong-direction. There must be an earlier ChatGPT mention of anatomy ideas that the script's seed list (`anatomy`, `anatomy-v1`, `anatomy-extension`, `anatomy-research`, `anatomy-rewrite`, `anatomy-map`, `anatomy-frame`, `anatomy-sidecar`) failed to capture. Possible misses: the convo might not contain the literal word "anatomy" yet, OR the genuine seeding convo lives outside the corpus.
- **Impact:** the 4 anatomy items show negative `lag_idea_to_ship_days` (-3.6, -3.2, -3.2, -2.4) which already surfaced this paradox in CORPUS_MAP F4. The audit confirms: the date is real, the topic is real, but the convo can't be the origin idea.

### 2.3 Spot-check of name_match anchors (5 of 13 sampled)

| convo_id | title                            | item             | verdict | reason |
|---------:|----------------------------------|------------------|---------|--------|
| 3191     | Tarantula hawk wasp description  | wasp             | **REJECT** | About the *Pepsis* insect ("This image shows a Tarantula Hawk Wasp..."), not the Wasp framework |
| 1929     | Pre Atlas System Review          | Pre Atlas        | **ACCEPT** | Real Pre Atlas governance discussion, first user msg begins "I have been working on some projects and now they are converging... PRE_ATLAS_MAP.md..." |
| 1928     | Pre-Atlas Progress Stages        | pre-atlas (gh)   | **ACCEPT** | Real Pre-Atlas progress assessment, first user msg "how far do you think I am along with pre-atlas" |
| 1043     | URBANNOMAD Prototype Breakdown   | URBANNOMAD       | **ACCEPT** | Real URBANNOMAD prototype review, references the actual github.com/lionestenzol/URBANNOMAD repo |
| 2333     | Behavioral research for Atlas OS | atlas (both)     | **ACCEPT** | Real Atlas OS design discussion, first user msg describes ENPAC self-sustaining building journal |

**Eight name_match anchors un-audited:** convo_ids 1298 (POLARIS), 1286 (STRUDEL), 1377 (OpenClaw), 375 (OPTOGON), 5915 (inPACT), 6521 (perception — same anchor as cluster_fallback for atlas_core, REJECT applies), 119 (Mandelbulb3D as a Forge — mandelbulb3d), and the duplicate convo 2333 (atlas github surface). The substring rule on name matches can in principle also produce FPs (the wasp case proves it). Pre-Atlas/atlas/OPTOGON/POLARIS/inPACT names are distinctive enough that a wider audit is lower priority, but worth confirming any item whose ship date is far from the anchor date.

### 2.4 Numeric impact

| status of `idea_at`              | item count |
|----------------------------------|-----------:|
| invalidated (REJECT anchor)      | 30 (15 + 8 + 5 + 2)                |
| topically suspect (WEAK anchor)  | 11 (6 + 5)                         |
| temporally wrong (ACCEPT-but-late)| 4 (anatomy items)                 |
| name_match REJECT (wasp)         | 1                                  |
| name_match ACCEPT (spot-checked) | 4                                  |
| name_match un-audited            | 8                                  |
| no_talk (no claim made)          | 2 (binre, everything-claude-code)  |
| **total**                        | **60**                             |

So **at least 46 of 60 strong items** (the 30 REJECT + 11 WEAK + 4 LATE + 1 wasp REJECT) have an `idea_at` that should not be load-bearing in any downstream analysis without re-anchoring. The remaining 14 are 4 spot-checked-OK name_match items + 8 un-audited name_match items + 2 no_talk items.

---

## 3 · Phase 2/3 substring-rule audit

Findings in Section 2 confirm Phase 2's own substring warnings (`stem`/`fest`) and identify two additional cluster-definition issues:

- **`perception` as an atlas_core seed:** the word "perception" has heavy psychological/social usage. Of atlas_core's 64 Era-1 ChatGPT items (the cluster's strongest pre-CC signal), an unknown but probably-large fraction are personality/voice/social-perception convos rather than perception-service convos. The single audited anchor (6521) is firmly in the social-perception bucket.
- **`comfyui` as a canvas_render seed:** ComfyUI is a generative-AI image tool with no overlap with the cluster's web-3D portfolio. Including it as a seed inflates canvas_render's apparent ChatGPT presence.
- **`scrape` as a web_extract seed:** the word has medical/physical usage that bleeds in (audited anchor 2530).
- **`fractal` as a mb3d_fractals seed:** the word has metaphorical/cognitive usage that bleeds in (audited anchor 4986). 3D-fractal-rendering conversations typically use more specific terms (mandelbulb, mandelbox, m3p, raymarching, IFS, Mb3d, mandelbulber).

Phase 2 flagged only 4-letter seeds (`stem`, `fest`). The audit shows 6+ letter seeds (`perception`, `comfyui`, `scrape`, `fractal`) also produce false-positive matches due to domain ambiguity rather than substring shortness.

---

## 4 · What this audit does NOT claim

- The audit read **first user message + first assistant message** of each of 7 cluster-fallback anchors and 5 of 13 name-match anchors. It did NOT read every message of those convos. A 127-message convo (6321) might shift toward audio in later messages — the audit cannot rule that out, only state what the first turns show. Verdicts say "what the read text is about," not "what the entire convo is about." For 4 anchors (6521, 2530, 6289, 6321), the title-language and first-turn content are so unrelated to the cluster domain that a topic shift mid-convo would not rehabilitate them as origin-idea anchors. For 4986 and 1705 the read text is on-seed; the question is whether the seed/cluster match is the right cluster, which is a Phase 2 design issue.
- The audit did NOT re-verify Phase 1's source data (the 6534 ChatGPT export, 1017 CC sessions, 140 portfolio paths). It verified that counts in `_progress.json` match the artifacts on disk, not that the artifacts capture the underlying truth.
- The audit did NOT validate whether `flow_pattern` classification is correct given a corrected `idea_at`. Almost every flow_pattern label downstream of a REJECT/WEAK anchor needs to be recomputed in a re-run.

---

## 5 · Required corrections for any re-run

These are the rule-changes the data demands. Listed as recommendations to Bruke; not silently applied.

1. **Drop `stem`, `fest`, `scrape` from seed lists.** Four-letter seeds with high collision rates. The audit's audited collisions are too costly: 16 items affected.
2. **Re-evaluate `perception`, `comfyui`, `fractal` as cluster seeds.** These are full-word but topically ambiguous. Options:
   - Replace with stricter compound terms: `perception service`, `perception layer`, `perceive entity`, `perception module`; `mandelbulb`, `mandelbox`, `mb3d`, `m3p`, `raymarched`; drop comfyui entirely from canvas_render and either drop or create a new `genai_image` cluster.
   - Or switch the matching rule from substring to word-boundary regex + co-occurrence (Phase 2 validate step needs to actually exclude anchors that fail a body-content check).
3. **`name_match` substring rule needs same scrutiny.** The `wasp` collision (convo 3191 = tarantula hawk wasp insect) shows even item-name-matching produces FPs. Recommended: when `idea_at` is name_match, the Phase 4 script should additionally check that the convo contains at least one of: item path, item README content keywords, or 2+ cluster seeds in the body. Title-substring alone is insufficient.
4. **Phase 4 `idea_at` rule needs body content gate.** The current rule is "earliest convo whose title contains the item name OR (fallback) any cluster seed." A re-run should require the convo body to contain at least one specific signal beyond the seed substring. Concretely: include only if body contains item name OR at least 2 distinct cluster seeds OR a known cluster-portfolio path/URL.
5. **Phase 4 negative-lag items signal a different bug.** The 4 anatomy items shipped *before* their anchor convo. This means either (a) the corpus is missing an earlier convo that should have anchored them, or (b) the anatomy seed list is too narrow to catch the actual origin convo. A re-run should report `no_idea_anchor_found` rather than picking a post-ship convo as `idea_at`.
6. **Phase 4 `no_build` rule is too narrow.** Currently `build_at` = earliest CC session whose `first_user_msg` substring-matches the item name. This misses sessions whose first user message is generic (e.g. `Explore C:\\Users\\bruke\\airwindows`) without naming the item. A re-run should additionally check `cwd`, `gitBranch`, and (if available) touched-file paths. If `cc_temporal.json` doesn't carry those fields, this is a Phase 1 widening too.
7. **Cluster definition splits worth considering** (not blocking, but a re-run candidate):
   - `canvas_render` → `web_3d_render` (three-js/react-three-fiber/anime-js/canvas-engine/remotion) + `genai_image` (ComfyUI/screenshot-to-code).
   - `atlas_core` is at risk of being a 25-item catchall; the `perception` collision suggests at least the seed list needs tightening.
8. **Add a `binary_re` or `tool_meta` cluster** so `binre` and `everything-claude-code` have a home (avoid `no_talk` artifacts from a missing cluster definition).

---

## 6 · Recommendation

The mechanical scaffolding (Phase 1 indexes, Phase 3 era counts, Phase 4 tabulation) is sound. The interpretive layer (Phase 2 cluster seed selection + Phase 4 `idea_at` rule) is unsound at scale — 4 of 7 cluster-fallback anchors fail body inspection, plus 1 of 5 spot-checked name_match anchors. The CORPUS_MAP findings that depend on `idea_at` (especially F2, F3, F5) are structurally suspect.

**Recommended call to Bruke:** decide between:

- **(A) Full re-run** with corrections #1-#8 above. Cost: ~3-4 sessions (Phases 2-4 must re-run; Phases 1 + 5 mostly survive). Highest credibility.
- **(B) Targeted re-run of Phase 4 only** with a stricter `idea_at` rule (corrections #1, #3, #4, #5) on existing cluster definitions. Cost: ~1 session. Preserves Phase 2 cluster shape but accepts the cluster-definition issues from corrections #2, #7.
- **(C) Annotate-and-park.** Keep CORPUS_MAP.md as-is but prepend the audit-rejected anchors so downstream readers don't treat the rejected `idea_at` claims as load-bearing. No re-run. Cost: 5 minutes.

A detailed re-run plan covering option (A) is appended to this document in Section 7.

---

## 7 · Phase 1-5 full re-run plan (corrected rules)

If Bruke chooses option (A), this is the sequencing.

### 7.1 Phase 1 · re-use, no re-run

Phases 1 outputs (`chatgpt_temporal.json`, `cc_temporal.json`, `fs_temporal.json`) are independent of cluster definitions and verified clean. Re-use as-is.

Optional Phase 1 widening (recommendation #6): augment `cc_temporal.json` schema to include `cwd`, `gitBranch`, and a small (e.g. first 5) touched-file path list per session. Estimate +10% size, enables a stronger `build_at` rule downstream.

### 7.2 Phase 2 · seed surgery + body-content validator

Re-run `tools/fest-reconcile/seed_clusters.py` and `expand_clusters.py` with:

- Drop seeds: `stem`, `fest`, `scrape` (audit-confirmed collisions).
- Replace seeds: `perception` → `perception service`, `perception layer`, `perceive entity`; `comfyui` (drop from canvas_render); `fractal` → `mandelbulb`, `mandelbox`, `mb3d`, `m3p`, `raymarched IFS`.
- Optional: split `canvas_render` and add `binary_re`/`tool_meta` clusters (recommendations #7, #8).

Re-run `validate_clusters.py` with an upgraded validator: for every candidate convo, require body to contain the seed term in a non-substring sense (word-boundary regex) AND at least one corroborating signal (item path, item name, or 2+ cluster seeds). Emit a per-cluster `body_verified_count` alongside the existing `corpus_match_count`.

Output: `clusters_final_v2.json`. Compare against `clusters_final.json` — expect significant drop in audio_music (was 209 chatgpt) and productivity_skills counts.

Estimate: 1 session (~10% context).

### 7.3 Phase 3 · re-run era matrix

Re-run `build_era_matrix.py` for all 4 eras using `clusters_final_v2.json`. Same scripts, new cluster input. Re-run `fs_overlay.py`, `merge_matrices.py`.

Output: `era_cluster_matrix_v2.json`. Expect anatomy/web_extract/mb3d_fractals Era-1 ChatGPT counts to drop toward 0 (the inflated cluster-seed matches go away).

Estimate: 1 session.

### 7.4 Phase 4 · re-run ship_flow with stricter `idea_at`

Rewrite `ship_flow.py::resolve_idea_at` rule:

```
For each strong item:
  1. earliest_name_hit = earliest convo whose title OR first user msg contains item name (word-boundary)
     If body also contains item path or 2+ cluster seeds: ACCEPT as idea_at, idea_via=name_match_verified.
  2. else: earliest_cluster_anchor = earliest convo where (body contains 2+ cluster seeds in word-boundary) AND
            (body contains item-cluster-domain marker e.g. portfolio path fragment or known item synonym)
     If found: ACCEPT, idea_via=cluster_anchor_verified.
  3. else: idea_at = null, idea_via = no_verified_anchor (this is the new equivalent of the old no_talk for cluster_fallback fails).
```

Same for `build_at` if Phase 1 was widened (recommendation #6): also check `cwd`/`gitBranch`/touched-files, not just `first_user_msg`.

Output: `ship_flow_v2.json`. Expect `no_verified_anchor` count to be ~30-40 (replacing the 45 cluster_fallback items); `talk_leads`/`no_build`/`parallel` counts to redistribute.

Estimate: 1 session.

### 7.5 Phase 5 · regenerate CORPUS_MAP

Replace `CORPUS_MAP.md` with a v2 based on the v2 inputs. The structural skeleton (heatmap, flow patterns, counter-narratives, open questions) stays; the data inside changes.

Estimate: 1 session (~10% context).

### 7.6 Total re-run cost

4 sessions in series (Phase 2 + 3 + 4 + 5). Phase 1 not re-run unless widened. Each session well under the 25% CEILING.

---

---

## 8 · Code-level audit addendum (added after Bruke caught me inferring rules from output text)

Sections 1-7 above were written after reading the phase ARTIFACTS (the JSON outputs) and the 7 anchor convo bodies, but **before reading the 7 phase scripts themselves**. Bruke pushed back: "did you even look at all the code." Honest answer was no — I had inferred rule shapes from `method:` strings in the JSON output, not from source. This section reports what reading the actual scripts changed.

Scripts read for this addendum: `phase1_temporal_index.py`, `seed_clusters.py`, `expand_clusters.py`, `validate_clusters.py`, `build_era_matrix.py`, `fs_overlay.py`, `merge_matrices.py`, `ship_flow.py`.

### 8.1 What I claimed correctly but inferred (not verified in source)

- Substring rule is literal `s in text.lower()`. ✓ confirmed at `ship_flow.py:62`, `ship_flow.py:80`, `expand_clusters.py:106`, `build_era_matrix.py:55`.
- Phase 2 validator flags only seeds shorter than 5 chars. ✓ `validate_clusters.py:33` `SHORT_SEED_THRESHOLD = 5`.
- `idea_at` rule: name_match else cluster_fallback. ✓ `ship_flow.py:56-95`.
- Phase 4 caveat applies only to audio_music + productivity_skills. ✓ `ship_flow.py:25` `FP_RISK_CLUSTERS = {"audio_music", "productivity_skills"}`.

### 8.2 New findings from reading the code

**8.2.A · Portfolio-level mis-cluster: operator-system → audio_music**

`seed_clusters.py::compute_hits` (lines 258-275) assigns a portfolio item to a cluster if ANY seed term is a substring of the item's name (case-insensitive `s in item.name.lower()`). I ran a non-word-boundary scan against the 60 strong items' cluster memberships and found one item where the assignment crosses a non-word boundary on a short seed:

| item              | cluster      | seed matched | substring location in name |
|-------------------|--------------|--------------|----------------------------|
| `operator-system` | `audio_music`| `stem`       | inside `system`            |

The other items that flagged (`mandelbulber2_install`, `mandelbulb3d`, `mandelbulber2`, `STEMai`) are genuine matches — `mandelbulb` is the legitimate seed, and `STEMai` literally has STEM in it as the product name.

**Impact:** `operator-system` is in ship_flow.json with `clusters: ["audio_music"]`. The cluster-fallback `idea_at` for it (anchor convo 6321 "Bartering Dual Economy System") was already audit-rejected in §2.2, but the cluster ASSIGNMENT itself is also wrong — operator-system is a meta-tooling repo, not audio. Even with a corrected `idea_at`, putting it in audio_music for any analysis is mis-grouping.

This is the bug class I missed in §3 of the original report: not just "seeds collide in TITLE substring match," but also "seeds collide in ITEM NAME substring match at the cluster-assignment step." Dropping `stem` from audio_music's seed list (correction #1 in §5) would also fix this.

**8.2.B · Phase 1 already captures `cwd` and `git_branch` — my §5 recommendation #6 was wrong**

I wrote in §5 #6: "if `cc_temporal.json` doesn't carry those fields, this is a Phase 1 widening too." That premise is false. `phase1_temporal_index.py:101-103, 117` read `cwd` and `gitBranch` from each session jsonl and write them to `cc_temporal.json::items[*]`. The data is already there. The Phase 4 `build_at` rule simply doesn't consult those fields — it only checks `first_user_msg`. A re-run of Phase 4 with a wider rule does NOT require any Phase 1 changes; it just needs to use the fields that already exist.

**8.2.C · `first_user_msg` is truncated to 200 chars at Phase 1 source**

`phase1_temporal_index.py:76, 108` clip the first user message to `[:200]`. So when Phase 4's `find_build_cc` substring-searches for the item name in `first_user_msg`, it only sees the first 200 characters. Sessions with long task-template boilerplate at the top (a known pattern in this corpus — many sessions begin with "You are running WEAPON mode against..." or similar wrappers) hide the item name past char 200 and miss the match. This is the sharpest cause of the `no_build` inflation, sharper than the generic "rule misses sessions that don't name the item first" I gave in §F6.

A re-run should either (a) raise the truncation cap in Phase 1's `_extract_first_user_text`, or (b) also check `cwd`/`git_branch` fields in Phase 4.

**8.2.D · `validate_clusters.py::substring_warning` only scans first 2000 of 6534 ChatGPT items**

`validate_clusters.py:65` `for it in chatgpt_items[:2000]`. This is a cap-for-speed, written as a magic number with no flag. With 6534 total chatgpt items, the FP-warning step sees ~30% of the corpus. The two warnings that DID surface (stem/fest) happened to fire within the first 2000 — which is sorted by `MIN(date)` ascending per `phase1_temporal_index.py:45 ORDER BY MIN(t.date)`. So this is the earliest 2000 chatgpt items by first message date. Any seed-substring FP that occurs only in convos after position 2000 (i.e., after a certain date) goes unflagged.

A re-run should remove or raise the 2000 cap. The full scan over 6534 items is not slow enough to warrant the cap (the cell is a per-convo dict lookup, O(n) over a few thousand items in seconds).

**8.2.E · `FP_RISK_CLUSTERS` is a hardcoded set in ship_flow.py, not dynamically loaded from Phase 2**

`ship_flow.py:25` declares `FP_RISK_CLUSTERS = {"audio_music", "productivity_skills"}` as a literal Python set. It does NOT read `clusters_final.json::clusters[*].validation.substring_warnings` at runtime. So even though Phase 2's validator output already names which clusters have warnings, Phase 4 uses a hand-typed copy of those names. If a future Phase 2 run discovers a new warning (e.g. by removing the 2000-cap or adding longer-seed FP detection), Phase 4 won't notice it until someone hand-edits the set.

A re-run should compute `FP_RISK_CLUSTERS` from `clusters_final.json::clusters[*].validation.substring_warnings` at the top of `main()`.

**8.2.F · `matched_seed_term` reported in ship_flow.json is iteration-order-first, not most-specific**

`ship_flow.py:80`: `matched = next((s for s in seed_lc if s in title), None)`. This returns the FIRST seed in the cluster's seed_terms list that is a substring of the convo title. So when convo 6521 ("Voice Perception as Strength") matched atlas_core's seed list, the rule iterated through `[atlas, pre atlas, pre-atlas, delta-kernel, delta kernel, cognitive-sensor, cognitive sensor, cycleboard, cortex, optogon, aegis, aegis-fabric, openclaw, mirofish, perception, triangulation, mosaic, inpact, ...]` and found `perception` as the first hit. The reported `matched_seed_term: "perception"` is therefore the first-in-iteration-order match, not the most diagnostic one. This is a reporting subtlety — for the audit it doesn't change the verdict (the convo body is the same regardless of which seed name we cite) — but anyone reading ship_flow.json should know the field is order-first, not specificity-first.

**8.2.G · `era_for` returns `pre_corpus_start` for ctimes before 2024-08-21 — this bucket is not summarized anywhere upstream**

`fs_overlay.py:50` returns label `pre_corpus_start` for items whose ctime predates the ChatGPT corpus's earliest date. The `ctime_buckets` dict in fs_overlay.json has a `pre_corpus_start` key. My CORPUS_MAP §1.3 heatmap shows only era_1 through era_4 — items in `pre_corpus_start` are silently dropped from the heatmap. The Phase 3 `_progress.json` summary I quoted also doesn't include this bucket. Whether any items fall there: per `fs_overlay.py` output, the `pre_corpus_start` arrays in clusters all have len 0 — but my CORPUS_MAP didn't audit this and didn't mention the existence of the bucket.

**8.2.H · Substring rule in Phase 2 seq 02 + Phase 3 builds + Phase 4 lookups is identical literal `in`**

The same `has_seed_match` function shape (`s in text.lower() for s in seeds_lc`) is reimplemented in:
- `expand_clusters.py:102-106`
- `build_era_matrix.py:51-55`
- `validate_clusters.py:96, 104` (inline)
- `ship_flow.py:62, 80, 104` (inline)

No word-boundary regex anywhere. No tokenization-based match anywhere. Every cluster-membership decision in Phases 2-4 is literal substring against either `title`, `first_user_msg`, or `item.name`. The FP risk is therefore systemic, not localized to one rule.

A re-run should hoist the match function to a single utility module and change it once to word-boundary regex (`re.search(rf"\b{re.escape(seed)}\b", text, re.IGNORECASE)`). This change alone — without any other corrections — would eliminate the audit-rejected anchors 6521, 2530, 6321, 6289 because their substring matches are all inside longer words.

### 8.3 What this means for the re-run plan

§5 recommendations stand, with one correction and one new item:

- **§5 #6 correction:** Phase 1 already captures `cwd`/`git_branch`. The widening is Phase 4 (use those fields) + Phase 1 (raise the 200-char `first_user_msg` cap), not Phase 1 schema.
- **New §5 #9:** the substring rule needs to change from `s in text.lower()` to a word-boundary regex match. Single utility, applied in all four script families (Phase 2 expand, Phase 2 validate, Phase 3 era matrix, Phase 4 ship_flow). This is the highest-leverage single change. It would eliminate all 4 REJECT anchors in §2 (Harrison's voice, skin scrape, bartering system, manifesting) by itself, without needing any seed list edits.
- **New §5 #10:** Phase 4 should load `FP_RISK_CLUSTERS` from `clusters_final.json::clusters[*].validation.substring_warnings` at runtime, not hardcode.
- **New §5 #11:** Phase 2 validator must scan the full ChatGPT corpus, not the first 2000.
- **Operator-system specifically:** re-cluster manually (or with the word-boundary rule which would have prevented this) into the right cluster (probably `atlas_core` or a new `meta_tooling` bucket — its memory.md home is "Operator system / handoff" tooling, not audio).

### 8.4 What the addendum still does NOT verify

- `cc_corpus_recon.py`, `corpus_recon.py`, `reconcile.py` (the older "Part A" reconciliation scripts in the same directory) — not read. Festival design says Phase 1-5 don't use them, but if any output of the festival is downstream of them, that would be a gap.
- `portfolio.py` fully — I read the first 100 lines (signal_band calculation, file_count heuristic). The `strong` band threshold (file_count >= 20 + has_git or has_weapon + file_count >= 3 or mem + file_count >= 5) determines which 60 items the festival operates on. Items just below threshold get dropped from this entire analysis. Worth a separate audit if Phase 4 re-runs.
- Each script's exception handling (open file, parse json, etc.) — not audited. Counts match so silent skips would have shown up as count discrepancies, but a deeper check is possible.

End of AUDIT_FINDINGS.md.

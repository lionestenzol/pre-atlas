# Next session handoff: corpus mining + CC session index

---

## 2026-05-28 LATE EVENING · DONE · Tier 3 + Tier 4 drained; strangler 11/15

**Status:** banner-op sweep landed clean. 6 docs touched, 2 commits, no
cite runs. Strangler now at 11/15 — only Tier 1 #2-#5 (REGEN, doctrinal
prose with human-in-the-loop cite gating) remains.

**Pickup state — `C:\Users\bruke\OneDrive\Desktop\claude-mining`:**

```
git log --oneline                # 4 commits on master
ls v2/*.contaminated             # 9 renamed predecessors w/ banners
ls v2-clean/                     # 6 cited docs + STRANGLE_ORDER + _NEXT_SESSION
```

Commit lineage:

```
41039dc  Tier 4 sweep · manifest_combined + chatgpt_artifact_inventory
         + chatgpt_shape_notes banner-stripped, NOTE banner added
1f29752  Tier 3 sweep · 3 glossary_v2 addendums renamed .contaminated
         + SUPERSEDED banner forward-linking to v2-clean/glossary_v2.md
5fa8760  Tier 2 sweep · 4 REGEN-AUTO docs (thread5/timeline/personal/p5)
fe79248  init: corpus archaeology pipeline + Tier 1 #1 (concept_only)
```

**What shipped this session (Tier 3 — 3 DEPRECATE + Tier 4 — 3 KEEP):**

| # | Doc | Action | Forward link |
|---|---|---|---|
| 10 | `v2/glossary_v2_addendum.md` | `.contaminated` + SUPERSEDED banner | `v2-clean/glossary_v2.md` |
| 11 | `v2/glossary_v2_addendum_2.md` | `.contaminated` + SUPERSEDED banner | `v2-clean/glossary_v2.md` |
| 12 | `v2/glossary_v2_addendum_3.md` | `.contaminated` + SUPERSEDED banner | `v2-clean/glossary_v2.md` + `v2-clean/concept_only_resolution.md` (addendum 3's WOODLINE / VVAVE / Parallax verdicts are superseded by Tier 1 #1's cite-backed regen) |
| 13 | `v2/manifest_combined.md` | CONTAMINATED → NOTE; counts kept verbatim | n/a (mechanical, no replacement) |
| 14 | `v2/chatgpt_artifact_inventory.md` | CONTAMINATED → NOTE; os.walk inventory kept verbatim | n/a (mechanical, no replacement) |
| 15 | `v2/chatgpt_shape_notes.md` | CONTAMINATED → NOTE; JSON shape probe kept verbatim | n/a (mechanical, no replacement) |

STRANGLE_ORDER.md annotated DONE inline for #10-#15 matching the pattern from #1 and #6-#9.

**What's left (4 docs, all Tier 1 REGEN):**

- **#2 `doctrine_v2.md`** (+ `_addendum.md` merged) — 17 principles + 5 addendum entries; each ≥3 cites or flagged "untestable / candidate for cut." Hand-written interpretive prose above each cite block. **Next up; needs Bruke in the loop on cut/keep adjudications.**
- **#3 `understanding_brief_parallax.md`** — 4-layer vocab (law-shape / metaphor / technical / spec-doc) re-derived from chunk cites + raw `parallax_*_human.txt` as ground truth.
- **#4 `pattern_report_v1.md`** — 5 hypotheses (P1-P5) each with confirming + refuting cites; verdict SUPPORTED / WEAK / FALSIFIED.
- **#5 `stack_map_v1.md`** — service-graph edges cite-backed or marked structural-only; MEMORY.md port map as factual spine.

**Recommendation for next pickup:** start Tier 1 #2 (`doctrine_v2`) with Bruke explicitly in the loop on the per-principle cut/keep calls. Use `scripts/cite.py` against `v2/index/chunks-minilm`; emit via `scripts/regen_doc.py` + a new `scripts/templates/doctrine_template.yaml` modeled on `glossary_template.yaml`. Predecessor-rename pattern: copy from `v2/concept_only_resolution.md.contaminated`. After each principle block: propose verdict → show cites → wait for Bruke's call → move to next.

**Cross-ref carry (unchanged):** WOODLINE = INSUFFICIENT-EVIDENCE, VVAVE = CONCEPT-ONLY, Parallax = CONCEPT-ONLY (from Tier 1 #1). These verdicts feed into the doctrine_v2 regen — any principle that depends on WOODLINE shipping is itself untestable.

---

## 2026-05-28 EVENING · DONE · Tier 1 #1 + Tier 2 sweep shipped; claude-mining now versioned

**Status:** the strangler mission described below was partially executed and is now 5/15 docs into the v2 brownfield queue. The `claude-mining/` directory is now a git repo (was unversioned). Tier 1 #1 (concept_only_resolution) shipped end of last session; Tier 2 (#6/#7/#8/#9) shipped this session.

**Pickup state — `C:\Users\bruke\OneDrive\Desktop\claude-mining`:**

```
git log --oneline                # 2 commits: init + Tier 2 sweep
ls v2-clean/                     # 6 cited docs + STRANGLE_ORDER.md + _NEXT_SESSION.md
ls v2/*.contaminated             # 6 renamed predecessors w/ forward banners
```

**What shipped this session (Tier 2 — 4 REGEN-AUTO docs):**

| # | Doc | Terms | Cites | Highlight |
|---|---|---:|---:|---|
| 6 | `v2-clean/thread5_project_audit.md` | 13 | 78 | Mechanical 13-project table preserved; per-project mini-briefs surface kudzu, inPACT-journal, pixelnary, strudel-grammar |
| 7 | `v2-clean/timeline_v1.md` | 16 | 76 | Optogon naming captured Bruke's actual founding utterance `[b678006e:24]` + Claude's architectural lock `[b678006e:39]` |
| 8 | `v2-clean/personal_index.md` | 8 | 54 | FAMILY marker surfaces both substantive cites AND lexical noise — calibration signal flagged for next pass |
| 9 | `v2-clean/p5_parallax_cluster.md` | 8 | 37 | Alignment-not-transmission principle anchors on `[69f4b524:246]`; cross-cite converges on `[988ccfaf:65]` meta-pattern |

Validation: 8/8 random byte-match via `cite.py --verify` (2 per doc). STRANGLE_ORDER.md annotated DONE inline for #1, #6, #7, #8, #9.

**What's left:**

- **Tier 1 #2-#5** (REGEN, doctrinal prose — human-in-the-loop): `doctrine_v2.md`, `understanding_brief_parallax.md`, `pattern_report_v1.md`, `stack_map_v1.md`. Each needs hand-written interpretive prose with cites as receipts (not template+emit). Run with attention to the "candidate for cut" judgments — principles without cites should be flagged untestable.
- **Tier 3 #10-#12** (DEPRECATE): glossary_v2 addendums 1/2/3 — rename `.contaminated` + banner-link to the regenerated `v2-clean/glossary_v2.md`. Near-zero cost.
- **Tier 4 #13-#15** (KEEP, banner-strip): `manifest_combined.md`, `chatgpt_artifact_inventory.md`, `chatgpt_shape_notes.md` — strip contamination banner, add elide note for any interpretive sub-sections. Near-zero cost.

**Recommendation for next pickup:** drain Tier 3 + Tier 4 in one short session (8 banner ops total, no regen), then attempt Tier 1 #2 with explicit Bruke involvement for the doctrinal cut/keep calls.

**Cross-ref carry:** WOODLINE = INSUFFICIENT-EVIDENCE, VVAVE = CONCEPT-ONLY, Parallax = CONCEPT-ONLY (from Tier 1 #1) — feeds into the timeline ships table and the glossary entry rewrites.

---

## 2026-05-28 LATE PM · STALE-IN-PART · /weapon mission pre-staged for v2 brownfield

**Status:** session hit CEILING (~26%) right after producing the full v2 remediation spec. Weapon mission staged but NOT executed. Fresh session can fire it cold.

**Fire it in one line:**

```
/weapon C:\Users\bruke\OneDrive\Desktop\claude-mining
```

Or for a manual resume, point /weapon at the pre-staged files:

```
.weapon/spec.md  ← WEAPON_SPEC (already filled)
.weapon/plan.md  ← EXECUTION_PLAN (6 tasks, 3.5 hrs)
```

**What this mission does (one line):** replace contaminated v2/*.md interpretive docs with semantic-cited regenerations, using FAISS-over-chunks as ground truth + an anticorruption layer for provenance. Proof-of-loop = `v2-clean/glossary_v2.md`.

**Tasks (from .weapon/plan.md):**

1. `chunk_corpus.py` → `chunks.jsonl` (chunk message bodies, not titles)
2. `build_faiss_chunks` → `v2/index/chunks-{minilm,mpnet}/`
3. `cite_acl` → `cite.py` (extend verify_quote.py into provenance wrapper)
4. `regen_doc.py` → template-driven cited-markdown emitter
5. `regen_glossary` → `v2-clean/glossary_v2.md` (first proof)
6. `strangle_order` → `v2-clean/STRANGLE_ORDER.md` (the remaining 15)

**Why this matters:** [ATLAS_LAWS.md](services/cognitive-sensor/ATLAS_LAWS.md) Law #1 (TGT) was codified this session. v2 fails the GRAPH layer (no provenance to source convs). This mission is the first real application of the law — fix the broken graph layer before any more makeup goes on top.

**Cut list (enforce, don't expand):**
- DO NOT regen all 16 docs; glossary is the only required regen, strangle order documents the rest
- DO NOT delete contaminated docs (banner-flag only, predecessors banner already exists)
- DO NOT touch raw `*_human.txt` / `*_claude.txt` dumps
- DO NOT add new embedding models

**Companion docs:**
- [`services/cognitive-sensor/ATLAS_LAWS.md`](services/cognitive-sensor/ATLAS_LAWS.md) — Law #1 (TGT) the mission applies
- [`.weapon/spec.md`](.weapon/spec.md) — full WEAPON_SPEC
- [`.weapon/plan.md`](.weapon/plan.md) — full EXECUTION_PLAN

---

## 2026-05-28 PM · COMPLETED · click-to-full-conv verified + window-manager shipped

Click-to-full-conv verified in browser (Bruke hit a `file://` → CORS issue first; fixed by detecting protocol + falling back to `http://localhost:8765` absolute URL).

Plus shipped during this session:
- All `.panel` / `.inspector` divs → `resize: both` + drag-from-title window manager
- `atlas-box` → `min-height: 600px`, `resize: both` (map breathes)
- `html, body` → `overflow-y: auto` (universal scroll)
- Atlas Law #1 (TGT) codified in repo + memory
- `/tgt` slash command at `~/.claude/commands/tgt.md`

Files touched:
- `services/cognitive-sensor/atlas_template.html` + `cognitive_atlas.html`
- `services/cognitive-sensor/ATLAS_LAWS.md` (new)
- `~/.claude/projects/.../memory/feedback_tgt_law.md` (new) + `MEMORY.md`
- `~/.claude/commands/tgt.md` (new)
- `.claude/launch.json` (added `triage-server` config)
- `.weapon/spec.md` + `.weapon/plan.md` (pre-staged for next session)

---

## 2026-05-28 PM · OPEN FIRST · click-to-full-conv shipped, needs browser test

**Status:** the actual gap Bruke flagged ("cognitive sensor only mentions a conv, can't open it") was wired up but not verified in a browser. Code is in three files. Server must run for fetch to work.

**Verify in 60 seconds:**

```
cd "C:\Users\bruke\Pre Atlas\services\cognitive-sensor"
python triage_server.py

# in browser:
http://localhost:8765/cognitive_atlas.html
# click any point on the UMAP scatter ·
# right sidebar should show full conversation with role-colored messages
```

**Files touched (smoke-tested, not browser-tested):**

| file | change |
|---|---|
| `services/cognitive-sensor/triage_server.py` | `+do_GET /api/conv/<id>` · lazy memory_db loader · cached |
| `services/cognitive-sensor/atlas_template.html` | conv-panel in sidebar · click handler · render fn · O(n) coord lookup |
| `services/cognitive-sensor/cognitive_atlas.html` | same JS+HTML applied to rendered file (so no rebuild needed) |

**If verification fails (likely causes):**

```
   ✗ port 8765 already in use            → check with netstat · use --port flag
   ✗ "is the triage server running?"     → start it, hard-refresh browser
   ✗ click does nothing                  → check console for plotly_click error
   ✗ side pane shows wrong conv          → coord lookup may collide on dense
                                            clusters · acceptable for now
   ✗ memory_db.json load times out       → 385 MB file, first request takes
                                            5-10 sec, then cached
```

**If verification passes:**

```
   🅐  Add layer-switch persistence (pane stays open across layer changes
       — already works, but verify)
   🅑  Add a "next conv in cluster" / "prev" navigation (small JS addition)
   🅒  Wire the OTHER direction: when you have a thought, find the convs
       that touch it. This is the search-from-side-pane flow.
   🅓  Move to OTHER sources (CC JSONL, Claude export) since cognitive-
       sensor only has ChatGPT (6,534 convs).  Atlas right now is
       chatgpt-only.
```

**Operating context for whoever picks this up:**

- Bruke is a strategic operator, not a coder. Speak strategy/architecture, NOT formal-technical drift.
- He's tired of menus + plans. Hold what he's saying, don't compress it into small executable.
- The v2/ doctrine .md files at `claude-mining/v2/` are CONTAMINATED (title-grep biased). All banner'd. See section below.
- Closed-loop in his terms = "click conv to see full text" — NOT control-theory feedback. Already wired up in this session.

**Companion docs:**

- [`LEGACY_CODE_AUDIT.md`](LEGACY_CODE_AUDIT.md) — full lineage: ChatGPTAnalysis (Sep 2024) → vector_index.pt (May 2025) → faiss_index/ (Jun 2025) → ollama_query*.py (Jun 2025) → cognitive-sensor (Jan 2026) → v2/index/ (May 2026). Every file verified.
- This doc (everything below the line) — the prior session's setup.

---

# (original handoff below)

Generated: 2026-05-28 (session 297b8155 wrapping at ~17% context)

**Companion doc:** [`LEGACY_CODE_AUDIT.md`](LEGACY_CODE_AUDIT.md) — forensic inventory of all old vectoring / FAISS / Ollama CLI / ChatGPTAnalysis code, verified by reading every source file. Added 2026-05-28 by follow-up session.

## What this is

Bruke wants to mine his personal corpus of AI conversations. He started a thread with an external AI that asked clarifying questions. He had me draft answers in this session, caught me hallucinating twice, then steered me to use `es` + `grep` + actual file reads. The corrected answer block is in this doc, ready to paste back to the other AI.

## Three corpora on disk (VERIFIED via byte-range reads, not inference)

### 1. ChatGPT - 3 export bundles

| Path | Pulled | Format |
|---|---|---|
| `C:\Users\bruke\OneDrive\Desktop\8423c259...-2025-01-29-...` | 2025-01-29 | Old single-file `conversations.json` + previous processing pass (chat.html, .md files, __pycache__) |
| `C:\Users\bruke\Legacy\8423c259...-2025-03-12-...` | 2025-03-12 | Old single-file `conversations.json` + `conversations.zip` + `chat.html` + `dalle-generations/` + assets |
| `C:\Users\bruke\OneDrive\Desktop\claude-mining\source-chatgpt\` | 2026-05-21 | NEW chunked: `conversations-000.json` through `conversations-028.json` (29 chunks, 158 .json total) |

Shape (verified): `{title, create_time, update_time, mapping: {id: {message: {author: {role}, content: {parts}}, parent, children}}}`

### 2. Claude - 1 export

`C:\Users\bruke\OneDrive\Desktop\claude-mining\source\` contains:
- `conversations.json` (82 MB, pulled 2026-05-23)
- `memories.json`, `users.json`, `projects/`

Shape (verified): `{uuid, name, summary, created_at (ISO 8601), updated_at, account, ...}` per conversation

### 3. Claude Code sessions - 999 JSONL across 69 projects, 853 MB

Full index: `C:\Users\bruke\Pre Atlas\cc-session-index.md` (human) + `.json` (programmatic)
Script: `C:\Users\bruke\Pre Atlas\cc-session-index.py` (re-runnable)

- 206 top-level sessions + 793 subagent transcripts
- Date range: 2026-02-08 -> 2026-05-28
- Top by activity: STRUDEL (94 MB), Pre Atlas (205 MB), aegis-fabric, STEMai, ComfyUI, POLARIS

Shape (verified): JSONL, one event per line, each with `{type, timestamp, sessionId, content, cwd, ...}`

## Sources Bruke explicitly does NOT have

The original AI's template mentioned "Character.AI/Copilot" - those were NOT Bruke's claim. Don't search for them again.

## CONTAMINATED - do not build on

### 1. May-27 fest-reconcile outputs

`tools/fest-reconcile/festival_out/` outputs from 2026-05-27 are flagged by Bruke as contaminated. Includes:
- chatgpt_temporal.json, cc_temporal.json, fs_temporal.json
- clusters_v0/v1/final.json (+ _v2)
- era_*_matrix.json, era_cluster_matrix.json
- CORPUS_MAP.md, CORPUS_MAP_v2.md, AUDIT_FINDINGS.md

### 2. May-25/26 mining outputs (added 2026-05-28)

The v2/ interpretive .md files at `C:\Users\bruke\OneDrive\Desktop\claude-mining\v2\` inherit the SAME bias as the fest-reconcile outputs. Findings were derived by scanning titles + ctrl-F'ing the corpus, BEFORE the FAISS semantic index existed. Bruke 2026-05-28: *"they were biased and only inferred from title and ctrl-F poorly across a large number of chats."*

**Banner applied 2026-05-28 to:**
- `v2/doctrine_v2.md` (+ addendum)
- `v2/glossary_v2.md` (+ 3 addendums)
- `v2/concept_only_resolution.md`
- `v2/thread5_project_audit.md`
- `v2/understanding_brief_parallax.md`
- `v2/personal_index.md` (+ review)
- `v2/pattern_report_v1.md`
- `v2/timeline_v1.md`
- `v2/manifest_combined.md`
- `v2/shape_report.md`, `v2/stack_map_v1.md`, `v2/p5_parallax_cluster.md`
- `v2/baseline_batch_search_report.md`, `v2/chatgpt_artifact_inventory.md`, `v2/chatgpt_shape_notes.md`
- `scripts/batch_search_report.md`, `scripts/classification_report.md`, `scripts/era_split_report.md`
- memory: `project_chatgpt_g_p_projects.md`, `feedback_projects_have_shapes.md`

**NOT contaminated** (mechanical / data):
- `_corpus.py` (loader), `semantic_search.py` (CLI), `embed_corpus.py`, `build_faiss.py`
- `v2/index/{minilm,mpnet}/` (FAISS embeddings)
- `shape_catalog.json`, `manifest_combined_raw.json`, `chatgpt_sample_normalized.json`
- `parallax_*_human.txt` (raw conv dumps)
- raw sources: `source/`, `source-chatgpt/`, `source-chatgpt-artifacts/`

If you need conclusions from any contaminated file, re-derive from semantic queries against `v2/index/`.

## OLD process - mechanics good, conclusions contaminated

The 2026-05-25 / 2026-05-26 work at `claude-mining/v2/` built the FAISS search infrastructure (verified working 2026-05-28: 7,110 convs indexed, 23ms latency on MiniLM, 117ms on mpnet). The interpretive outputs from that session are contaminated as noted above. **The pipeline mechanics are good; the doctrine outputs are not.**

## Answer block ready to paste to the other AI

```
## 1. What do I want to be able to do?

ALL of them, prioritized:
1. Browse by topic + auto-cluster
2. Track change over time (eras already exist in old mining work)
3. Personal knowledge base / second brain (this is the Pre Atlas project; cognitive-sensor service runs Python + SQLite on conversation analysis)
4. Identify repeated patterns + mistakes
5. Find half-remembered specific conversations (semantic, not just keyword)
6. Plus: doctrine extraction, shipped-vs-abandoned tracking, conversation -> project linkage

## 2. Working environment

- Python + SQLite native; comfortable with ChromaDB; venv-based pipelines fine
- No-code tools NOT needed
- Privacy: tier-based. Cloud APIs OK for work corpus, local-only Ollama for personal/sensitive

## 3. What structure exists

VERIFIED via filesystem reads (es + grep + byte-range), not inference:

ChatGPT - 3 export bundles on disk:
- 2025-01-29 single-file format (older, processed)
- 2025-03-12 single-file format (older, raw)
- 2026-05-21 chunked: 29 conversations-NNN.json files in source-chatgpt/

Claude - 1 export at claude-mining/source/, pulled 2026-05-23. Single conversations.json (82 MB) + memories.json + users.json + projects/.

Claude Code - 999 JSONL session files across 69 project directories, 853 MB, dates 2026-02-08 to today. Full index at cc-session-index.md.

Shapes verified:
- ChatGPT: {title, create_time (unix float), mapping: {id: {message: {author: {role}, content: {parts}}, parent, children}}}
- Claude:  {uuid, name, summary, created_at (ISO 8601), updated_at, account}
- CC:      JSONL events, one per line, with cwd, sessionId, timestamp, content

## What I want from you

A minimal pipeline that:
1. Unifies all 3 sources into one SQLite corpus table
2. Adds semantic vector search on top of keyword search
3. Tier-routes embeddings (local Ollama for sensitive, cloud API for the rest)
4. Re-uses what's already on disk (don't re-derive what exists; just don't trust the May 27 fest-reconcile outputs)
```

## What to do next session

Bruke's open decision: what to do with all this. Options he might pick:
- Get the answer block above to the other AI and proceed with their recipe
- Skip the other AI and start the unified pipeline directly (cognitive-sensor is the natural home)
- First read the OLD process artifacts at claude-mining/v2/ to see what doctrine/patterns/timeline actually contain before deciding

Ask him before assuming.

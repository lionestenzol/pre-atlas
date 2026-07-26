# Reuse Map · Phase 0 Reconciliation

Pre-existing inventory artifacts vs the dogfood-audit deliverables. Generated 2026-05-29.

## 1. What each file actually covers

- **`cc-session-index.py`** — Re-runnable Python script that walks `~/.claude/projects/`, counts `.jsonl` session files per project dir, extracts `cwd` from each, emits both `cc-session-index.md` and `.json`. No analysis logic — pure inventory enumerator.
- **`cc-session-index.md`** — Generated output: 69 project dirs · 999 jsonl files · 853 MB · range 2026-02-08 to 2026-05-28. Table sorted by session count. Top: STRUDEL (94 MB / 345 sessions), Pre Atlas (205 MB / 234 sessions). Pure ops-layer inventory; no library or hand-roll classification.
- **`cc-session-index.json`** — Same data as `.md` but programmatic. Per-project: slug, cwd, sessions_main, sessions_subagent, size_bytes, mtimes, sample_session_ids. No semantic content.
- **`gap-map.md`** — Surface-merge plan for "CycleBoard (atlas core) → inPACT". Lists 16 CycleBoard screens and which 5 collapsed into inPACT; gap table of remaining capabilities (governance/HUD/energy/finance/skills/network/OSINT/AI). Frames as "inPACT is surface, atlas core is engine; CycleBoard becomes parts donor." Surface-consolidation map, NOT a reuse-vs-handroll audit.
- **`NEXT_SESSION_HANDOFF.md`** — 359-line corpus-mining session handoff. Strangler progress 11/15 v2-clean docs. Contains: ATLAS_LAWS.md Law #1 (TGT) reference, contaminated-doc list, FAISS index status (7110 convs, 23ms MiniLM), conversation export shapes, three-corpus disk inventory. Operates on the conversation-mining track, NOT the assemble-first doctrine track.

## 2. Deliverable overlap matrix

Cells: 0=none, P=partial, F=full. Files: SI=cc-session-index (py+md+json bundled), GM=gap-map.md, HO=NEXT_SESSION_HANDOFF.md, IN=inventory.md, LC=LEGACY_CODE_AUDIT.md.

| Deliverable                          | SI | GM | HO | IN | LC |
|--------------------------------------|----|----|----|----|----|
| D1 assemble-first rule               | 0  | 0  | 0  | 0  | 0  |
| D2 swap-backlog                      | 0  | P  | 0  | 0  | 0  |
| D3 moat-map                          | 0  | P  | 0  | P  | 0  |
| D4 fingerprint-memory                | 0  | 0  | 0  | 0  | P  |
| D5 workflow-update                   | 0  | 0  | 0  | 0  | 0  |

Justifications: GM/D2 cites "5 domain trackers = same job five times" and "AI read+act" as candidate consolidations — overlaps with swap-backlog framing. GM/D3 names governance/planning as load-bearing (atlas core engine) — partial moat-naming. IN/D3 (per task spec) is the live ops layer where moats run. LC/D4 is the lineage trail of one pipeline — a fingerprint for one subsystem only.

## 3. Track scope adjustment

- **Track A · reinvention-surface:** No existing file enumerates "categories we hand-rolled vs library candidates." GM hints at it for the 5 trackers but stays at surface-merge level. **Track proceeds as scoped.**
- **Track B · lava-layers:** LC supplies the lineage template for one pipeline (mining); the rest of the federated monorepo lacks equivalent lineage. **Track narrows: reuse LC's format, apply to other subsystems** (delta-kernel, canvas-engine, inPACT, aegis-fabric).
- **Track C · vocab-collisions:** No prior work. NEXT_SESSION_HANDOFF mentions doctrine vocab (WOODLINE/VVAVE/Parallax verdicts) but that's conversation-corpus terms, not code-surface vocab. **Track proceeds as scoped.**
- **Track D · ecosystem-prior-art:** GM does light prior-art naming (CycleBoard → inPACT collapse) but only within Bruke's own repos. No external-library scan exists. **Track proceeds as scoped.**

## 4. Critical recommendations

NEXT_SESSION_HANDOFF.md is **NOT a doctrine-level supersede**. It's a corpus-mining strangler operating on a separate track (claude-mining v2/ contamination cleanup) and does not mention assemble-first, library-vs-handroll choices, or the audit framing. No CRITICAL flag. One adjacent finding: ATLAS_LAWS.md Law #1 (TGT) is referenced as a load-bearing doctrine artifact; the audit deliverables (especially D1 assemble-first rule) should be checked for alignment with the existing Atlas Laws structure rather than creating a parallel doctrine surface — they likely belong as Law #2 or as an annex.

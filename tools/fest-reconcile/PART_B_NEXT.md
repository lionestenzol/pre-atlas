# Part B — corpus-wide intent-vs-artifact reconciliation

**Status:** queued for next session. Part A shipped 2026-05-27 as `dbb3d94` + `92076f8` + `1c7deb6`.

**Goal:** cross-reference the 6,534-conversation memory_db (2024-08-21 → 2026-05-21) against `portfolio_evidence.json` to emit three buckets:

1. **discussed AND shipped** — talk converged into artifact
2. **discussed but NOT shipped** — intent without execution (planning-addiction signal)
3. **shipped but NOT discussed** — execution outside the conversation channel (proof that conversation-as-planning is a small slice of work)

**Re-entry path:**
1. `python tools/fest-reconcile/portfolio.py` — refresh `portfolio_evidence.json`
2. Build `tools/fest-reconcile/corpus_recon.py` — reuses cognitive-sensor classifier output + portfolio JSON
3. Output `conversation_artifact_reconciliation.json` with the 3 buckets + 5-10 spot-check examples per bucket
4. Don't auto-classify — HOTL gate (per the autonomy-level-shift discussion this session)

**Three interrogations to answer before designing:**
- Will future-you actually consume the output JSON?
- Which bucket matters most (planning addiction vs spontaneous-ship proof)?
- Is "conversation" the right unit, or should it be cluster/topic/project?

**Full jargonized brief:** see `~/.claude/jargonize/log.jsonl` (most recent entry, search `talk-vs-walk-audit`).

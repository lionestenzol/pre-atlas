# Part B — corpus-wide intent-vs-artifact reconciliation

**Status:** SHIPPED 2026-05-27, two variants.

## PRIMARY result: Claude Code corpus (cc_corpus_recon.py)

Bruke's note 2026-05-27: "everything got made in claude code for the most part."
This corpus (1017 sessions across 65 project dirs) is the real ship channel.

- `tools/fest-reconcile/cc_corpus_recon.py` (matcher + loader)
- `tools/fest-reconcile/cc_conversation_artifact_reconciliation.json`
- `tools/fest-reconcile/CC_RECONCILIATION_REPORT.md`

**Top-line:** 79 discussed_and_shipped · 33 discussed_but_not_shipped · 7 shipped_but_not_discussed · 16 neither · 5 skipped.

The 7 "shipped without Claude Code discussion" are almost all cloned/vendored repos (airwindows, surge-xt, MB-Lab, outpost, mb3d_anim_demo). So the real "shipped outside the chat channel" count is ~0 - Claude Code is where everything Bruke built came from.

**Surfaced bug in portfolio.py:** band=stale on actively-used items (mini-ship 33 sessions, weapon 18, fest 15, autopilot 14, competitor-monitor 16). portfolio.py uses directory mtime which misses recently-used-but-unchanged skills. Fixing this would move several items from bucket 2 -> bucket 1.

## SIDECAR result: ChatGPT export corpus (corpus_recon.py)

Kept as a side-channel diagnostic. Showed 52 shipped-without-discussion - but that was just "not in ChatGPT," not "undiscussed." Misleading on its own, useful as a contrast against the CC corpus.

- `tools/fest-reconcile/corpus_recon.py`
- `tools/fest-reconcile/conversation_artifact_reconciliation.json`
- `tools/fest-reconcile/RECONCILIATION_REPORT.md`

---

## Original handoff (for reference)

**Part A shipped 2026-05-27 as `dbb3d94` + `92076f8` + `1c7deb6`.**

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

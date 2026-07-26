# Staging — the Atlas × ATM × UASC analysis

> **Purpose.** Get ready for the three-way analysis between **Atlas**, **ATM**, and **UASC/LANGUAGE**. The files on disk are a mess (dupes, mirrors, worktree copies); *this* doc + the three source reports below are the clean truth. Nothing here is the analysis yet — this is the loaded chamber so the analysis fires clean instead of abbreviated.
> **Date:** 2026-06-28.

---

## The three systems (clean, one paragraph each)

**ATLAS** — the personal behavioral-governance OS he actually runs. The `Pre Atlas` monorepo: `delta-kernel` (deterministic state engine, 6-mode FSM RECOVER→CLOSURE→MAINTENANCE→BUILD→COMPOUND→SCALE), CycleBoard, the item-backbone, the atlas-map gateway. *Governs a life.* It is the one of the three that is fully **real and running**.

**ATM (Asynchronous Temporal Mesh)** — the decentralized, time-based content network designed live in the Gemini conversation. The Sun (super-server), Data Mules (sneakernet), the Sundial (append-only ledger), the Ghost Canvas (stateless runtime), homeostasis, LoRa transport. *Moves data across a town with no live internet.* **Dream + scoped-down core**: delta-kernel IS its buildable engine; the city-scale/hardware layer is unbuilt.

**UASC / LANGUAGE** — the symbolic command language. Words→phonemes→binary→novenary→strokes→executable glyphs; a base-9 ISA (NCSE), a stroke writing system (SSES), a compression cosmology up to 道 = all human knowledge (UCHCSE), a trust PKI, an M2M teaching protocol. *Expresses and executes commands as compressed symbols.* **Dream → sober build → live "hands"**: the `uasc-executor` (:3008) runs as delta-kernel's execution layer.

---

## Canonical source docs (read these, ignore the disk mess)

| System | Clean doc(s) | Status |
|---|---|---|
| **ATM** | [GEMINI_ATM_MAP.md](GEMINI_ATM_MAP.md) + [GEMINI_ATM_TRANSCRIPT.md](GEMINI_ATM_TRANSCRIPT.md) | ✅ complete, verified |
| **UASC** | [UASC_LANGUAGE_REPORT.md](UASC_LANGUAGE_REPORT.md) | ✅ core read first-hand; ⚠️ skipped: lab `mvp/` + `spec/` docs, LANGUAGE `sections/`, service `server.py`/`auth.py` |
| **ATLAS** | — none yet — | ❌ **gap.** No single clean standalone doc. Lives in `MEMORY.md`, the `delta-kernel` code, and `atlas-manifest.yaml`. Needs one before the comparison. |

---

## The comparison framework (pre-loaded axes)

When the analysis runs, compare the three on these axes:

1. **Domain — what it acts on.** Atlas governs *a life*; ATM moves *data*; UASC expresses *commands*. (governance / transport / language)
2. **The unit.** Atlas = the *delta/event* (+ mode). ATM = the *seed/key* over the Sundial. UASC = the *glyph/token*. All three: a tiny thing that unfolds into a whole plan.
3. **Brain vs hands.** Atlas = the brain (decides). UASC-executor = the hands (does). ATM = the would-be nervous system (transport). delta-kernel is where brain and hands meet.
4. **Dream → build → ship tier.** Atlas = shipped/running. ATM = dream + core only. UASC = full arc visible (cosmology → opcode engine → live token runner).
5. **The shared signature** (test each against it): time-as-storage / append-only · determinism over generation · compression-to-essence · trust + audit · self-expansion.
6. **Connection topology.** Working hypothesis: **delta-kernel is the hub.** It's the scoped ATM engine, it's Atlas's core, and uasc-executor bolts onto it as hands. ATM = how things *move*, UASC = how things are *said*, Atlas = how things are *governed* — three faces of one deterministic, event-sourced spine. (To be proven in the analysis, not assumed.)

---

## File-mess status (disk ≠ docs)

- UASC canonical homes: `Downloads/LANGUAGE` (corpus) · `research/uasc-m2m` (lab) · `services/uasc-executor` (service) · `delta-kernel/.../executor-bridge.ts` (wire) · `cortex/.../uasc_client.py` (consumer).
- Noise to ignore (do NOT bulk-delete — git worktrees + backups): ~30 `.claude/worktrees/*` copies, the `pre-atlas` hyphen mirror, the self-nested `research/uasc-m2m/UASC-M2M/`, the loose zips, the `claude-mining` LANGUAGE copy.
- Dedup is a **separate, careful job** — flagged, not done. Worktree copies are git-managed; deleting inside them corrupts worktrees.

---

## To run the full analysis at full power (the checklist)

1. Write the missing **clean ATLAS doc** (synthesize from `delta-kernel` code + `MEMORY.md` + `atlas-manifest.yaml`).
2. Finish the **UASC rescan** of the skipped files (lab `mvp/`, `spec/`, LANGUAGE `sections/`, service `server.py`/`auth.py`) — first-hand, no agents.
3. With all three clean docs in hand, run the comparison on the 6 axes above → one analysis artifact.

> **Recommendation:** run step 3 (and finish 1–2) in a **fresh context.** This session is deep, and a deep context is exactly what produced the abbreviated takes — the three-way analysis deserves full power so it lands with the intensity the architecture has, not a degraded skim.

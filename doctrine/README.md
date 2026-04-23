# doctrine/

Founding docs for the Optogon stack. Read in order.

| # | File | What it is |
|:---|:---|:---|
| 01 | [SEED](01_SEED.md) | Discovery doc — stack vision, philosophy, moat |
| 02 | [ROSETTA_STONE](02_ROSETTA_STONE.md) | Interlayer data contracts — five contracts between layers |
| 03 | [OPTOGON_SPEC](03_OPTOGON_SPEC.md) | Product spec v2.1 — nodes, paths, session state, MVP scope |
| 04 | [BUILD_PLAN](04_BUILD_PLAN.md) | Concrete mapping onto this repo, four-phase build, lane choice |
| 05 | [FEST_PLAN](05_FEST_PLAN.md) | Festival-shaped projection of build plan; festival/phase/sequence/task structure + copy-paste command block to materialize in WSL Ubuntu next session |

**The stack:** `Site Pull → Optogon → Atlas → Ghost Executor → InPACT`

**Status (2026-04-22):** Phases 1-4 shipped. Phase 5 (fs-loop extension) shipped same day.

| Phase | Status | Commit / Date |
|:---|:---|:---|
| 1 · Contracts | DONE | 065a4a6 (2026-04-18) · 10 schemas + validator |
| 2 · Optogon service | DONE | 9a7b299 (2026-04-19) · FastAPI :3010, 16 tests |
| 3 · Atlas / Cortex / InPACT wiring | DONE | 306e6f7 (2026-04-19) · Directive + Signals |
| 4 · Close-loop + preference store | DONE | d5b82cf (2026-04-19) · ui_theme pref proven |
| 5 · Universal Triage Inbox | DONE | 2026-04-22 · es eyes + triage_fs_loop + auto_triage + cortex_bridge |

**Phase 5 additions (2026-04-22):**
- Second pair of eyes: `es_scan.py` in cognitive-sensor uses Everything CLI for machine-wide loop detection
- New Optogon path: `services/optogon/paths/triage_fs_loop.json` (5 nodes) with handlers `inspect_fs_item`, `propose_fs_verdict`
- Autonomous driver: `auto_triage.py` runs as run_daily.py Phase 1.7
- UI live-wire: `triage_server.py` exposes POST /api/decide so thread_cards.html swipes flow straight into Atlas state
- Cortex bridge: `cortex_bridge.py` emits Directive.v1 from proposed actions (dry-run default; in-repo scope only)
- Thread cards render Optogon proposals inline with [ACCEPT PROPOSAL] one-click

See `PRE_ATLAS_MAP.md` section "Universal Triage Inbox" for the full flow and the three-switch safety ladder.

**Next session entry point:** review `cortex_directives_log.json` proposals; if sane, flip `CORTEX_BRIDGE_APPLY=1`. For in-repo closures, also `CORTEX_BRIDGE_RUN_PROPOSAL=1`. Original lane still pending: materialize the fest tree in WSL Ubuntu (Section 8 of `05_FEST_PLAN.md`).

**Governing principle:** The user experiences a conversation. The system executes a close.

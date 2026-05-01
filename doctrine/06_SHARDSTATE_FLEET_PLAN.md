# SHARDSTATE FLEET — FESTIVAL PLAN
*Target: ship the shardstate edge-coordination stack as a fleet of small ships, each independently testable*
*Status 2026-05-01: Festival authored. Ships 1 (library) ✅ shipped on `claude/shardstate-coordination-ZxEgN`. Ships 2, 5, 6 are the next parallel build wave (no hardware needed). Ships 3, 4 deferred until LoRa hardware is in hand.*

---

## 1. Festival Identity

| Field | Value |
|:---|:---|
| **Name** | `shardstate-fleet` |
| **Type** | `implementation` |
| **Goal** | Ship the shardstate edge-coordination stack so that two devices can coordinate via Merkle refs over a constrained transport (LoRa-class), with a deterministic ops layer enabling shared-behavior coordination — so a real edge pair (e.g. two Pis) can run end-to-end without prose handoffs |
| **Lifecycle start** | `festivals/planning/` (moves to `ready/` after validation, `active/` at first task start) |

---

## 2. Phase Structure (8 phases)

Six implementation phases bracketed by `000_PLAN` and `999_REVIEW`. Phases 001-003 are **independent of hardware** and run in parallel agents this session. Phases 004-005 are blocked on real LoRa hardware and run later.

| # | Phase | Type | Hardware? | Why this type |
|:---|:---|:---|:---|:---|
| 000 | `000_PLAN` | `planning` | — | This file. Decisions D1-D5 below. |
| 001 | `001_WIRE` | `implementation` | no | Ship 2: binary codec for Ref + 2-device sync over a stream |
| 002 | `002_MCP_DEMO` | `implementation` | no | Ship 5: local-LLM-style agent driving shardstate via MCP |
| 003 | `003_OPS` | `implementation` | no | Ship 6: deterministic ops layer (Option A — registered functions) |
| 004 | `004_RADIO` | `implementation` | **YES** | Ship 3: LoRa transport adapter on top of 001 wire format |
| 005 | `005_STEG` | `implementation` | **YES** | Ship 4: steganographic packing inside carrier traffic |
| 999 | `999_REVIEW` | `review` | — | Measure against success metrics in §7 |

**Parallelism:** Phases 001, 002, 003 are mutually independent — they touch disjoint file sets. They run as **three parallel agents in separate git worktrees** off `claude/shardstate-coordination-ZxEgN` and merge sequentially after each completes.

---

## 3. Decisions (from earlier conversation)

| # | Decision | Resolution |
|:---|:---|:---|
| D1 | shardstate scope | Stay small. Single SQLite, trusted fleet, polling subscribe. ✅ Decided. |
| D2 | Use case framing | Edge LLM + LoRa, not cloud agent fleets. The bandwidth constraint forces the technique. ✅ Decided. |
| D3 | Steg as compression vs covert channel | **Compression / bandwidth amplifier.** Embed compressed refs in carrier LSBs. ✅ Decided. |
| D4 | Ops layer execution model | **Option A: registered functions.** Both devices import the same Python module; ship `(op_id, args)`. Sandbox/VM (Option B) deferred until proven necessary. ✅ Decided. |
| D5 | Fleet shape | Many mini-ships, not one big ship. Each ship answers one assumption. ✅ Decided. |

---

## 4. Sequence + Task Breakdown (implementation phases)

### Phase 001_WIRE — Ship 2 (binary codec + 2-device sync)

**Goal:** Ref binary-packs to ≤32 bytes; two Stores can converge by exchanging packed refs over a stream.

| Seq | Tasks |
|:---|:---|
| `01_codec` | `01_pack_unpack_ref.md`, `02_pack_state_root.md`, `03_codec_tests.md` |
| `02_sync` | `01_sync_protocol.md`, `02_missing_node_request.md`, `03_sync_tests.md` |

**Files owned:** `shardstate/src/shardstate/wire.py`, `shardstate/src/shardstate/sync.py`, `shardstate/tests/test_wire.py`, `shardstate/tests/test_sync.py`. No edits to existing files except `__init__.py` exports.

### Phase 002_MCP_DEMO — Ship 5 (local-LLM agent demo)

**Goal:** A working example where two "agents" (mocked LLM call sites) coordinate via shardstate; documented path to swap the mock for ollama/llama.cpp.

| Seq | Tasks |
|:---|:---|
| `01_demo` | `01_two_agent_demo.md`, `02_mock_llm_caller.md` |
| `02_docs` | `01_examples_readme.md`, `02_ollama_wiring_notes.md` |

**Files owned:** `shardstate/examples/` (new directory). No edits to existing files.

### Phase 003_OPS — Ship 6 (deterministic ops, Option A)

**Goal:** `@op` decorator registers deterministic functions; `run_op(name, args, parent_state)` applies + verifies; an op-ref packs to ≤40 bytes.

| Seq | Tasks |
|:---|:---|
| `01_registry` | `01_op_decorator.md`, `02_determinism_guard.md`, `03_registry_tests.md` |
| `02_runner` | `01_run_op.md`, `02_op_ref_format.md`, `03_runner_tests.md` |

**Files owned:** `shardstate/src/shardstate/ops.py`, `shardstate/tests/test_ops.py`. No edits to existing files except `__init__.py` exports.

### Phase 004_RADIO — Ship 3 (LoRa transport) — **BLOCKED on hardware**

To run when 2× LoRa modules + 2× Pis are in hand. Wraps Phase 001 wire format in a LoRa frame, measures bytes/sec, packet-loss rate, time-to-coordinate.

### Phase 005_STEG — Ship 4 (steg packing) — **BLOCKED on Ship 3**

Embeds compressed refs in LSBs of a carrier message type chosen later. Order: compress (zstd shared dict) → embed → send.

---

## 5. Quality Gates

Standard fest 4-gate suffix appended to each implementation sequence:

1. `NN_testing` — pytest passes for the sequence
2. `NN_review` — self-review against task `Definition of Done`
3. `NN_iterate` — address findings
4. `NN_fest_commit` — commit with task reference

For this session these are inlined into each agent's instructions rather than authored as separate files.

---

## 6. Execution — This Session

```bash
# Each parallel ship runs as a Claude Agent with isolation: "worktree"
# The agents share the same starting commit but commit to separate branches:
#   - claude/shardstate-coordination-ZxEgN-ship2-wire
#   - claude/shardstate-coordination-ZxEgN-ship5-mcp
#   - claude/shardstate-coordination-ZxEgN-ship6-ops
# After all three return, merge them back to the parent branch sequentially.
```

**Spawn order:** all three agents in a single tool message (true parallelism).

**Merge order:** Ship 2 → Ship 6 → Ship 5 (alphabetical by file boundary, no functional dependency).

**Validation after merge:** `cd shardstate && python -m pytest tests/` — all tests pass (existing 26 + new ones from each ship).

---

## 7. Definition of Done — This Festival

The festival is complete when ALL are true:

- [ ] Ship 2 lands: Ref binary packs to ≤32 bytes; sync test demonstrates two Stores converging.
- [ ] Ship 5 lands: a runnable demo in `examples/` showing two-agent coordination via shardstate.
- [ ] Ship 6 lands: `@op` registry + `run_op` + determinism guard all pass tests; op-ref packs to ≤40 bytes.
- [ ] All ships: pytest green on the merged branch.
- [ ] README updated with brief notes on the new modules (no fabricated benchmarks).
- [ ] Branch pushed to `origin/claude/shardstate-coordination-ZxEgN`.
- [ ] Hardware-blocked ships (3, 4) clearly documented as deferred with prerequisites listed.

---

## 8. Deferred / Known Risks

- **Determinism in Python is delicate**: floating-point order, dict iteration in some patterns, `time.time()` calls inside ops. Ship 6's determinism guard rejects obvious cases (banned imports) but can't catch every nondeterminism. Mitigation: keep ops small, document the constraints, prefer integers over floats.
- **Wire format may need to change for LoRa frame headers**: Ship 2 produces a stream-oriented codec. LoRa modules want fixed-size frames with their own preambles. Ship 3 will wrap, not replace, Ship 2's format. If Ship 3 reveals a misfit, Ship 2's codec is internal enough to revise.
- **MCP demo without a real LLM is a smoke test, not a value test**: Ship 5 proves the plumbing connects. Real value validation requires a real edge LLM, which is downstream of Ship 4 / Ship 5 hardware availability.
- **Three parallel agents in worktrees can produce subtly inconsistent style**: e.g. one agent might use `dataclass`, another `attrs`. Mitigation: explicit constraints in each agent brief; reviewer (me) reconciles after merge.

---

## 9. Next Session Entry Point (after this session ships 2/5/6)

1. Verify merged state: `git log --oneline claude/shardstate-coordination-ZxEgN -10`
2. Run full test suite: `cd shardstate && python -m pytest tests/ -v`
3. If all green: order LoRa hardware (RFM95W or SX1276 modules + 2× Pi 4 or Pi Zero 2W).
4. Once hardware arrives: begin Phase 004_RADIO. First task: validate Ship 2 wire format actually serializes/deserializes over a UART link between two Pis (no LoRa yet — just UART) before introducing the radio variable.
5. Phase 005_STEG begins after 004 reports stable transmission.

---

*This plan is the fleet projection of the shardstate vision discussed 2026-05-01. The vision is the source of truth for what we're building toward. This doc is the source of truth for how to ship it incrementally.*

# Optogon Audit Report

*Generated 2026-04-19 by Claude Opus 4.7 on claude.ai, given `doctrine/AUDIT_BUNDLE.md` as attachment. Run via Claude-in-Chrome MCP from a Claude Code session.*

*Source chat: https://claude.ai/chat/6a0943e0-0e06-4303-86d7-628307d427cf*

---

## Optogon Audit — Findings

**Scope:** Doctrine 01–05 vs. the schema + code excerpts provided. All findings tagged BLOCKING / DEVIATION / OK-DEFERRED / OK.

### 1. Schema fidelity to Rosetta Stone

- **DEVIATION** — `OptogonNode.qualification.required` is an array, spec is a map. Spec Section 6 writes `"required": [ {key, ...} ]` (array), and the schema matches. But Section 14's pseudocode iterates `for key, req in current_node.qualification["required"].items()` — i.e. treats it as a dict. `node_processor._handle_qualify` correctly uses the array shape, so the code matches the schema; the spec pseudocode is the one out of sync. Worth flagging because a non-code reader comparing spec→code directly will think the implementation is wrong when the spec is.
- **OK** — enums match. Node types (qualify/execute/gate/fork/approval/close), node states, risk tiers, context tiers, and signal source layers all line up with Rosetta Stone and Spec.
- **OK** — transitions required fields. Schema requires `[to, condition]`; spec Section 6 shows priority too but as optional. Consistent.

### 2. Node processor vs. Spec Section 14

- **DEVIATION** — "qualify first, infer second, ask last" ordering is inverted. Spec §14 step order: (1) LLM parse user input → user tier, (2) apply inference for missing keys, (3) check qualification. `_handle_qualify` does this — but only seeds the user tier if exactly one key is missing (`if len(missing) == 1`). With 2+ missing keys, the user's message is discarded and inference runs on empty. The commit_a_file entry node has two required keys (file_path, commit_message) and asks one bundled question — so a user reply like "services/optogon/foo.py, fix typo" never gets parsed. **This is a real behavioral gap vs. the spec's "one question does multiple jobs" doctrine.**
- **DEVIATION** — LLM parse step is missing entirely. Spec §14 calls `llm_parse(user_message, required)` to extract structured values. The code does a raw `.strip()` assignment. This is tied to the stub LLM note in the bundle, but it means inference currently can't split a multi-key answer even when the LLM exists.
- **OK** — promotion to confirmed on qualification. Good call, and correctly enables the preference store loop.
- **OK** — context hierarchy enforcement. `resolve()` / `set_tier()` respect `confirmed > user > inferred > system`. System-tier writes from action results never override user intent — matches Rosetta's cross-session memory rules.

### 3. Pacing layer vs. Spec Section 10

- **DEVIATION** — pacing is advisory, not enforced. Spec §10 lists pacing as "strict constraints." The code calls `compose(node, state)` which returns text + token count and increments a metric, but there's no visible gate rejecting responses that exceed `max_options_shown`, violate `max_questions_per_turn`, or leak node IDs. The question counter uses "?" in text as a proxy — a response with two questions counts as one. **For a system whose moat is pacing discipline, this is the most important gap to close.**

### 4. Deferrals

- **OK-DEFERRED** — Learning Layer, fork nodes, Site Pull integration, Interrupt Protocol, Fest materialization. All explicitly scoped out in Build Plan §4 and the "won't build" list.
- **BLOCKING** — `ship_inpact_lesson` being stubbed is a doctrine miss. Build Plan D3 chose it specifically because it "tests doctrine against real work you already do." `commit_a_file` is a fine second path, but it's a generic git workflow. Per Seed Part 6, the moat is the judgment, not the engine — and `commit_a_file` doesn't exercise any inPACT-specific judgment (shared CSS merge, lesson skeleton, preview). The bundle flags this honestly ("requires inPACT curriculum first") — but the call-out in the brief asks whether something core got stubbed, and the answer is yes: the path D3 explicitly picked to validate the doctrine.

### 5. commit_a_file as "closer" behavior

- **DEVIATION (soft)**. It's a clean workflow engine demo, not a closer. A closer removes burden: if file_path is clear from context, don't ask. If the diff is small and `feedback_*` rules are clean, auto-propose a commit message rather than requiring the user to type one. Currently both keys are hard-required from the user with no inference rules attached. This is Optogon running as a deterministic FSM, not as the burden-removal layer the doctrine describes. **The machinery is right; the path author didn't use it.**

### 6. Architecture deviations a non-code reader would miss

- **Close signal posts to delta-kernel via HTTP with silent failure** (`except Exception: pass`). Rosetta Contract 2 rule 1 says Optogon "must emit a close signal on every terminal state" — swallowing network errors makes Atlas silently miss completions. Should at minimum log or buffer.
- **`inference_accuracy = 1.0` placeholder** in the close signal. Spec §11 sets >0.85 as a success metric; hardcoding 1.0 means the metric is uninstrumented, not met.
- **`nodes_total` set only at close** — earlier in-flight sessions report `nodes_total: 0`, making mid-session progress reporting impossible for InPACT.

### Priority stack

1. **Pacing enforcement** (§3)
2. **Multi-key qualify parsing** (§2)
3. **Swap stubs back for ship_inpact_lesson** when curriculum lane opens
4. **Burden-removal inference rules** on real paths (§5)

> The contracts-and-scaffold work is solid; the doctrine-specific behavior is where it thins out.

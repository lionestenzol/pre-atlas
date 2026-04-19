#!/usr/bin/env python3
"""
write_fest_tasks.py
Materializes the optogon-stack festival task body markdown files.

Two modes:
  --target staging  (default)  Writes to doctrine/fest_staging/optogon-stack/
                                For review in repo. Overwrites every run.
  --target fest                Writes to /root/festival-project/festivals/<lifecycle>/optogon-stack/
                                Use after `fest create festival/phase/sequence` has
                                scaffolded the directory tree. WSL only.
  --target <path>              Writes to a custom absolute path.

Source of truth for task content lives in TASKS below. Editing a generated .md
file under fest_staging is futile — re-running the script overwrites it. Edit
this script instead.

Usage:
  python doctrine/scripts/write_fest_tasks.py
  python doctrine/scripts/write_fest_tasks.py --target staging
  python doctrine/scripts/write_fest_tasks.py --target fest --lifecycle planning
  python doctrine/scripts/write_fest_tasks.py --dry-run
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Task data structure
#
# TASKS is a dict keyed by phase. Each phase is a dict keyed by sequence.
# Each sequence is a list of (filename, content_dict) tuples.
# content_dict = {objective, requirements, steps, dod}
# Templates render to a standard fest task markdown format.
# ---------------------------------------------------------------------------

PHASES = ["000_PLAN", "001_CONTRACTS", "002_OPTOGON_SERVICE", "003_INTEGRATION", "004_CLOSE_LOOP", "999_REVIEW"]


def task(objective: str, requirements: list[str], steps: list[str], dod: list[str]) -> dict:
    return {"objective": objective, "requirements": requirements, "steps": steps, "dod": dod}


# ---- 001_CONTRACTS ---------------------------------------------------------
CONTRACTS_01_OPTOGON = [
    ("01_optogon_node.md", task(
        objective="Create OptogonNode.v1.json schema covering all node types from spec Section 6.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 6 (Node Architecture)",
            "Schema must support node types: qualify, execute, gate, approval, close, fork",
            "Required top-level fields: id, type, label, qualification_keys, actions, transitions, schema_version",
            "Use $schema draft-07 to match existing contracts/schemas/ConventionVersion",
            "schema_version field literal '1.0'",
        ],
        steps=[
            "Open contracts/schemas/ for naming/format reference (ModeContract.v1.json)",
            "Author contracts/schemas/OptogonNode.v1.json",
            "Cross-check every field name against spec Section 6",
            "Validate schema itself parses with jsonschema.Draft7Validator.check_schema",
        ],
        dod=[
            "File contracts/schemas/OptogonNode.v1.json exists",
            "Draft-07 self-check passes",
            "Covers all 6 node types with type-specific conditional requirements",
        ],
    )),
    ("02_optogon_path.md", task(
        objective="Create OptogonPath.v1.json schema per spec Section 7.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 7 (Path Composition)",
            "Path = ordered+branching graph of OptogonNode references",
            "Required: id, label, description, entry_node_id, nodes[], success_criteria, schema_version",
            "Each node reference can be inline or by id pointing into a registry",
        ],
        steps=[
            "Author contracts/schemas/OptogonPath.v1.json",
            "Use $ref into OptogonNode.v1.json for inline node definitions",
            "Allow alternative: nodes[] of just id strings + separate node_registry",
        ],
        dod=[
            "Schema validates against draft-07",
            "Example with ship_inpact_lesson shape (5+ nodes) parses",
        ],
    )),
    ("03_optogon_session_state.md", task(
        objective="Create OptogonSessionState.v1.json schema per spec Section 8.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 8 (Session State Model)",
            "Captures: session_id, path_id, current_node_id, context tiers, history, started_at",
            "Context hierarchy fields (confirmed, user, inferred, system) per spec",
            "schema_version literal '1.0'",
        ],
        steps=[
            "Author contracts/schemas/OptogonSessionState.v1.json",
            "Model context tiers as 4 named objects in a parent context object",
            "Include node_history array tracking entered_at/closed_at per node",
        ],
        dod=[
            "Schema validates against draft-07",
            "Round-trips through json.dump/load without loss",
        ],
    )),
]

CONTRACTS_02_ROSETTA = [
    ("01_context_package.md", task(
        objective="Create ContextPackage.v1.json schema per Rosetta Stone Contract 1.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 1",
            "Top-level: id, source, captured_at, structure_map, dependency_graph, action_inventory, inferred_state, token_count, compression_ratio",
            "Must support partial_context_package variant with coverage_score",
        ],
        steps=[
            "Copy field tree directly from Rosetta Contract 1 'What Site Pull Produces'",
            "Express enums for source, route.method, component.type, action.type, action.risk_tier",
            "Add schema_version field",
        ],
        dod=[
            "Schema validates against draft-07",
            "Includes both full and partial variants via oneOf",
        ],
    )),
    ("02_close_signal.md", task(
        objective="Create CloseSignal.v1.json schema per Rosetta Stone Contract 2.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 2",
            "Top-level: id, session_id, path_id, closed_at, status, deliverables, session_summary, decisions_made, unblocked, context_residue, interrupt_log",
            "status enum: completed, abandoned, failed, forked",
        ],
        steps=[
            "Author contracts/schemas/CloseSignal.v1.json",
            "Make context_residue.learned_preferences an open object (additionalProperties true)",
            "Make session_summary fields all required and numeric",
        ],
        dod=[
            "Schema validates against draft-07",
            "All four status values accepted in enum check",
        ],
    )),
    ("03_directive.md", task(
        objective="Create Directive.v1.json schema per Rosetta Stone Contract 3.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 3",
            "Top-level: id, issued_at, priority_tier, leverage_score, task, context_bundle, execution, interrupt_policy",
            "task.success_criteria minItems 1 (Atlas must never emit empty success_criteria)",
        ],
        steps=[
            "Author contracts/schemas/Directive.v1.json",
            "Enforce task.success_criteria minItems via JSON schema",
            "Constrain leverage_score to [0,1]",
        ],
        dod=[
            "Schema validates against draft-07",
            "Example with empty success_criteria fails validation",
        ],
    )),
    ("04_task_prompt.md", task(
        objective="Create TaskPrompt.v1.json schema per Rosetta Stone Contract 4 (request side).",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 4 (Ghost Executor → Claude Code)",
            "Top-level: id, directive_id, issued_at, instruction, environment, prior_attempts, output_spec, constraints",
            "Must include both success_criteria and failure_criteria as required arrays",
        ],
        steps=[
            "Author contracts/schemas/TaskPrompt.v1.json",
            "Make do_not_modify a constraint string array (treated as hard rule downstream)",
        ],
        dod=[
            "Schema validates against draft-07",
            "Examples missing failure_criteria fail validation",
        ],
    )),
    ("05_build_output.md", task(
        objective="Create BuildOutput.v1.json schema per Rosetta Stone Contract 4 (response side).",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 4 (response shape)",
            "Top-level: task_prompt_id, completed_at, status, artifacts, summary, issues_encountered, follow_on_tasks, tokens_used",
            "status enum: success, partial, failed",
        ],
        steps=[
            "Author contracts/schemas/BuildOutput.v1.json",
            "Make artifacts.path required only for type=file or type=diff (conditional)",
        ],
        dod=[
            "Schema validates against draft-07",
            "Failure-status example with empty artifacts still validates (silent failure forbidden but empty allowed)",
        ],
    )),
    ("06_signal.md", task(
        objective="Create Signal.v1.json schema per Rosetta Stone Contract 5.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md CONTRACT 5 (Universal Signal Schema)",
            "Top-level: id, emitted_at, source_layer, signal_type, priority, payload",
            "source_layer enum: site_pull, optogon, atlas, ghost_executor, claude_code",
            "signal_type enum: status, completion, blocked, approval_required, error, insight",
            "When action_required true, action_options must be non-empty",
        ],
        steps=[
            "Author contracts/schemas/Signal.v1.json",
            "Use if/then/else to enforce action_options when action_required is true",
        ],
        dod=[
            "Schema validates against draft-07",
            "Approval-required example without action_options fails validation",
        ],
    )),
    ("07_user_preference_store.md", task(
        objective="Create UserPreferenceStore.v1.json schema per Rosetta Stone cross-session memory section.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md 'Cross-Session User Memory'",
            "Top-level: user_id, last_updated, preferences[], behavioral_patterns[]",
            "preferences[].source enum: explicit, inferred",
            "preferences[].confidence in [0,1]",
        ],
        steps=[
            "Author contracts/schemas/UserPreferenceStore.v1.json",
            "Constrain confidence numeric range",
        ],
        dod=[
            "Schema validates against draft-07",
            "Example with confidence > 1 fails validation",
        ],
    )),
]

CONTRACTS_03_EXAMPLES = [
    ("01_author_one_example_per_schema.md", task(
        objective="Author one valid example per schema in contracts/examples/.",
        requirements=[
            "10 example files matching the 10 schemas (3 Optogon + 7 Rosetta)",
            "Examples must be realistic — use ship_inpact_lesson as the running example where possible",
            "File naming: contracts/examples/<schema_basename>.example.json",
        ],
        steps=[
            "For each schema in contracts/schemas/, create matching example file",
            "Cross-link: ContextPackage example references same routes that ship_inpact_lesson path uses",
            "Directive example references the OptogonPath example by id",
        ],
        dod=[
            "10 example files exist",
            "Each example is valid JSON",
        ],
    )),
    ("02_validate_all_examples.md", task(
        objective="Run jsonschema validator over every example against its schema; all must pass.",
        requirements=[
            "Use the validator from sequence 04 as the runner",
            "Exit non-zero if any example fails",
        ],
        steps=[
            "Run python contracts/validate.py",
            "Read its output; fix any failing examples or schemas",
            "Re-run until clean",
        ],
        dod=[
            "validate.py exits 0",
            "Output line: '10 schemas, 10 examples, all valid'",
        ],
    )),
]

CONTRACTS_04_VALIDATOR = [
    ("01_validator_py.md", task(
        objective="Create contracts/validate.py — loads every schema and example, asserts validity.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 1 step 3 deliverable",
            "Iterate contracts/schemas/*.json and contracts/examples/*.json",
            "Pair by basename (OptogonNode.v1.json ↔ OptogonNode.v1.example.json)",
            "Use jsonschema library (Draft7Validator)",
            "Exit code 0 on success, 1 on any failure",
        ],
        steps=[
            "Author contracts/validate.py",
            "Add jsonschema to requirements (if not already present in contracts/)",
            "Print summary: schema count, example count, validation status",
        ],
        dod=[
            "python contracts/validate.py exits 0 with clean output",
            "Deleting any example causes script to fail with clear error",
        ],
    )),
]

# ---- 002_OPTOGON_SERVICE ---------------------------------------------------
SERVICE_01_SCAFFOLD = [
    ("01_pyproject_and_start_bat.md", task(
        objective="Create services/optogon/pyproject.toml and start.bat.",
        requirements=[
            "Match pattern from services/cortex/ and services/cognitive-sensor/",
            "pyproject.toml: name=optogon, deps=fastapi, uvicorn, pydantic, jsonschema, sqlite (stdlib)",
            "start.bat launches uvicorn on :3010",
        ],
        steps=[
            "Copy services/cortex/pyproject.toml as template, change name + deps",
            "Author start.bat with: uvicorn optogon.main:app --port 3010 --reload",
        ],
        dod=[
            "services/optogon/pyproject.toml exists and parses",
            "services/optogon/start.bat launches without ImportError (smoke test)",
        ],
    )),
    ("02_dir_tree.md", task(
        objective="Create the full src/optogon/ directory layout from build plan Phase 2.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 2 scaffold tree",
            "Create empty __init__.py + stub files for: main.py, config.py, node_processor.py, contract_validator.py, response_composer.py, session_store.py, context.py, inference.py, signals.py",
            "Create paths/ with _template.json and ship_inpact_lesson.json placeholder",
            "Create tests/ with empty test files",
        ],
        steps=[
            "Create directory tree under services/optogon/src/optogon/",
            "Each .py stub has module docstring + 'pass' or empty class skeleton",
            "_template.json contains a minimal valid OptogonPath",
        ],
        dod=[
            "All directories and files exist",
            "python -c 'import optogon' succeeds (after pip install -e .)",
        ],
    )),
    ("03_launch_json_entry.md", task(
        objective="Add optogon entry to .claude/launch.json so preview tooling can start it.",
        requirements=[
            "Match pattern of existing entries in .claude/launch.json",
            "Name: 'optogon'",
            "runtimeExecutable: services/optogon/start.bat OR uvicorn (cross-platform)",
            "port: 3010",
        ],
        steps=[
            "Read .claude/launch.json",
            "Append new configuration object",
            "Verify JSON parses",
        ],
        dod=[
            "preview_start name='optogon' boots a server on :3010",
            "GET http://localhost:3010/health returns 200",
        ],
    )),
]

SERVICE_02_CORE = [
    ("01_session_store.md", task(
        objective="Implement session_store.py — in-memory + SQLite persistence of OptogonSessionState.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 8",
            "API: create_session, get_session, update_session, close_session",
            "Backing: SQLite file at services/optogon/data/sessions.db (auto-created)",
            "Validate state against OptogonSessionState.v1.json on every write",
        ],
        steps=[
            "Author session_store.py",
            "On startup, ensure sessions table exists",
            "Use json column for full state blob; index session_id",
        ],
        dod=[
            "Round-trip create→update→get returns equal state",
            "Schema-invalid state raises before write",
        ],
    )),
    ("02_context_hierarchy.md", task(
        objective="Implement context.py — confirmed > user > inferred > system tier resolver.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md context hierarchy section",
            "API: resolve(key, session_state) → (value, tier) or (None, None)",
            "Tier order: confirmed > user > inferred > system",
        ],
        steps=[
            "Author context.py with resolve() and set_tier(key, value, tier)",
            "Add merge() that promotes inferred → confirmed when user explicitly confirms",
        ],
        dod=[
            "Unit test: confirmed value beats user value beats inferred value",
            "Unit test: resolve returns (None, None) for unknown key",
        ],
    )),
    ("03_inference_rules.md", task(
        objective="Implement inference.py — Burden-Removal inference rules from spec.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Burden-Removal section",
            "Each rule: input qualification keys + system context → inferred value with confidence",
            "Confidence > 0.85 means it propagates to learned_preferences in close signal",
        ],
        steps=[
            "Author inference.py with apply_rules(session_state) → list of (key, value, confidence)",
            "Implement at least 3 starter rules per spec examples",
            "Mark rules as data-driven (loadable from JSON later)",
        ],
        dod=[
            "Unit test: known input produces known inferred output with expected confidence",
            "Output structure matches what session_store expects",
        ],
    )),
    ("04_contract_validator.md", task(
        objective="Implement contract_validator.py — load & validate against contracts/schemas/.",
        requirements=[
            "API: validate(payload, contract_name) → True or raises ContractError",
            "Loads schemas lazily; caches Draft7Validator instances",
            "Used at every emit boundary (close signal, signal to inpact, directive consume)",
        ],
        steps=[
            "Author contract_validator.py",
            "Resolve schema path relative to repo root via env var or sys.path walk",
            "Add small test using OptogonNode example",
        ],
        dod=[
            "validate(valid_payload, 'CloseSignal') returns True",
            "validate(invalid_payload, 'CloseSignal') raises ContractError with field detail",
        ],
    )),
]

SERVICE_03_NODE = [
    ("01_processor_skeleton.md", task(
        objective="Create node_processor.py skeleton — process_turn(session, message) entry point.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 14",
            "Single entry: process_turn(session_state, user_message) → (new_state, response_text, signals)",
            "Branches by current node.type",
        ],
        steps=[
            "Author node_processor.py with process_turn() and per-type stub functions",
            "Wire to session_store and context modules",
        ],
        dod=[
            "process_turn dispatches to correct handler for each node type",
            "Unit test exercises every dispatch branch",
        ],
    )),
    ("02_qualification_and_inference.md", task(
        objective="Implement qualification node behavior — collect qualification_keys, run inference rules first.",
        requirements=[
            "On enter: run inference.apply_rules(); for any key already inferred with confidence > 0.85, skip the question",
            "For remaining keys, ask one-at-a-time per pacing constraints",
            "On user answer, write to confirmed tier",
        ],
        steps=[
            "Implement handle_qualify() in node_processor.py",
            "Hook to context.set_tier and inference.apply_rules",
            "Track which keys are still pending in session_state.history",
        ],
        dod=[
            "Test: qualify node with all keys pre-inferred completes in 0 questions",
            "Test: qualify node asks remaining keys one at a time",
        ],
    )),
    ("03_actions_and_contract.md", task(
        objective="Implement execute node behavior — fire actions, validate outputs against contract.",
        requirements=[
            "Each action runs and produces a structured result",
            "On result, validate against the schema referenced by the node (if any)",
            "Failure → emit error Signal, do not transition",
        ],
        steps=[
            "Implement handle_execute() in node_processor.py",
            "Use contract_validator on outputs",
            "Surface action errors as Signal with action_options for retry/abandon",
        ],
        dod=[
            "Test: successful action transitions; failed action emits error signal and holds",
        ],
    )),
    ("04_transitions.md", task(
        objective="Implement transition resolution — gate, approval, fork, close node types.",
        requirements=[
            "gate: evaluates condition, transitions to true_branch or false_branch",
            "approval: emits approval_required Signal, blocks until external resolution",
            "fork: spawns sub-session (deferred per build plan; raise NotImplementedError with TODO)",
            "close: assemble CloseSignal, validate, emit to Atlas",
        ],
        steps=[
            "Implement handle_gate, handle_approval, handle_fork (stub), handle_close",
            "On close, build CloseSignal payload from session_state via dedicated builder",
        ],
        dod=[
            "Test: gate with true condition transitions correctly",
            "Test: close emits valid CloseSignal that passes contract_validator",
        ],
    )),
]

SERVICE_04_RESPONSE = [
    ("01_pacing_constraints.md", task(
        objective="Implement response_composer pacing layer — token budget + question-count constraint.",
        requirements=[
            "Source: doctrine/03_OPTOGON_SPEC.md Section 11 metrics + spec pacing section",
            "Hard cap: 1 question per turn",
            "Soft cap: < 200 tokens per node closed",
            "If composer wants to ask more, log violation and truncate",
        ],
        steps=[
            "Author response_composer.py with compose(node, session, draft) → final_text",
            "Implement question-count enforcement before LLM call",
        ],
        dod=[
            "Composer never returns response with > 1 question mark in non-clarification turn",
            "Logged metric: tokens_used per node",
        ],
    )),
    ("02_llm_call_with_budget.md", task(
        objective="Wire actual LLM call (Claude/local) with strict prompt budget.",
        requirements=[
            "Use anthropic SDK (already in cortex deps)",
            "Prompt template: [system context, current node, qualification keys outstanding, pacing rules]",
            "Pass max_tokens=200 default; configurable per node",
        ],
        steps=[
            "Author llm_call() in response_composer.py",
            "Use ANTHROPIC_API_KEY from env (same as cortex)",
            "Enable prompt caching on system prompt segment",
        ],
        dod=[
            "Test (mocked): call returns within token budget",
            "Test (live, optional): actual API call returns valid response",
        ],
    )),
]

SERVICE_05_SERVER = [
    ("01_fastapi_endpoints.md", task(
        objective="Implement FastAPI endpoints per build plan Phase 2 spec.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 2 endpoints list",
            "POST /session/start, POST /session/{id}/turn, GET /session/{id}, GET /paths, GET /health",
            "All responses JSON; errors return structured ContractError detail",
        ],
        steps=[
            "Author main.py with FastAPI app + 5 routes",
            "Wire to session_store and node_processor",
            "Add CORS middleware allowing inpact origin (:3006)",
        ],
        dod=[
            "All 5 endpoints respond with expected shapes",
            "OpenAPI docs at /docs render",
        ],
    )),
    ("02_health_and_paths.md", task(
        objective="Implement /health (uptime + version) and /paths (lists paths/*.json).",
        requirements=[
            "/health: returns {status: ok, version, uptime_seconds, schemas_loaded: int}",
            "/paths: scans services/optogon/paths/, returns [{id, label, description}]",
        ],
        steps=[
            "Implement health endpoint in main.py",
            "Implement paths endpoint that reads paths/*.json and extracts metadata",
        ],
        dod=[
            "GET /health returns 200 with all fields populated",
            "GET /paths returns at least ship_inpact_lesson",
        ],
    )),
]

SERVICE_06_PATH = [
    ("01_author_ship_inpact_lesson_json.md", task(
        objective="Author services/optogon/paths/ship_inpact_lesson.json — first real path.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Section 5 (table of nodes for this path)",
            "9 nodes: entry, load_skeleton, validate_content, merge, preview, em_dash_check, approve, commit, done",
            "Must validate against OptogonPath.v1.json",
            "Must use ship_inpact_lesson real repo paths (apps/inpact/content/lessons/{N}.md)",
        ],
        steps=[
            "Author the JSON file using _template.json as base",
            "Cross-check qualification_keys per build plan node table",
            "Validate via contract_validator before commit",
        ],
        dod=[
            "Path file exists and validates against OptogonPath.v1.json",
            "GET /paths returns it",
        ],
    )),
    ("02_end_to_end_test.md", task(
        objective="Author tests/test_path_ship_inpact_lesson.py — full path execution test.",
        requirements=[
            "Mock LLM responses; mock filesystem reads/writes",
            "Test must complete the path with status=completed and emit valid CloseSignal",
            "Asserts: questions_asked < 3, completion_rate = 1.0",
        ],
        steps=[
            "Author the test file",
            "Use TestClient from fastapi.testclient",
            "Drive the full path: POST /session/start → loop POST /session/{id}/turn until close",
        ],
        dod=[
            "pytest services/optogon/tests/test_path_ship_inpact_lesson.py passes",
            "CloseSignal payload validates against schema",
        ],
    )),
]

# ---- 003_INTEGRATION -------------------------------------------------------
INTEGRATION_01_ATLAS = [
    ("01_directive_emitter_ts.md", task(
        objective="Add services/delta-kernel/src/atlas/directive.ts — transforms task queue → Directive.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 3a",
            "Function: emitNextDirective(): Directive | null",
            "Reads from existing leverage-scored queue in delta-kernel",
            "Output validates against Directive.v1.json",
        ],
        steps=[
            "Add directive.ts module under src/atlas/",
            "Map current task fields onto Directive shape",
            "Use ajv (or existing schema validator) for runtime validation",
        ],
        dod=[
            "Unit test: emit returns valid Directive for known queue state",
            "Test: empty queue returns null cleanly",
        ],
    )),
    ("02_next_directive_endpoint.md", task(
        objective="Add GET /api/atlas/next-directive endpoint to delta-kernel server.ts.",
        requirements=[
            "Returns Directive JSON or 204 if queue empty",
            "Calls directive.emitNextDirective()",
            "CORS allows cortex origin",
        ],
        steps=[
            "Edit services/delta-kernel/src/api/server.ts",
            "Wire route to directive.ts",
            "Add to OpenAPI surface if delta-kernel has one",
        ],
        dod=[
            "curl localhost:3001/api/atlas/next-directive returns valid Directive or 204",
        ],
    )),
    ("03_schema_validate_on_emit.md", task(
        objective="Enforce Directive.v1.json validation before emit; refuse invalid output.",
        requirements=[
            "If validation fails, log error to delta-kernel and return 500 with error detail",
            "Never emit a Directive that fails validation",
        ],
        steps=[
            "Wrap emitNextDirective output in validator call",
            "On validation failure, log + raise",
        ],
        dod=[
            "Test: corrupted task in queue → 500, not a malformed Directive",
        ],
    )),
]

INTEGRATION_02_CORTEX = [
    ("01_consume_directive.md", task(
        objective="Add services/cortex/src/cortex/ghost_executor/ — consume_directive(directive) → TaskPrompt.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 3b",
            "Validate input against Directive.v1.json",
            "Map Directive → TaskPrompt per Rosetta Contract 4",
            "Output validates against TaskPrompt.v1.json",
        ],
        steps=[
            "Create cortex/ghost_executor/ package",
            "Author consume.py with consume_directive()",
            "Wire to existing cortex planner if it makes sense; otherwise standalone",
        ],
        dod=[
            "Unit test: known Directive maps to known TaskPrompt",
            "Output validates against schema",
        ],
    )),
    ("02_emit_build_output.md", task(
        objective="Add emit_build_output(result) → BuildOutput in ghost_executor.",
        requirements=[
            "Wraps Claude Code execution result",
            "Validates against BuildOutput.v1.json before emitting",
            "Emits Signal to InPACT (completion or error)",
        ],
        steps=[
            "Author emit.py with emit_build_output()",
            "Hook into existing cortex executor return path",
        ],
        dod=[
            "Successful run → BuildOutput status=success + completion Signal",
            "Failed run → status=failed + error Signal with action_options",
        ],
    )),
    ("03_readme_alias.md", task(
        objective="Document in services/cortex/README.md that Cortex plays the Ghost Executor role.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md D6 + Risk Register",
            "Add a section 'Role: Ghost Executor' linking to doctrine/02_ROSETTA_STONE.md Contract 3 & 4",
        ],
        steps=[
            "Edit cortex/README.md",
            "Add the role section near the top",
        ],
        dod=[
            "README mentions Ghost Executor and links to Rosetta",
        ],
    )),
]

INTEGRATION_03_INPACT = [
    ("01_signals_endpoint.md", task(
        objective="Add GET /api/signals to delta-kernel — aggregates Signals from all layers.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 3c",
            "Returns array of Signal objects",
            "Sorts by priority + emitted_at desc",
            "Supports ?since=timestamp filter",
        ],
        steps=[
            "Add signals collection table to delta-kernel SQLite",
            "Add ingest endpoint POST /api/signals/ingest",
            "Add list endpoint GET /api/signals",
        ],
        dod=[
            "curl /api/signals returns valid array",
            "POST /api/signals/ingest with valid Signal stores and is returned by GET",
        ],
    )),
    ("02_today_html_render.md", task(
        objective="Add apps/inpact/js/signals.js + today.html block to render Signals.",
        requirements=[
            "Reuse existing today.html ls-* blocks (per feedback_one_lesson_template.md)",
            "Light theme only (per locked design)",
            "No em dashes in any rendered text (per feedback_no_em_dashes_in_ui.md)",
            "Polls /api/signals every 30s with exponential backoff",
        ],
        steps=[
            "Author signals.js — fetch + render loop",
            "Add signal feed block to today.html using existing classes",
            "Verify in browser via preview_start name='inpact'",
        ],
        dod=[
            "Signals visible in today.html when present",
            "preview_inspect confirms light theme styling",
            "No em dashes in rendered output",
        ],
    )),
    ("03_approval_required_surface.md", task(
        objective="Surface approval_required signals above-the-fold with action buttons.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md Section 5 InPACT Display Rules",
            "approval_required signals always render at top regardless of priority",
            "Each action_option becomes a clickable button",
            "Click POSTs decision back to /api/signals/{id}/resolve",
        ],
        steps=[
            "Extend signals.js with approval rendering",
            "Add /api/signals/{id}/resolve endpoint to delta-kernel",
            "Wire button click → POST → re-fetch",
        ],
        dod=[
            "Approval signal renders with buttons at top",
            "Clicking button removes signal and resolves it",
        ],
    )),
]

INTEGRATION_04_E2E = [
    ("01_trigger_path_from_inpact.md", task(
        objective="Add 'Run path' control to today.html that triggers Optogon path execution.",
        requirements=[
            "Lists paths from GET /paths on Optogon (:3010)",
            "Click → POST /session/start with selected path_id",
            "Returns session_id; track in localStorage",
        ],
        steps=[
            "Add path-runner block to today.html using ls-* classes",
            "Author paths.js to fetch + start sessions",
            "Render running session inline (status from GET /session/{id})",
        ],
        dod=[
            "Click on ship_inpact_lesson starts a session and shows status",
        ],
    )),
    ("02_verify_signal_round_trip.md", task(
        objective="Verify end-to-end: trigger path → Optogon → CloseSignal → Atlas → Signal → today.html.",
        requirements=[
            "All services running: delta-kernel :3001, optogon :3010, inpact :3006",
            "Path completes; CloseSignal posted to /api/atlas/close-signal",
            "Atlas emits completion Signal; today.html renders it",
        ],
        steps=[
            "Run all services",
            "Trigger ship_inpact_lesson from today.html",
            "Walk the path to close",
            "Verify completion Signal appears in today.html within 30s",
        ],
        dod=[
            "Full round trip succeeds without manual intervention",
            "Screenshots saved as proof",
        ],
    )),
]

# ---- 004_CLOSE_LOOP --------------------------------------------------------
CLOSE_01_INGEST = [
    ("01_atlas_close_signal_endpoint.md", task(
        objective="Add POST /api/atlas/close-signal to delta-kernel.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 4",
            "Validates body against CloseSignal.v1.json",
            "Returns 202 on accept; 400 on schema fail",
        ],
        steps=[
            "Add route in delta-kernel server.ts",
            "Wire to close_signal handler module",
        ],
        dod=[
            "Valid CloseSignal POST → 202",
            "Invalid → 400 with structured error",
        ],
    )),
    ("02_queue_update_on_close.md", task(
        objective="On CloseSignal receive: mark task complete, update queue, write decisions to cognitive map.",
        requirements=[
            "Mark task with id matching CloseSignal.path_id (or matching task_id) as completed",
            "Add CloseSignal.decisions_made to long-term cognitive map (cognitive-sensor)",
            "Re-score queue per existing leverage logic",
            "Process unblocked array as advisory hints",
        ],
        steps=[
            "Implement handleCloseSignal() in delta-kernel",
            "Persist decisions via cognitive-sensor write API",
        ],
        dod=[
            "Task moves from queue → completed table",
            "Decisions present in cognitive map after close",
        ],
    )),
]

CLOSE_02_PREFS = [
    ("01_schema_and_sqlite_table.md", task(
        objective="Add user_preferences SQLite table backing UserPreferenceStore.v1.json.",
        requirements=[
            "Source: doctrine/02_ROSETTA_STONE.md Cross-Session User Memory",
            "Table columns: id, user_id, key, value (json), confidence, source, observed_count, last_observed",
            "Single user system for now (user_id literal 'bruke')",
        ],
        steps=[
            "Add migration to delta-kernel storage layer",
            "Add Preference repo module with read/write API",
        ],
        dod=[
            "Table exists; round-trip insert+query succeeds",
            "Schema validation against UserPreferenceStore.v1.json passes",
        ],
    )),
    ("02_writer_from_optogon.md", task(
        objective="Optogon close handler writes context_residue.learned_preferences to Atlas preference store.",
        requirements=[
            "On close, read learned_preferences from CloseSignal",
            "POST each entry to /api/atlas/preferences (new endpoint)",
            "If preference exists with same key, increment observed_count + average confidence",
        ],
        steps=[
            "Add /api/atlas/preferences POST endpoint to delta-kernel",
            "Hook into Optogon close handler to call it",
        ],
        dod=[
            "After path close, new preferences appear in store",
            "Re-running same path increments observed_count",
        ],
    )),
    ("03_reader_in_cortex.md", task(
        objective="Cortex reads preferences when composing TaskPrompt — populate context_bundle.user_preferences.",
        requirements=[
            "GET /api/atlas/preferences reads back the store",
            "Cortex consume_directive populates user_preferences in TaskPrompt from these",
        ],
        steps=[
            "Add /api/atlas/preferences GET endpoint",
            "Edit cortex/ghost_executor/consume.py to fetch + inject",
        ],
        dod=[
            "TaskPrompt example has populated user_preferences after path runs",
        ],
    )),
]

CLOSE_03_VALIDATION = [
    ("01_run_ship_inpact_lesson_twice.md", task(
        objective="Execute ship_inpact_lesson twice and capture metrics for both runs.",
        requirements=[
            "Run 1: cold start (no preferences)",
            "Run 2: after Run 1 close signal processed",
            "Capture: questions_asked, tokens_used, time_to_close per run",
        ],
        steps=[
            "Wipe sessions.db before Run 1",
            "Execute Run 1 end-to-end; record metrics",
            "Execute Run 2 with preference store warm",
        ],
        dod=[
            "Both runs reach status=completed",
            "Metrics captured to a markdown table",
        ],
    )),
    ("02_measure_questions_drop.md", task(
        objective="Verify Run 2 asks measurably fewer questions than Run 1.",
        requirements=[
            "Source: doctrine/04_BUILD_PLAN.md Phase 4 success criterion",
            "Acceptance: Run 2 questions_asked < Run 1 questions_asked by at least 1",
            "If not met, identify which preference failed to apply and iterate",
        ],
        steps=[
            "Compare metrics from previous task",
            "If pass, commit the metrics table to doctrine/05_FEST_PLAN.md as proof",
            "If fail, write findings to a follow-up task and re-run Phase 4",
        ],
        dod=[
            "Documented Run 1 vs Run 2 comparison with verdict",
            "If pass: festival eligible for /999_REVIEW",
        ],
    )),
]

# ---- TASKS table -----------------------------------------------------------
TASKS: dict[str, dict[str, list[tuple[str, dict]]]] = {
    "001_CONTRACTS": {
        "01_optogon_schemas": CONTRACTS_01_OPTOGON,
        "02_rosetta_schemas": CONTRACTS_02_ROSETTA,
        "03_examples": CONTRACTS_03_EXAMPLES,
        "04_validator_script": CONTRACTS_04_VALIDATOR,
    },
    "002_OPTOGON_SERVICE": {
        "01_scaffold": SERVICE_01_SCAFFOLD,
        "02_core_modules": SERVICE_02_CORE,
        "03_node_processor": SERVICE_03_NODE,
        "04_response_composer": SERVICE_04_RESPONSE,
        "05_server": SERVICE_05_SERVER,
        "06_first_path": SERVICE_06_PATH,
    },
    "003_INTEGRATION": {
        "01_atlas_directive": INTEGRATION_01_ATLAS,
        "02_cortex_ghost_executor": INTEGRATION_02_CORTEX,
        "03_inpact_signals": INTEGRATION_03_INPACT,
        "04_end_to_end": INTEGRATION_04_E2E,
    },
    "004_CLOSE_LOOP": {
        "01_close_signal_ingest": CLOSE_01_INGEST,
        "02_preference_store": CLOSE_02_PREFS,
        "03_validation_run": CLOSE_03_VALIDATION,
    },
}


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
TASK_TEMPLATE = """# Task: {title}

## Objective
{objective}

## Requirements
{requirements}

## Implementation Steps
{steps}

## Definition of Done
{dod}
"""


def title_from_filename(fn: str) -> str:
    stem = fn.replace(".md", "")
    parts = stem.split("_", 1)
    if len(parts) == 2 and parts[0].isdigit():
        return parts[1].replace("_", " ").title()
    return stem.replace("_", " ").title()


def render_task(filename: str, content: dict) -> str:
    return TASK_TEMPLATE.format(
        title=title_from_filename(filename),
        objective=content["objective"],
        requirements="\n".join(f"- {r}" for r in content["requirements"]),
        steps="\n".join(f"{i+1}. {s}" for i, s in enumerate(content["steps"])),
        dod="\n".join(f"- [ ] {d}" for d in content["dod"]),
    )


def write_phase(target_root: Path, phase: str, sequences: dict, dry_run: bool) -> int:
    count = 0
    phase_dir = target_root / phase
    if not dry_run:
        phase_dir.mkdir(parents=True, exist_ok=True)
    for seq_name, tasks in sequences.items():
        seq_dir = phase_dir / seq_name
        if not dry_run:
            seq_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in tasks:
            out = seq_dir / filename
            body = render_task(filename, content)
            if dry_run:
                print(f"[DRY] {out}")
                print(body)
                print("---")
            else:
                out.write_text(body, encoding="utf-8")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # doctrine/scripts/.. -> doctrine; ../ -> repo


def resolve_target(target: str, lifecycle: str) -> Path:
    if target == "staging":
        return DEFAULT_REPO_ROOT / "doctrine" / "fest_staging" / "optogon-stack"
    if target == "fest":
        return Path(f"/root/festival-project/festivals/{lifecycle}/optogon-stack")
    return Path(target).resolve()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default="staging", help="staging | fest | <absolute path>")
    ap.add_argument("--lifecycle", default="planning", choices=["planning", "ready", "active", "dungeon"],
                    help="Only used when --target=fest")
    ap.add_argument("--dry-run", action="store_true", help="Print tasks instead of writing files")
    args = ap.parse_args()

    target_root = resolve_target(args.target, args.lifecycle)
    print(f"Target: {target_root}")
    if not args.dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    total = 0
    for phase, sequences in TASKS.items():
        n = write_phase(target_root, phase, sequences, args.dry_run)
        print(f"  {phase}: {n} tasks")
        total += n

    # Empty phases (000_PLAN, 999_REVIEW) get just the directory
    for empty_phase in ["000_PLAN", "999_REVIEW"]:
        d = target_root / empty_phase
        if not args.dry_run:
            d.mkdir(parents=True, exist_ok=True)
            (d / ".keep").touch()

    print(f"\nTotal: {total} task files {'(dry run)' if args.dry_run else 'written'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

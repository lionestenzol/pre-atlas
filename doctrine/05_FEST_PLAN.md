# OPTOGON STACK — FESTIVAL PLAN
*Target system: `fest` CLI in WSL2 Ubuntu at `/root/festival-project`*
*Status 2026-04-18: WSL fully unresponsive (echo / --shutdown / --status all hung). Task bodies authored offline into `doctrine/fest_staging/optogon-stack/`; materializer at `doctrine/scripts/write_fest_tasks.py` can drop them into the fest tree once WSL recovers.*

---

## 1. Festival Identity

| Field | Value |
|:---|:---|
| **Name** | `optogon-stack` |
| **Type** | `implementation` |
| **Goal** | Ship the Optogon stack MVP (contracts → service → integration → close loop) so that a real path (ship_inpact_lesson) runs end-to-end, emitting contracts, and feeds back into Atlas and InPACT |
| **Lifecycle start** | `festivals/planning/` (moves to `ready/` after validation, `active/` at first task start) |

---

## 2. Phase Structure (6 phases)

Four build phases from `04_BUILD_PLAN.md`, bracketed by a `000_PLAN` phase (planning) and a `999_REVIEW` phase (review). That structure is standard fest shape: planning at the front, implementation phases in the middle, review at the end.

| # | Phase | Type | Why this type |
|:---|:---|:---|:---|
| 000 | `000_PLAN` | `planning` | Uses WORKFLOW.md for decisions (D1–D6 from build plan), no sequences |
| 001 | `001_CONTRACTS` | `implementation` | Generates 10 JSON schemas — real code deliverables with quality gates |
| 002 | `002_OPTOGON_SERVICE` | `implementation` | Scaffolds `services/optogon/` with Node Processor, Pacing Composer, etc. |
| 003 | `003_INTEGRATION` | `implementation` | Wires Atlas → Cortex → InPACT against the new contracts |
| 004 | `004_CLOSE_LOOP` | `implementation` | Preference store + second-run learning validation |
| 999 | `999_REVIEW` | `review` | Free-form PHASE_GOAL.md — measure against MVP success metrics |

---

## 3. Sequence + Task Breakdown (implementation phases)

### Phase 001_CONTRACTS

**Goal:** 10 JSON schemas + examples, all validating.

| Seq | Tasks |
|:---|:---|
| `01_optogon_schemas` | `01_optogon_node.md`, `02_optogon_path.md`, `03_optogon_session_state.md` |
| `02_rosetta_schemas` | `01_context_package.md`, `02_close_signal.md`, `03_directive.md`, `04_task_prompt.md`, `05_build_output.md`, `06_signal.md`, `07_user_preference_store.md` |
| `03_examples` | `01_author_one_example_per_schema.md`, `02_validate_all_examples.md` |
| `04_validator_script` | `01_validator_py.md` (loads all schemas + examples, asserts validity) |

Parallelism note: same-numbered task files run in parallel per fest rules. Tasks inside `01_optogon_schemas` can all share number `01_…`/`02_…`/`03_…` if you want sequential authoring, or be renumbered `01_…` three times for parallel execution. **Recommendation: sequential** — schemas reference each other.

### Phase 002_OPTOGON_SERVICE

**Goal:** `services/optogon/` FastAPI on :3010, first path runs.

| Seq | Tasks |
|:---|:---|
| `01_scaffold` | `01_pyproject_and_start_bat.md`, `02_dir_tree.md`, `03_launch_json_entry.md` |
| `02_core_modules` | `01_session_store.md`, `02_context_hierarchy.md`, `03_inference_rules.md`, `04_contract_validator.md` |
| `03_node_processor` | `01_processor_skeleton.md`, `02_qualification_and_inference.md`, `03_actions_and_contract.md`, `04_transitions.md` |
| `04_response_composer` | `01_pacing_constraints.md`, `02_llm_call_with_budget.md` |
| `05_server` | `01_fastapi_endpoints.md`, `02_health_and_paths.md` |
| `06_first_path` | `01_author_ship_inpact_lesson_json.md`, `02_end_to_end_test.md` |

### Phase 003_INTEGRATION

**Goal:** Atlas speaks Directive, Cortex plays Ghost Executor, InPACT renders Signals.

| Seq | Tasks |
|:---|:---|
| `01_atlas_directive` | `01_directive_emitter_ts.md`, `02_next_directive_endpoint.md`, `03_schema_validate_on_emit.md` |
| `02_cortex_ghost_executor` | `01_consume_directive.md`, `02_emit_build_output.md`, `03_readme_alias.md` |
| `03_inpact_signals` | `01_signals_endpoint.md`, `02_today_html_render.md`, `03_approval_required_surface.md` |
| `04_end_to_end` | `01_trigger_path_from_inpact.md`, `02_verify_signal_round_trip.md` |

### Phase 004_CLOSE_LOOP

**Goal:** Second run of same path asks fewer questions.

| Seq | Tasks |
|:---|:---|
| `01_close_signal_ingest` | `01_atlas_close_signal_endpoint.md`, `02_queue_update_on_close.md` |
| `02_preference_store` | `01_schema_and_sqlite_table.md`, `02_writer_from_optogon.md`, `03_reader_in_cortex.md` |
| `03_validation_run` | `01_run_ship_inpact_lesson_twice.md`, `02_measure_questions_drop.md` |

---

## 4. Quality Gates (auto-appended by `fest gates apply`)

Every implementation sequence gets the standard 4-gate suffix appended:

1. `NN_testing` — verify implementation works
2. `NN_review` — code review
3. `NN_iterate` — address findings
4. `NN_fest_commit` — commit with task reference

These are appended by `fest gates apply --approve`, not authored manually.

---

## 5. Exact Commands — Next Session Resume Script

Copy-paste this block when WSL Ubuntu is responsive. It creates the full festival scaffold. Task file BODIES are filled in a second pass because they need markdown content — the memory file flags that Python writes them cleanly.

```bash
# 5.1 — Create festival
wsl -d Ubuntu -- bash -c "cd /root/festival-project && fest create festival --name 'optogon-stack' --type implementation --goal 'Ship the Optogon stack MVP so that ship_inpact_lesson path runs end-to-end, emitting Rosetta Stone contracts, and feeds back into Atlas and InPACT'"

# 5.2 — Planning phase (no sequences)
wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack && fest create phase --name '000_PLAN' --type planning"

# 5.3 — Implementation phases
for P in 001_CONTRACTS 002_OPTOGON_SERVICE 003_INTEGRATION 004_CLOSE_LOOP; do
  wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack && fest create phase --name '$P' --type implementation"
done

# 5.4 — Review phase
wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack && fest create phase --name '999_REVIEW' --type review"

# 5.5 — 001_CONTRACTS sequences
cd_contracts() { wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack/001_CONTRACTS && $1"; }
cd_contracts "fest create sequence --name '01_optogon_schemas'"
cd_contracts "fest create sequence --name '02_rosetta_schemas'"
cd_contracts "fest create sequence --name '03_examples'"
cd_contracts "fest create sequence --name '04_validator_script'"

# 5.6 — 002_OPTOGON_SERVICE sequences
cd_opt() { wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack/002_OPTOGON_SERVICE && $1"; }
for S in 01_scaffold 02_core_modules 03_node_processor 04_response_composer 05_server 06_first_path; do
  cd_opt "fest create sequence --name '$S'"
done

# 5.7 — 003_INTEGRATION sequences
cd_int() { wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack/003_INTEGRATION && $1"; }
for S in 01_atlas_directive 02_cortex_ghost_executor 03_inpact_signals 04_end_to_end; do
  cd_int "fest create sequence --name '$S'"
done

# 5.8 — 004_CLOSE_LOOP sequences
cd_close() { wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack/004_CLOSE_LOOP && $1"; }
for S in 01_close_signal_ingest 02_preference_store 03_validation_run; do
  cd_close "fest create sequence --name '$S'"
done

# 5.9 — Task files: create with Python (avoids bash quote mangling)
# See section 6 below — Python script writes all task bodies from the task table.

# 5.10 — Apply quality gates to all implementation sequences
wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack && fest gates apply --approve"

# 5.11 — Validate
wsl -d Ubuntu -- bash -c "cd /root/festival-project/festivals/planning/optogon-stack && fest validate"

# 5.12 — Move to ready when green
wsl -d Ubuntu -- bash -c "cd /root/festival-project && mv festivals/planning/optogon-stack festivals/ready/"
```

---

## 6. Task File Content — DONE (authored offline)

**Status:** Authored 2026-04-18 (session 2). 48 task files across 4 implementation phases, plus empty `000_PLAN/` and `999_REVIEW/` directories.

**Source of truth:** `doctrine/scripts/write_fest_tasks.py` (single Python module with all task bodies as data structures). Editing a staged `.md` file directly is pointless — re-running the script overwrites it. Edit the script.

**Staged output:** `doctrine/fest_staging/optogon-stack/` mirrors the festival shape:
```
doctrine/fest_staging/optogon-stack/
├── 000_PLAN/ (empty, planning phase)
├── 001_CONTRACTS/         (13 tasks across 4 sequences)
├── 002_OPTOGON_SERVICE/   (17 tasks across 6 sequences)
├── 003_INTEGRATION/       (11 tasks across 4 sequences)
├── 004_CLOSE_LOOP/        (7 tasks across 3 sequences)
└── 999_REVIEW/ (empty, review phase)
```

**Task template used:**
```
# Task: <Name>
## Objective
## Requirements
## Implementation Steps
## Definition of Done
```

**Content sources (per task):**
- Objective → 1-line summary from `04_BUILD_PLAN.md` deliverable list
- Requirements → spec excerpts from `03_OPTOGON_SPEC.md` (for 002) or `02_ROSETTA_STONE.md` (for 001/003/004)
- Implementation Steps → lifted from build plan phase detail sections
- Definition of Done → file paths + `fest validate` clean + schema/test pass criteria

**Materializer usage:**
```bash
# Regenerate staging (default)
python doctrine/scripts/write_fest_tasks.py

# Drop into live fest tree after `fest create festival/phase/sequence` has scaffolded dirs
python doctrine/scripts/write_fest_tasks.py --target fest --lifecycle planning

# Inspect without writing
python doctrine/scripts/write_fest_tasks.py --dry-run
```

**Quality gates are NOT authored** — they are appended by `fest gates apply --approve` (4 gates × 15 sequences = 60 gate task files, all auto-generated).

---

## 7. Definition of Done — This Festival

The festival is complete when ALL are true:

- [ ] All 10 JSON schemas exist and self-validate (001)
- [ ] `services/optogon/` responds on :3010, `ship_inpact_lesson` path runs end-to-end (002)
- [ ] Atlas emits a valid Directive; Cortex consumes it; today.html renders a Signal (003)
- [ ] Running the same path twice asks measurably fewer questions the second time (004)
- [ ] MVP success metrics from spec Section 11 hit: <3 questions/close, >0.85 inference accuracy, >0.75 completion rate, <200 tokens/node
- [ ] Festival moved to `festivals/dungeon/` with `fest commit` trail

---

## 8. Next Session Entry Point

First thing next session:

1. Try WSL: `wsl -d Ubuntu -- echo ok` — if it returns fast, WSL is healthy
2. If WSL still hangs: from admin PowerShell run `Restart-Service LxssManager` or reboot Windows. `wsl --shutdown` alone was not sufficient on 2026-04-18.
3. Once healthy, paste the command block from Section 5 above to scaffold festival + phases + sequences
4. Materialize task bodies in one command:
   ```bash
   python doctrine/scripts/write_fest_tasks.py --target fest --lifecycle planning
   ```
5. Apply quality gates: `fest gates apply --approve`
6. `fest validate` and address findings
7. Move to ready: `mv festivals/planning/optogon-stack festivals/ready/`
8. `fest next` — first task should be `001_CONTRACTS/01_optogon_schemas/01_optogon_node.md`

---

## 9. Deferred / Known Risks

- **Task body authoring scale**: ~40+ task files. Batch via Python, not one-by-one.
- **Parallelism numbering**: fest rule says same-numbered items run in parallel. Schemas should stay sequential (renumber `01_…`, `02_…`, `03_…`). Scaffolding tasks can run parallel (same number).
- **Quality gates cost**: 4 gates × 15 implementation sequences = 60 extra task files. `fest gates apply --approve` handles creation; don't hand-author.
- **WSL hanging behavior**: track whether this happens again. If chronic, consider fest in native Windows or ditch fest for this festival and track via TodoWrite only.

---

*This plan is the festival-shaped projection of `04_BUILD_PLAN.md`. The build plan is the source of truth for what to build. This doc is the source of truth for how to structure it as fest work.*

# OPTOGON AUDIT BUNDLE

> One document. Everything an outside reviewer needs to audit whether the
> implementation matches the original plan. Bruke planned Optogon in a prior
> session. A different Claude Code instance built it. This bundle lets you
> compare intent (doctrine) vs. reality (code) without needing file access.

---

## HOW TO USE THIS DOCUMENT

1. Read the **Verification Brief** section immediately below.
2. Read the 5 doctrine documents to absorb intent.
3. Read the code excerpts to compare against intent.
4. Return findings in the format the Brief asks for.

---

## VERIFICATION BRIEF

Bruke wants to know whether the Optogon implementation matches his original
plan, captured in the doctrine below.

### Commit chain (all work landed on main)

```
d6938ac feat(optogon): commit_a_file path with real side effects - first live path
d5b82cf feat(optogon-stack): Phase 4 close-loop + preference store - PATH COMPLETE
306e6f7 feat(optogon-stack): Phase 3 integration - Atlas emits, Cortex consumes, InPACT renders
9a7b299 feat(optogon): scaffold service on :3010 - Phase 2 of build plan
065a4a6 feat(contracts): optogon stack schemas v1 - 10 schemas, 10 examples, validator
bf5417d docs(doctrine): optogon stack â€” doctrine, contracts, spec, build plan, fest staging
d707fce docs: add scorecard framework (sales-floor reference version)
4c45676 feat: full system state sync â€” UASC bridge, auto_actor, CycleBoard, dead code cleanup
b43837e fix: execution claim TTL uses job timeout instead of hardcoded 5min
1e175d2 feat: UASC executor service â€” deterministic command execution engine
```

### Test state

- 33/33 optogon tests pass
- 6/6 cortex ghost_executor tests pass
- delta-kernel tsc clean
- 10/10 schemas validate examples (contracts/validate.py)

### Decisions made during build (from 04_BUILD_PLAN.md)

| # | Decision | Chosen |
|---|----------|--------|
| D1 | Optogon language | Python |
| D2 | Optogon port | 3010 |
| D3 | First real path | ship_inpact_lesson (but stubbed) AND commit_a_file (real) |
| D4 | Path JSONs location | services/optogon/paths/ |
| D5 | Schemas location | contracts/schemas/ |
| D6 | Cortex rename? | No; documented as Ghost Executor role via alias |

### What actually works end-to-end (verified)

- All 6 node types dispatch (fork raises NotImplementedError; explicit scope)
- Context hierarchy `confirmed > user > inferred > system` enforced
- Pacing: max 1 question per turn; token budget per node
- Session state persists to SQLite, validates against OptogonSessionState.v1
- Atlas GET /api/atlas/next-directive emits valid Directive.v1 or 204
- Cortex consume_directive / emit_build_output validate against schemas
- InPACT renders approval_required + urgent signals; click-to-resolve verified
- Close loop: Optogon -> delta-kernel preference store; next session pre-loads.
  LIVE PROOF: ran ship_inpact_lesson twice, run 1 taught ui_theme=light,
  run 2 omitted it from initial_context, it was auto-injected from
  preferences, path completed with 0 questions.
- commit_a_file path: real git_commit handler with guards (refuses if other
  files staged, explicit-path `git add`, verifies staging before committing).
  4 e2e tests against tmp git repos prove commits actually land.

### What is stubbed / deferred

1. `ship_inpact_lesson` execute nodes (load_skeleton, merge, preview, commit)
   are stubs. `apps/inpact/content/lessons/` does not exist; wiring real
   handlers requires the inPACT curriculum infrastructure first (separate lane).
2. LLM call in `response_composer.py` returns a deterministic stub unless
   ANTHROPIC_API_KEY is set. No live LLM testing performed.
3. Signals store in delta-kernel is in-memory (max 500 ring buffer).
4. Fork nodes raise NotImplementedError (per spec Section 4 deferral).
5. Site Pull integration is zero (spec calls it external for MVP).
6. Fest festival was never materialized — WSL Ubuntu was unresponsive across
   both sessions. 48 task bodies staged in `doctrine/fest_staging/` plus a
   Python materializer.
7. Learning Layer (spec §6) deferred per build plan §4.
8. Cross-layer Interrupt Protocol documented but not coded.

### Audit questions - please answer these

1. Do the 10 schemas faithfully implement the contracts in 02_ROSETTA_STONE.md?
   Flag any missing/renamed field or divergent enum.
2. Does node_processor.py match the behavior described in 03_OPTOGON_SPEC.md
   Section 14? Specifically the "qualify first, infer second, ask last" order.
3. Does the pacing layer enforce what the spec's Section 10 says (strict
   constraints, not soft hints)?
4. Are the deferred items above the RIGHT ones to defer? Or did something
   get stubbed that Bruke considered core?
5. Does commit_a_file feel like the "closer" behavior described in 01_SEED.md,
   or is it too close to a generic workflow engine?
6. Where does implementation language / architecture deviate from the plan
   in ways a non-code reader wouldn't notice?

### Report format

For each finding, tag with one of:
  - **BLOCKING** — violates core intent
  - **DEVIATION** — changes a decision without explicit flag
  - **OK-DEFERRED** — correctly deferred per build plan
  - **OK** — matches intent

Target length: under 500 words. Prioritize BLOCKING/DEVIATION findings.

---


## DOCTRINE 01 - SEED (vision + moat)

*Source: `doctrine/01_SEED.md`*

# SEED DOCUMENT
## The Full Stack — Discovery, Doctrine, and Build Spec
*Generated from founding conversation — April 2026*

---

## PART 1 — CONVERSATION ITINERARY
*What happened in this session, in order*

1. **Trajectory audit** — Started with a review of the builder's pattern: deep architectural thinking, multiple simultaneous projects, solo execution, building toward a platform.

2. **Correction** — Builder corrected the frame. He has shipped. Site Pull is live on NPM. The pattern isn't stalled — it's compounding.

3. **Site Pull revealed** — What started as a clone tool is actually a context extraction engine. Its core value: lets AI understand infrastructure without reading every line of code. Solves the context window burn problem for solo builders.

4. **Solo builder logic** — Builder articulated the deliberate strategy: build the muscles you don't have, come to collaborators with value not asks, hand off only what you don't want to develop.

5. **Recursive system recognized** — Everything connects. Site Pull feeds Atlas feeds InPACT feeds the execution engine. Not ten projects — one system revealing itself from ten angles.

6. **VirtualStudio closure path** — Identified site pull + existing prototype + PDF spec + Firebase/GitHub as a clean assembly path to ship VirtualStudio.

7. **Optogon named** — The markdown skills and tools layer was named Optogon in this session. Previously unnamed, now a product.

8. **Optogon doctrine developed** — Full governing philosophy articulated: prepared paths, execution tools, burden removal, pacing logic, completion orientation. The closer model from sales encoded into architecture.

9. **Full stack articulated** — Site Pull + Optogon + Atlas + InPACT + Ghost Executor named and positioned as a coherent system.

10. **Platform company vision** — Recognized that together the stack is not competing with Notion, Copilot, or LangChain. It is the layer underneath all of them.

11. **Bootstrap MVP scoped** — Full stack MVP estimated at 3 hours using existing components. Not a roadmap — a session.

12. **Moat identified** — The code is not the moat. The doctrine is. The closer model baked into Optogon. The leverage logic in Atlas. The interval methodology in InPACT. Built from real pressure, not theory.

13. **Discovery moment** — The founding doctrine of Optogon was discovered and articulated for the first time in this conversation. This document is the artifact.

---

## PART 2 — CORE PHILOSOPHY

### The Governing Principle
Most AI systems are conversational. They ask too much, explain too much, drift too much, and push orchestration work back onto the user.

This stack solves that by giving AI prepared execution structure: proven paths, burden-removal behaviors, deterministic tools, pacing logic, and completion-oriented routing.

**The result: an agent that feels natural on the surface but is quietly driving the work toward done underneath.**

### The Mental Model
Raw AI is a rookie rep.
This stack is the loaded structure that makes it perform like a trained closer.

Not a smart talker. A structured finisher.

### The Optical System Metaphor
- **Glasses** — lets you see clearly what you're working with
- **Telescope** — lets you see what's far away (future state, architecture)
- **Microscope** — lets you see deep inside (code, infrastructure, patterns)

The stack is the optical layer for AI-assisted development.

### Product Laws
1. Do not start from zero if the path is already known.
2. Do not ask what can be safely inferred.
3. Do not explain when the blocker is operational and can be removed.
4. Do not make the user carry work the system can carry.
5. Do not let conversational drift break execution continuity.
6. Do not overload the user just because the system has more to say.
7. Stay patient as long as signal is still live. Exit when the path is dead.
8. Surface should feel natural. Backend should stay locked.

### The North Star
**The user should experience conversation. The system should execute a close.**

---

## PART 3 — THE FULL STACK

### Overview
```
Site Pull     →    Optogon     →    Atlas     →    Ghost Executor    →    InPACT
   Eyes            Brain Stem        Mind            Autonomy Layer        Hands
 Ingestion      Execution Arch    Prioritization    Directive Bridge    Human Layer
```

Read bottom to top: productivity system for humans.
Read top to bottom: autonomous development platform.
Read as whole: an operating system for human and AI execution sharing the same engine.

---

### LAYER 1 — SITE PULL
**Role:** Eyes. Ingestion and mapping layer.

**What it does:**
- Pulls structure from any website, local server, or infrastructure
- Maps ports, routes, components without reading raw code line by line
- Compresses infrastructure into AI-readable context
- Works on external sites (clone/template) and internal projects (onboarding layer)

**Key insight:** Solves the context window burn problem. Instead of feeding an entire codebase into context, Site Pull produces a structured map that any AI can navigate.

**Current status:** Shipped. Live on NPM.

**Primary use cases:**
1. Infrastructure reader for your own projects — feeds Claude Code without manual explanation
2. Website cloner — creates local offline template versions
3. Onboarding layer — lets AI understand multi-port projects from the front end shell
4. Context compression — reduces token cost of understanding complex systems

**Platform compatibility:** AI-agnostic. Works with Claude Code, Codex, and any LLM-based coding tool.

**Next test:** Run against own multi-port infrastructure to consolidate shells into one readable context object.

---

### LAYER 2 — OPTOGON
**Role:** Brain stem. Deterministic execution architecture.

**One sentence:** Optogon is the control layer that turns AI from a talker into a closer.

**Technical definition:** A layered execution architecture for AI that combines pathing, deterministic tools, contracts, pacing, and learned workflow structure to reduce drift, reduce token waste, and increase completion reliability.

**What it is NOT:**
- Not just prompting
- Not just markdown
- Not just memory
- Not just a tool registry
- Not just a workflow engine
- Not just a chatbot wrapper
- Not just a decision tree
- Not just an agent framework

All of those are pieces. Optogon is the loaded stack around execution.

**What it actually does:**
1. **Prepares the path** — gives AI known-good routes, branches, and next moves before the interaction begins
2. **Qualifies fast** — identifies user type, request type, and routes accordingly
3. **Preserves momentum** — avoids unnecessary questions, explanation, and branching
4. **Removes burden** — once the system has enough signal, it stops making the user do all the work
5. **Executes in parallel** — advances the task while conversation is happening

**Architecture layers:**

| Layer | Purpose | Examples |
|-------|---------|---------|
| Path Layer | Known-good routes | Entry points, qualification nodes, branch logic, objection patterns, close states |
| Execution Layer | Actual work | Tool calls, code execution, retrieval, transformation, validation, action sequencing |
| Contract Layer | Trustworthy output | Schemas, validators, error behavior, completion criteria, side-effect rules |
| Pacing Layer | Felt experience | What to ask now vs later, when to simplify, when to push next action |
| Burden-Removal Layer | Absorb work for user | Safe defaults, auto-filled fields, hidden unnecessary options, background preparation |
| Learning Layer | Sharpen over time | Successful paths, common drop-offs, compression of repeated conversations into reusable routes |

**Origin of the model:** The closer framework comes from the builder's background in door-to-door and telecom sales. A trained closer doesn't improvise — they have prepared paths, qualification logic, objection handling, and completion orientation built in. Optogon encodes that into AI architecture. This is the moat.

**Current status:** Doctrine complete. MVP buildable from markdown files and schema definitions.

---

### LAYER 3 — ATLAS
**Role:** Mind. Cognitive prioritization and agenda layer.

**What it does:**
- Ingests personal history, messages, project data
- Scores leverage across active work
- Produces a prioritized execution queue
- Sets the agenda for what gets worked on next

**Technical components (full vision):**
- MiniLM embeddings
- UMAP/HDBSCAN clustering
- 8 specialized agents (Excavator, Deduplicator, Classifier, Orchestrator, Reporter, Conversation Classifier, Daily Governor, Weekly Governor)
- Cognitive Atlas visualization
- Leverage scoring
- Tiered execution queue

**MVP version:**
- Notion or Obsidian as data layer
- Single Python scoring script
- Outputs prioritized project list
- Feeds Ghost Executor

**Current status:** Full architecture designed. MVP scoped to one Python script + existing vector DB.

---

### LAYER 4 — GHOST EXECUTOR
**Role:** Autonomy layer. Directive bridge between Atlas and Claude Code.

**What it does:**
- Reads Atlas output (prioritized queue)
- Formats directives into structured Claude Code prompts
- Executes autonomously without requiring manual initiation for each task
- Bridges the gap between deciding and building

**MVP version:**
- Single Python script
- Reads Atlas output
- Formats as Claude Code directive
- Fires the task

**Current status:** Concept defined. MVP is one script.

---

### LAYER 5 — INPACT
**Role:** Hands. Human-facing productivity and execution layer.

**What it does:**
- Surfaces Atlas priorities to the user
- Provides planning interface (Today Dashboard)
- Tracks execution through the day
- Closes the human loop — shows what happened, what's next, what needs a decision

**Methodology origin:** Binder/interval system from direct sales management. The human layer runs on the same engine as the AI layers.

**Product tiers:**
1. Free Today tool — plan and execute daily
2. Core journal product — paid
3. Coaching tier — future

**MVP version:**
- Single page web app
- Firebase backend
- Shows today's top priorities from Atlas
- Input for planning and execution tracking

**Current status:** Methodology complete. Landing funnel built. Free tool and paid system in development.

---

## PART 4 — VIRTUALSTUDIO CLOSURE PATH
*Immediate ship opportunity using the full stack*

**What it is:** AI identity photography service. Generates professional portrait bundles from existing identity logic.

**Assembly path (not a build from scratch):**
1. Feed existing PDF spec into Claude Code session — full product context loaded
2. Run Site Pull against existing prototype — maps infrastructure without reading code
3. Use Site Pull template to create local offline version
4. Adapt prototype to current plan
5. Deploy to Firebase via GitHub
6. Google AI Studio provides AI backend

**Status:** All components exist. This is an assembly job. Estimated time: one focused session.

---

## PART 5 — MVP BUILD SPEC
*Full stack from scratch using existing components*

**Estimated time: 3 hours with Claude Code**

### Session Plan

**Hour 1 — Foundation**
- Define 5-10 Optogon skill files in markdown (inputs, outputs, execution steps)
- Install Site Pull from NPM
- Write Atlas v0.1 scoring script in Python (reads projects, outputs prioritized list)

**Hour 2 — Bridge and Interface**
- Write Ghost Executor v0.1 (reads Atlas output, formats Claude Code directive)
- Build InPACT Today Dashboard (single page, Firebase backend, priority display + execution input)

**Hour 3 — Connect and Validate**
- Run Site Pull against own infrastructure
- Feed output into Claude Code session
- Validate Optogon skills load correctly into context
- Test Atlas → Ghost Executor → Claude Code handoff
- Confirm InPACT surfaces correctly

### Infrastructure Dependencies
| Component | Stack |
|-----------|-------|
| Execution | Claude API |
| Backend | Firebase |
| Deployment | GitHub |
| Package distribution | NPM |
| Vector storage | Chroma or Pinecone |
| AI backend | Google AI Studio |
| Skills/tools | Markdown files |

### What you must own
- Site Pull ingestion logic
- Optogon path and execution doctrine
- Atlas leverage scoring logic
- InPACT interval methodology

### What you can use as commodity
- Firebase, GitHub, Claude API, vector storage, deployment infrastructure

---

## PART 6 — THE MOAT

The code is not the moat.

**What is:**
- The closer model inside Optogon — came from years of real sales floor experience
- The leverage scoring logic inside Atlas — calibrated to real cognitive patterns
- The interval methodology inside InPACT — pressure-tested from direct sales management
- The insight that site pull is context compression, not just cloning

Someone else could assemble the same components in 3 hours. They would produce a generic agent orchestration framework with no doctrine underneath it — which already exists and which nobody is using at scale.

The doctrine is what makes it work. The doctrine took years to produce. It is not in any repository. It is in the builder.

---

## PART 7 — POSITIONING

**What this is not:**
- Not a productivity app
- Not an AI assistant
- Not competing with Notion, Copilot, or LangChain

**What this is:**
The layer underneath all of them.

An execution infrastructure that treats human intelligence and artificial intelligence as complementary layers of the same operating system.

**Market position:**
Most tooling is built top-down by teams optimizing for general use cases. This stack is built bottom-up, from real friction, by someone who uses AI for complex solo development daily. That is different knowledge baked into the architecture.

**One paragraph thesis:**
Most AI systems are conversational. They ask too much, explain too much, drift too much, and push orchestration work back onto the user. This stack solves that by giving AI prepared execution structure: proven conversational paths, burden-removal behaviors, deterministic tools, pacing logic, and completion-oriented routing. The result is an agent that feels natural on the surface but is quietly driving the work toward done underneath.

---

## PART 8 — WHAT TO BUILD FIRST

Do not build everything Optogon could be. Build the minimum version that proves the thesis.

**Four things needed:**

1. A way to define a path — structured flow with branches and completion states (not just a prompt)
2. A way to attach executable actions to nodes — so the system does work while conversation happens
3. A way to validate output and state transitions — so behavior is predictable not just felt
4. A way to carry forward likely next steps without asking — proves burden removal and conversational compression

That is enough to prove the core idea.

---

*This document was produced in a single founding conversation. The doctrine did not exist in written form before this session. Everything here emerged from real building pressure, not theory. Treat it as a living spec — the center holds, the edges will evolve.*


## DOCTRINE 02 - ROSETTA STONE (interlayer contracts)

*Source: `doctrine/02_ROSETTA_STONE.md`*

# THE ROSETTA STONE
## Interlayer Data Contracts — Full Stack
*Site Pull → Optogon → Atlas → Ghost Executor → InPACT*

---

## Overview

This document defines the data contracts between every layer of the stack. Each contract specifies what one layer outputs, what the next layer expects to receive, and what happens at the boundary between them.

These contracts are the connective tissue of the system. The layers can evolve independently as long as the contracts hold.

---

## The Stack at a Glance

```
SITE PULL
    ↓  [Context Package]
OPTOGON
    ↓  [Close Signal]
ATLAS
    ↓  [Directive]
GHOST EXECUTOR
    ↓  [Task Prompt]
CLAUDE CODE
    ↓  [Build Output]
INPACT  ←————————————————— (receives signals from all layers)
```

---

## CONTRACT 1: Site Pull → Optogon

### Purpose
Site Pull maps infrastructure and delivers a context package that Optogon uses to understand the environment before execution begins. This eliminates the need for Optogon to discover the environment through conversation.

### What Site Pull Produces

```json
{
  "context_package": {
    "id": "string",
    "source": "url | localhost | filesystem",
    "captured_at": "timestamp",

    "structure_map": {
      "entry_points": ["string"],
      "routes": [
        {
          "path": "string",
          "method": "GET | POST | PUT | DELETE | WS",
          "params": ["string"],
          "inferred_purpose": "string"
        }
      ],
      "components": [
        {
          "name": "string",
          "type": "page | service | api | worker | store",
          "dependencies": ["string"],
          "inferred_purpose": "string"
        }
      ]
    },

    "dependency_graph": {
      "nodes": [
        {
          "id": "string",
          "type": "internal | external | package",
          "name": "string"
        }
      ],
      "edges": [
        {
          "from": "string",
          "to": "string",
          "relationship": "imports | calls | extends | consumes"
        }
      ]
    },

    "action_inventory": [
      {
        "id": "string",
        "label": "string",
        "type": "api_call | function | event | form_submit",
        "inputs": ["string"],
        "outputs": ["string"],
        "risk_tier": "low | medium | high",
        "reversible": true
      }
    ],

    "inferred_state": {
      "auth_required": true,
      "data_stores": ["string"],
      "environment": "dev | staging | production",
      "tech_stack": ["string"]
    },

    "token_count": 0,
    "compression_ratio": 0.0
  }
}
```

### What Optogon Expects on Receive

Optogon loads the context package into session state before the first node fires. It uses:

- `structure_map` → to validate that action nodes reference real endpoints
- `action_inventory` → to auto-populate available actions in execute nodes
- `dependency_graph` → to understand blast radius of high-risk actions
- `inferred_state` → to pre-fill system context tier in session state

### Contract Rules

1. Site Pull must always output a `context_package` with at minimum: `entry_points`, `routes`, and `action_inventory`.
2. If a source is unavailable, Site Pull emits a `partial_context_package` with a `coverage_score` between 0 and 1.
3. Optogon must not fail on a partial package — it degrades gracefully, treating unknown actions as `risk_tier: high` by default.
4. Token count must be included so Optogon can budget context window usage.

---

## CONTRACT 2: Optogon → Atlas

### Purpose
When Optogon closes a path, it emits a close signal that Atlas uses to update its cognitive map, mark tasks complete, and re-score the execution queue.

### What Optogon Produces on Path Close

```json
{
  "close_signal": {
    "id": "string",
    "session_id": "string",
    "path_id": "string",
    "closed_at": "timestamp",
    "status": "completed | abandoned | failed | forked",

    "deliverables": [
      {
        "type": "file | url | confirmation | data | decision",
        "label": "string",
        "value": "any",
        "location": "string | null"
      }
    ],

    "session_summary": {
      "total_tokens": 0,
      "total_questions_asked": 0,
      "total_inferences_made": 0,
      "inference_accuracy": 0.0,
      "nodes_closed": 0,
      "nodes_total": 0,
      "time_to_close_seconds": 0,
      "path_completion_rate": 0.0
    },

    "decisions_made": [
      {
        "key": "string",
        "value": "any",
        "source": "user | inferred | system",
        "node_id": "string"
      }
    ],

    "unblocked": [
      {
        "task_id": "string",
        "reason": "string"
      }
    ],

    "context_residue": {
      "confirmed": {},
      "learned_preferences": {}
    },

    "interrupt_log": [
      {
        "triggered_at": "timestamp",
        "reason": "string",
        "resolution": "resumed | abandoned | forked"
      }
    ]
  }
}
```

### What Atlas Does on Receive

Atlas processes the close signal to:

- Mark the corresponding task complete in the execution queue
- Add `decisions_made` to the long-term cognitive map
- Add `learned_preferences` to the cross-session user preference store
- Unlock tasks listed in `unblocked`
- Re-score leverage across the queue
- Log session metrics for path optimization

### Contract Rules

1. Optogon must emit a close signal on every terminal state — including `abandoned` and `failed`.
2. `context_residue.learned_preferences` is Atlas's primary input for building cross-session user memory. Optogon must populate it when a user explicitly states a preference or when a preference is inferred with confidence > 0.85.
3. Atlas must not re-queue a task that has a `completed` close signal with valid deliverables.
4. `unblocked` is advisory — Atlas re-scores independently but uses it as a strong signal.

---

## CONTRACT 3: Atlas → Ghost Executor

### Purpose
Atlas selects the highest-leverage task from the execution queue and emits a directive that Ghost Executor can fire without ambiguity.

### What Atlas Produces

```json
{
  "directive": {
    "id": "string",
    "issued_at": "timestamp",
    "priority_tier": "critical | high | medium | low",
    "leverage_score": 0.0,

    "task": {
      "id": "string",
      "label": "string",
      "description": "string",
      "type": "build | fix | research | review | deploy | configure",
      "estimated_complexity": "trivial | simple | moderate | complex",
      "success_criteria": ["string"],
      "constraints": ["string"]
    },

    "context_bundle": {
      "project_id": "string",
      "relevant_files": ["string"],
      "relevant_decisions": [
        {
          "key": "string",
          "value": "any",
          "source": "string",
          "made_at": "timestamp"
        }
      ],
      "user_preferences": {},
      "prior_attempts": [
        {
          "attempt_id": "string",
          "outcome": "string",
          "lessons": ["string"]
        }
      ],
      "site_pull_context_id": "string | null"
    },

    "execution": {
      "target_path_id": "string | null",
      "target_agent": "claude_code | optogon | human",
      "autonomy_level": "full | supervised | approval_required",
      "timeout_seconds": 0,
      "fallback": "escalate_to_human | retry | skip"
    },

    "interrupt_policy": {
      "interruptible": true,
      "interrupt_threshold": "critical_only | high_and_above | any",
      "resume_on_interrupt": true
    }
  }
}
```

### What Ghost Executor Does on Receive

Ghost Executor validates the directive and formats it for the target agent. It:

- Checks `autonomy_level` — if `approval_required`, surfaces to InPACT before firing
- Loads `site_pull_context_id` if present and attaches context package
- Formats the task prompt for the target agent
- Sets interrupt listeners based on `interrupt_policy`
- Logs execution start to InPACT

### Contract Rules

1. Atlas must never emit a directive with an empty `success_criteria`. Ghost Executor needs a definition of done.
2. `autonomy_level: approval_required` always routes through InPACT before execution. Ghost Executor must not bypass this.
3. `target_path_id` is optional — if present, Ghost Executor loads that Optogon path. If absent, Ghost Executor composes a direct prompt.
4. Atlas must include `prior_attempts` if the task has been attempted before. Ghost Executor passes this to the agent so it does not repeat known failures.
5. The `interrupt_policy` must be respected. A directive with `interruptible: false` must run to completion or timeout.

---

## CONTRACT 4: Ghost Executor → Claude Code

### Purpose
Ghost Executor formats the Atlas directive into a structured task prompt that Claude Code can execute without requiring a back-and-forth conversation to understand scope.

### What Ghost Executor Produces

```json
{
  "task_prompt": {
    "id": "string",
    "directive_id": "string",
    "issued_at": "timestamp",

    "instruction": {
      "objective": "string",
      "context": "string",
      "constraints": ["string"],
      "success_criteria": ["string"],
      "failure_criteria": ["string"]
    },

    "environment": {
      "working_directory": "string",
      "relevant_files": ["string"],
      "available_tools": ["string"],
      "infrastructure_context": "string | null"
    },

    "prior_attempts": [
      {
        "summary": "string",
        "what_failed": "string",
        "what_to_avoid": "string"
      }
    ],

    "output_spec": {
      "expected_artifacts": ["string"],
      "format": "string",
      "location": "string"
    },

    "constraints": {
      "max_tokens": 0,
      "timeout_seconds": 0,
      "do_not_modify": ["string"],
      "require_tests": false
    }
  }
}
```

### What Claude Code Does on Receive

Claude Code executes the task and returns a build output:

```json
{
  "build_output": {
    "task_prompt_id": "string",
    "completed_at": "timestamp",
    "status": "success | partial | failed",

    "artifacts": [
      {
        "type": "file | diff | url | log",
        "path": "string",
        "description": "string"
      }
    ],

    "summary": "string",
    "issues_encountered": ["string"],
    "follow_on_tasks": ["string"],
    "tokens_used": 0
  }
}
```

### Contract Rules

1. Ghost Executor must always include `success_criteria` and `failure_criteria` in the instruction. Claude Code uses these to self-evaluate before returning output.
2. `do_not_modify` is a hard constraint. Claude Code must not touch listed files under any circumstances.
3. `prior_attempts` must be surfaced plainly — not buried in context. Claude Code should see failures before it starts.
4. Claude Code must always return a `build_output` even on failure. A silent failure is a contract violation.
5. `follow_on_tasks` in the build output feeds back into Atlas as candidate tasks for the next queue evaluation.

---

## CONTRACT 5: All Layers → InPACT

### Purpose
InPACT is the human surface. It receives signals from every layer and surfaces what the user needs to see — what's in flight, what just closed, what's next, and what requires a human decision.

### Universal Signal Schema

Every layer emits signals to InPACT using a shared schema:

```json
{
  "signal": {
    "id": "string",
    "emitted_at": "timestamp",
    "source_layer": "site_pull | optogon | atlas | ghost_executor | claude_code",
    "signal_type": "status | completion | blocked | approval_required | error | insight",
    "priority": "urgent | normal | low",

    "payload": {
      "task_id": "string | null",
      "label": "string",
      "summary": "string",
      "data": {},
      "action_required": true,
      "action_options": [
        {
          "id": "string",
          "label": "string",
          "consequence": "string",
          "risk_tier": "low | medium | high"
        }
      ]
    }
  }
}
```

### Signal Types by Layer

| Layer | Signal Types | InPACT Behavior |
|:---|:---|:---|
| **Site Pull** | `status` (mapping in progress), `completion` (context ready), `error` (source unreachable) | Show mapping status; surface partial context warnings |
| **Optogon** | `status` (path active), `approval_required` (high-risk action), `completion` (path closed), `blocked` (awaiting dependency) | Show active sessions; surface approval requests immediately; log completions |
| **Atlas** | `insight` (leverage score update), `status` (queue re-scored), `blocked` (no executable tasks) | Surface top 3 queue items on Today Dashboard; flag when queue is blocked |
| **Ghost Executor** | `status` (directive fired), `approval_required` (autonomy check), `error` (execution failed) | Show tasks in flight; route approval requests to user |
| **Claude Code** | `completion` (build done), `error` (build failed), `status` (in progress) | Surface build outputs; flag failures with follow-on options |

### InPACT Display Rules

1. `approval_required` signals always surface immediately regardless of other activity. They block the relevant execution thread until resolved.
2. `urgent` priority signals surface above the fold on the Today Dashboard.
3. `completion` signals with deliverables are logged and linkable — the user can always find what was built and when.
4. `error` signals always include `action_options` so the user is never left with a dead end.
5. InPACT never shows internal system data (node IDs, path IDs, session state). It translates everything into plain language.
6. The Today Dashboard surfaces only what requires human attention. Everything the system can handle autonomously is handled autonomously and logged, not surfaced.

---

## Cross-Stack Interrupt Protocol

When a higher-priority task surfaces mid-execution, the interrupt protocol fires across layers:

```
Atlas detects higher-priority task
    ↓
Atlas checks active directive in Ghost Executor
    ↓
If directive.interrupt_policy.interruptible = true:
    Ghost Executor pauses execution
    Saves current state to session
    Emits interrupt signal to InPACT
    Loads new directive
    ↓
If directive.interrupt_policy.interruptible = false:
    Atlas queues the new task at top of queue
    Waits for current directive to complete or timeout
    ↓
On resume:
    Ghost Executor reloads saved session state
    Continues from last checkpoint
```

This resolves the coordination gap between Atlas and Optogon identified in DeepSeek's revised assessment.

---

## Cross-Session User Memory

Atlas owns the cross-session user preference store. Every layer can read from it. Only Optogon (via close signal `context_residue.learned_preferences`) and InPACT (via explicit user settings) can write to it.

```json
{
  "user_preference_store": {
    "user_id": "string",
    "last_updated": "timestamp",

    "preferences": [
      {
        "key": "string",
        "value": "any",
        "confidence": 0.0,
        "source": "explicit | inferred",
        "observed_count": 0,
        "last_observed": "timestamp"
      }
    ],

    "behavioral_patterns": [
      {
        "pattern": "string",
        "frequency": "always | usually | sometimes",
        "context": "string",
        "first_observed": "timestamp"
      }
    ]
  }
}
```

This resolves the cross-session memory gap identified in DeepSeek's revised assessment. It lives in Atlas. It is not a separate layer.

---

## Contract Versioning

As layers evolve, contracts will need to version independently. Rules:

1. Each contract has a `schema_version` field (semver).
2. Breaking changes require a major version bump.
3. Additive changes (new optional fields) are minor bumps.
4. All layers must declare which contract version they produce and consume.
5. A mismatch in major version between producer and consumer is a hard failure — not a degraded mode.

---

## Summary Table

| Contract | Producer | Consumer | Critical Field |
|:---|:---|:---|:---|
| Context Package | Site Pull | Optogon | `action_inventory` |
| Close Signal | Optogon | Atlas | `learned_preferences` |
| Directive | Atlas | Ghost Executor | `success_criteria` |
| Task Prompt | Ghost Executor | Claude Code | `failure_criteria` |
| Signal | All Layers | InPACT | `action_required` |
| Preference Store | Atlas (owns) | All Layers (read) | `confidence` |

---

*This document is the Rosetta Stone. The layers can be built independently. As long as the contracts hold, the stack holds.*

*Version 1.0 — Produced from founding session, April 2026.*


## DOCTRINE 03 - OPTOGON SPEC v2.1

*Source: `doctrine/03_OPTOGON_SPEC.md`*

# OPTOGON
## Product Specification v2.1
**The Control Layer That Turns AI from a Talker into a Closer**

---

## 0. Doctrine — Why This Exists and Where It Came From

This section comes before the mission because the mission only makes sense if you understand what produced it.

### The Origin

Optogon was not designed from AI research. It was not derived from agent framework literature or LLM benchmarks. It was built backwards from a problem that every sales floor already solved decades ago.

In door-to-door and telecom sales, the difference between a rookie rep and a trained closer is not intelligence. It is not charm. It is not even work ethic.

It is **prepared structure**.

A rookie rep walks up to a door and improvises. They ask too many questions. They over-explain the product. They follow the customer's frame instead of leading it. They drift. They talk themselves out of the close. They leave the door having had a conversation but not having moved anything forward.

A trained closer does not improvise. Before they knock, the path is already loaded. They know the entry. They know the qualification signals. They know which objections are real and which are deflections. They know when to stop talking and let the close land. They are patient because the structure is doing the work underneath. The customer experiences a natural conversation. What is actually happening is a disciplined sequence moving toward a single outcome.

That is the model.

### The Problem With Raw AI

Raw AI is a rookie rep.

It starts from zero every time. It asks questions it should already know the answers to. It over-explains. It hedges. It drifts conversationally when the user needs forward momentum. It separates talking from doing — it discusses what it could do instead of doing it while the conversation continues. It pushes the orchestration burden back onto the user, who now has to manage both their own thinking and the AI's behavior simultaneously.

This is not a model capability problem. The models are capable. This is a **structure problem**. The AI has no prepared path. No qualification logic. No pacing discipline. No completion orientation. It is improvising on every turn.

The result is a system that feels helpful but rarely finishes anything.

### What Optogon Is

Optogon is the loaded structure that makes AI perform like a trained closer.

It does not make the model smarter. It gives the model what the closer already has before the first word is spoken — a prepared path, qualification checkpoints, burden-removal defaults, pacing discipline, and a defined close state that the entire interaction is moving toward.

The user experiences a conversation. The system is executing a sequence.

That gap — between what the user experiences and what is actually happening — is where Optogon lives. It is the invisible discipline underneath a natural surface.

### Why This Is the Moat

This architecture came from a sales floor, not a whitepaper. The pacing rules exist because real closers learned the hard way that overloading a prospect kills momentum. The burden-removal layer exists because every rep eventually learns that the fastest path to a close is removing decisions, not adding information. The qualification logic exists because a trained closer never asks two questions when one question can do both jobs.

These are not engineering abstractions. They are field-tested truths encoded into a system.

An engineer without this background can build the technical layer from this spec. What they cannot build is the judgment that produced the spec. That judgment is the moat.

### The Governing Principle

**The user should experience a conversation. The system should execute a close.**

Everything in this specification is downstream of that sentence. Every architectural decision, every pacing rule, every burden-removal behavior — all of it exists to hold that principle in place at runtime.

---

## 1. Mission

Optogon exists to give AI the hidden structure behind reliable execution: known-good paths, burden-removal behaviors, executable actions, pacing logic, validation contracts, and completion discipline.

The goal is **more finished outcomes with less friction, less drift, and less user burden.**

---

## 2. Core Definitions

**Plain English**
Optogon is a layered preparation and execution system that preloads AI with structure before interaction begins, so it can guide naturally, reduce unnecessary conversation, and move work toward completion.

**Technical**
Optogon is a structured execution architecture combining pathing, tools, contracts, pacing, and burden-removal logic to produce predictable agent behavior with lower token waste.

**The Core Principle**
*"The user experiences a conversation. The system executes a close."*

---

## 3. Problem

Current AI systems fail predictably:
- Start from zero too often
- Ask too many questions
- Over-explain
- Drift conversationally
- Push orchestration onto the user
- Separate talking from doing
- Rediscover workflows that should already be known

Users want less burden, less friction, less waiting, and more completion.

---

## 4. Product Thesis

The best assistant doesn't make the user do all the work. It qualifies quickly, understands enough, removes unnecessary decisions, and quietly advances the task.

Optogon achieves this by giving AI:
- Pre-structured paths (the domain graph)
- Multi-purpose qualification nodes (one question, multiple jobs)
- Deterministic execution hooks (tools with risk profiles)
- Burden-removal defaults (safe inference with reversibility checks)
- Pacing constraints (information density per turn)
- Continuous movement toward a close state

---

## 5. The Six-Layer Architecture

| Layer | Purpose | Key Components |
|:---|:---|:---|
| **1. Path Layer** | Defines known-good interaction routes | Entry conditions, node graph, branches, objection patterns, close states, sub-routines |
| **2. Execution Layer** | Performs real work | Tool calls, code ops, retrieval, transformation, side effects—all with risk tiers |
| **3. Contract Layer** | Guarantees stable, trustworthy behavior | Required outputs, validation rules, completion criteria, failure modes |
| **4. Pacing Layer** | Controls information density | What to surface, what to suppress, max options, explanation toggles |
| **5. Burden-Removal Layer** | Absorbs work the system can carry | Inference rules, safe defaults, admin takeover, next-step staging |
| **6. Learning Layer** | Turns repetition into infrastructure | Successful branches, dead ends, token efficiency, path optimization |

---

## 6. The Atomic Unit: Node

A **Node** is the smallest unit of work. Every interaction is a chain of node resolutions.

### Node Types

| Type | Purpose | Behavior |
|:---|:---|:---|
| **qualify** | Gather information needed to advance | Asks one multi-purpose question or infers from context. Transitions when qualification keys are filled. |
| **execute** | Perform an action | Runs tools/code. May run in parallel with conversation. No question unless action fails. |
| **gate** | Check a condition before proceeding | Pure logic. Silent. Evaluates state and routes to the correct branch. |
| **fork** | Spawn a sub-routine | Pushes current path onto the stack, enters a child path. Resumes parent on child close. |
| **approval** | Obtain explicit user confirmation for high-risk actions | Pauses execution, presents a bundled confirmation, waits for user acknowledgment before proceeding. |
| **close** | Terminal node | Validates final contract. Emits completion signal and deliverable. |

### Node States

Every node instance is in exactly one of:

| State | Meaning |
|:---|:---|
| **UNQUALIFIED** | Missing required qualification data. Needs user input or inference. |
| **QUALIFIED** | All inputs present. Actions can fire. |
| **BLOCKED** | Actions fired but waiting on external dependency (API, webhook, human). |
| **AWAITING_APPROVAL** | High-risk action pending user confirmation. |
| **CLOSED** | Contract satisfied. Ready to transition. |

### Node Schema

```json
{
  "id": "string",
  "type": "qualify | execute | gate | fork | approval | close",
  "label": "string",

  "qualification": {
    "required": [
      {
        "key": "string",
        "description": "string",
        "source": "user | inferred | system | prior_node",
        "fallback": "any | null",
        "confidence_floor": 0.7
      }
    ],
    "question": {
      "text": "string",
      "purpose": ["string"],
      "max_asks": 1
    },
    "max_missing_keys_before_split": 2
  },

  "inference_rules": [
    {
      "key": "string",
      "condition": "string",
      "confidence": 0.0,
      "confidence_source": "static | logprob | learned",
      "reversible": true,
      "risk_tier": "low | medium | high"
    }
  ],

  "actions": [
    {
      "id": "string",
      "type": "tool_call | code | retrieval | transform | side_effect",
      "trigger": "on_entry | on_qualified | parallel",
      "spec": {},
      "reversible": true,
      "risk_tier": "low | medium | high",
      "retry_strategy": "immediate | exponential_backoff | none"
    }
  ],

  "contract": {
    "required_outputs": ["string"],
    "validation": "string | function_ref",
    "completion_criteria": "string",
    "max_retries": 2,
    "failure_mode": "retry | fallback | escalate | abort"
  },

  "pacing": {
    "surface": ["string"],
    "suppress": ["string"],
    "max_options_shown": 3,
    "explain": false,
    "bundle_confirmations": true
  },

  "transitions": [
    {
      "to": "node_id",
      "condition": "string | default",
      "priority": 1
    }
  ],

  "metadata": {
    "token_budget": 200,
    "tags": ["string"]
  }
}
```

---

## 7. Path Definition

A **Path** is a directed graph of nodes defining one complete workflow.

### Path Schema

```json
{
  "id": "string",
  "name": "string",
  "version": "string",
  "description": "string",

  "entry": {
    "node_id": "string",
    "match_conditions": [
      {
        "signal": "string",
        "operator": "contains | equals | regex | intent",
        "value": "string"
      }
    ],
    "match_threshold": 0.6,
    "tie_break": "priority | specificity"
  },

  "nodes": { "node_id": { } },
  "edges": [
    {
      "from": "node_id",
      "to": "node_id",
      "condition": "string | default",
      "priority": 1
    }
  ],

  "sub_routines": {
    "routine_id": {
      "trigger": "string",
      "path_id": "string",
      "resume_node": "node_id | auto",
      "inherit_context": ["key1", "key2"]
    }
  },

  "close_state": {
    "description": "string",
    "deliverables": ["string"],
    "validation": "string | function_ref"
  },

  "defaults": {
    "pacing": { },
    "inference_confidence_floor": 0.7
  }
}
```

---

## 8. Runtime State

### Session State Schema

```json
{
  "session_id": "string",
  "path_id": "string",
  "current_node": "string",

  "node_states": {
    "node_id": {
      "status": "unqualified | qualified | blocked | awaiting_approval | closed",
      "entered_at": "timestamp",
      "closed_at": "timestamp | null",
      "attempts": 0,
      "qualification_data": {},
      "action_results": {},
      "errors": []
    }
  },

  "context": {
    "confirmed": {},
    "user": {},
    "inferred": {},
    "system": {}
  },

  "fork_stack": [
    {
      "parent_path_id": "string",
      "parent_node_id": "string",
      "resume_node": "string",
      "forked_at": "timestamp"
    }
  ],

  "action_log": [
    {
      "action_id": "string",
      "node_id": "string",
      "type": "string",
      "status": "pending | success | failed | rolled_back",
      "executed_at": "timestamp",
      "result": {},
      "reversible": true,
      "reversed": false
    }
  ],

  "metrics": {
    "total_tokens": 0,
    "total_questions_asked": 0,
    "total_inferences_made": 0,
    "total_actions_fired": 0,
    "nodes_closed": 0,
    "nodes_total": 0
  }
}
```

### Context Hierarchy (Strict Override Order)

| Tier | Source | Override Rule |
|:---|:---|:---|
| **confirmed** | User explicitly stated or approved | Cannot be overridden by inference |
| **user** | Parsed from user input (not confirmed) | Overridden by confirmed |
| **inferred** | System guess based on inference rules | Overridden by user or confirmed |
| **system** | Environment data (time, location, history) | Informational only; never overrides user intent |

---

## 9. Burden-Removal: The Risk Matrix

Every inference and action is evaluated on **Confidence × Blast Radius**.

| | **Low Risk** (Reversible, no cost, no external effect) | **High Risk** (Irreversible, has cost, external side effect) |
|:---|:---|:---|
| **High Confidence** | Act silently | Act + notify |
| **Low Confidence** | Act + mention | Ask first (or use approval node) |

### Risk Tier Definitions

| Tier | Criteria | Examples |
|:---|:---|:---|
| **low** | Reversible, no external effect, no cost | Auto-fill name, default timezone, pre-load template |
| **medium** | Reversible but inconvenient, minor external effect | Draft email, calendar hold, table reservation |
| **high** | Irreversible or costly, external consequences | Charge payment, submit application, delete data |

---

## 10. Pacing Rules

Pacing is **information density per turn**, not real-time silence detection.

### Default Pacing Constraints

| Rule | Value |
|:---|:---|
| Maximum options shown | 3 |
| Maximum questions per turn | 1 |
| Explain by default | false |
| Show progress | false |
| Suppress internal logic | true (never mention nodes, paths, or state machines) |
| Bundle confirmations | true |

### Pacing Doctrine

1. **One question per turn** — that question must do multiple jobs (qualify + route + signal intent).
2. **Suppress options the path already knows are irrelevant.**
3. **Front-load action, back-load explanation.**
4. **Bundle confirmations** — confirm the whole intent, not each field.
5. **Never mention nodes, paths, or internal state to the user.**

---

## 11. MVP Scope

**Goal**: Prove that structured preparation materially improves AI completion quality and reduces wasted interaction.

### MVP Components

1. **Path definitions** (JSON, hand-authored for 2–3 use cases)
2. **Node Processor** — deterministic engine that:
   - Parses user input into context (LLM)
   - Applies inference rules
   - Manages node state transitions
   - Fires actions
   - Validates contracts
3. **Contract Validator** — checks required outputs
4. **Response Composer** — LLM call with pacing constraints
5. **Session Store** — key-value persistence

### MVP Success Metrics

| Metric | Target |
|:---|:---|
| Questions per Close | < 3 for a 5-node path |
| Inference Accuracy | > 0.85 |
| Path Completion Rate | > 0.75 |
| Token Efficiency (tokens / node closed) | < 200 |

---

## 12. Example Walkthrough: Booking a Flight

### Path: `book_flight`

| Node | Type | Behavior |
|:---|:---|:---|
| `entry` | qualify | "Where are you headed and when?" → populates destination + date |
| `preferences` | qualify | "Window or aisle? Airline preference?" → fallback any/any |
| `search` | execute | Calls flight search API; marks BLOCKED until results return |
| `select` | qualify | Shows top 3 options; user selects one |
| `confirm` | approval | Bundles: "NYC → LAX, Thu 8am, Delta, window. Book now?" Requires explicit "yes" |
| `book` | execute | High-risk side effect; charges card, returns booking ref |
| `done` | close | Delivers confirmation number |

**Burden-removal in action:**
- `preferences` closes instantly on defaults if user says "I don't care."
- `confirm` is an approval node — it pauses for explicit acknowledgment before irreversible action.
- Pacing surfaces only top 3 flights; 27 other results are suppressed.

**Sub-routine fork:**
User: *"Wait, is there a good hotel near LAX?"*
→ Fork trigger matched → push `book_flight` state → enter `hotel_search` sub-routine → on close, resume at `select` with hotel info in context.

**The closer parallel:**
A trained rep would not stop the booking to research hotels from scratch. They would say "let me handle that" — keep the primary close alive on the stack, handle the objection, and return to the path. That is exactly what the fork does. The user experiences helpfulness. The system never lost the close.

---

## 13. What Optogon Is Not

- Not a chatbot wrapper
- Not a prompt library
- Not a tool registry alone
- Not a workflow engine
- Not a decision tree
- Not a generic agent framework

All of those are pieces. Optogon is the **loaded execution stack** that makes those components behave like a trained closer, not a chatterbox.

The difference is doctrine. Any team can assemble the components. The judgment behind the architecture — the pacing rules, the burden-removal philosophy, the completion orientation — that came from a sales floor. It is not reproducible from a whitepaper.

---

## 14. Node Processor Implementation

The Node Processor is the engine. Pseudocode skeleton:

```python
def process_turn(session: SessionState, user_message: str) -> tuple[SessionState, str]:
    current_node = get_node(session.path_id, session.current_node)

    # 1. Parse user input into context (LLM call)
    extracted = llm_parse(user_message, current_node.qualification["required"])
    update_context(session, extracted, tier="user")

    # 2. Apply inference rules for missing keys
    for key, req in current_node.qualification["required"].items():
        if not is_qualified(session.context, key):
            inferred = apply_inference_rule(key, session)
            if inferred.confidence >= req.get("confidence_floor", 0.7):
                update_context(session, {key: inferred.value}, tier="inferred")

    # 3. Check qualification
    if all_keys_present(current_node, session.context):
        session.node_states[current_node.id].status = "qualified"

        # 4. Fire actions
        for action in current_node.actions:
            if action.trigger in ["on_qualified", "parallel"]:
                result = execute_action(action, session.context)
                session.node_states[current_node.id].action_results[action.id] = result
                if action.risk_tier == "high" and current_node.type != "approval":
                    redirect_to_approval(session, current_node, action)

        # 5. Validate contract
        if validate_contract(current_node.contract, session.context):
            if current_node.type == "approval" and not user_approved(user_message):
                session.node_states[current_node.id].status = "awaiting_approval"
            else:
                session.node_states[current_node.id].status = "closed"
                next_node = determine_transition(current_node.transitions, session.context)
                session.current_node = next_node.id
        else:
            handle_validation_failure(current_node, session)

    # 6. Compose response with pacing constraints
    response = llm_compose(session, current_node, pacing_rules)
    return session, response
```

---

*Optogon Product Spec v2.1*
*Section 0 added — doctrine before architecture.*
*The code is implementable by an engineer. The doctrine is not. Both are required.*


## DOCTRINE 04 - BUILD PLAN (mapped to repo)

*Source: `doctrine/04_BUILD_PLAN.md`*

# OPTOGON STACK — BUILD PLAN
*Maps the doctrine (01), contracts (02), and spec (03) onto concrete work in this repo.*
*Generated 2026-04-18.*

---

## 1. Layer Reality Check — What Exists Today

| Stack Layer (doctrine name) | Closest Thing In Repo | Status | Gap |
|:---|:---|:---|:---|
| **Site Pull** (Eyes) | None in this repo | Shipped on NPM per doctrine, not integrated here | No adapter that emits `ContextPackage` |
| **Optogon** (Brain stem) | None | Doctrine complete, zero code | Entire service |
| **Atlas** (Mind) | `services/delta-kernel/` + `services/cognitive-sensor/` + `atlas.ts` CLI | Real, running, leverage scoring exists | Doesn't emit `Directive` in Rosetta Stone shape |
| **Ghost Executor** (Autonomy) | `services/cortex/` (:3009, planner/executor/reviewer) + `services/uasc-executor/` (:3008, command executor) | Two separate pieces that together cover this role | Neither consumes `Directive` nor produces `TaskPrompt` in Rosetta Stone shape |
| **InPACT** (Hands) | `apps/inpact/` (:3006, today.html) | Product surface locked, light theme, Phase 2 live | No Signal ingestion; doesn't yet render cross-layer state |

**Critical insight:** Ghost Executor is not one thing in this repo. It is split across Cortex (agent orchestration) and UASC (command execution). The Rosetta Stone's Contract 3 → 4 flow maps onto **Atlas → Cortex → (UASC | Claude Code)**. Treat Cortex as Ghost Executor going forward; UASC stays as the tool-level executor beneath it.

---

## 2. Decisions Required Before Build (resolve these first)

| # | Decision | Options | Recommendation |
|:---|:---|:---|:---|
| D1 | Optogon language | Python (matches spec pseudocode, matches Cortex/UASC) / TypeScript (matches delta-kernel) | **Python** — spec is Python, and Optogon talks to Atlas via HTTP not in-process |
| D2 | Optogon port | :3010 next available | **:3010** |
| D3 | First real path to implement | `book_flight` (toy), `ship_inpact_lesson` (real), `close_cognitive_sensor_run` (real) | **`ship_inpact_lesson`** — tests doctrine against real work you already do |
| D4 | Where do Path JSON files live | `services/optogon/paths/` / `contracts/paths/` | **`services/optogon/paths/`** — paths are code, not contracts |
| D5 | Contract schemas location | `contracts/schemas/` (existing) | **`contracts/schemas/`** — consistent with ModeContract.v1.json, AegisPolicy.v1.json, etc. |
| D6 | Does Cortex get renamed to `ghost_executor`? | Yes / No / Alias | **No, alias** — keep service name, document that Cortex *is* the Ghost Executor role |

---

## 3. Build Sequence — Four Phases

Mapped to doctrine's Part 8 ("What To Build First"):

### Phase 1 — Contracts First (1–2 hours)
*Ground truth before any logic. JSON Schemas that every layer validates against.*

**Deliverables:**
- `contracts/schemas/OptogonNode.v1.json` — Section 6 of spec
- `contracts/schemas/OptogonPath.v1.json` — Section 7 of spec
- `contracts/schemas/OptogonSessionState.v1.json` — Section 8 of spec
- `contracts/schemas/ContextPackage.v1.json` — Rosetta Contract 1
- `contracts/schemas/CloseSignal.v1.json` — Rosetta Contract 2
- `contracts/schemas/Directive.v1.json` — Rosetta Contract 3
- `contracts/schemas/TaskPrompt.v1.json` — Rosetta Contract 4
- `contracts/schemas/BuildOutput.v1.json` — Rosetta Contract 4 response
- `contracts/schemas/Signal.v1.json` — Rosetta Contract 5
- `contracts/schemas/UserPreferenceStore.v1.json` — Rosetta cross-session memory
- `contracts/examples/` — one valid example per schema

**Success:** All 10 schemas validate their own example with `jsonschema`. Nothing else runs yet.

---

### Phase 2 — Optogon MVP Service (2–3 hours)
*The four things doctrine says must exist.*

**Scaffold `services/optogon/`:**
```
services/optogon/
  pyproject.toml
  start.bat
  src/optogon/
    __init__.py
    main.py                  # FastAPI server on :3010
    config.py
    node_processor.py        # Section 14 of spec
    contract_validator.py    # Contract Layer enforcement
    response_composer.py     # Pacing Layer — LLM call with constraints
    session_store.py         # In-memory + SQLite persistence
    context.py               # Context hierarchy (confirmed > user > inferred > system)
    inference.py             # Burden-Removal inference rules
    signals.py               # Emits Signal to InPACT
  paths/
    ship_inpact_lesson.json  # First real path
    _template.json           # Blank path for authoring
  tests/
    test_node_processor.py
    test_contract_validator.py
    test_pacing.py
    test_path_ship_inpact_lesson.py
```

**Endpoints (FastAPI):**
- `POST /session/start` — body: `{path_id, initial_context}` → creates session, returns `session_id` + first response
- `POST /session/{session_id}/turn` — body: `{message}` → processes user turn, returns response + current node state
- `GET /session/{session_id}` — returns full session state (debug/Inpact consumption)
- `GET /paths` — lists available paths
- `GET /health`

**Success metrics (from spec Section 11):**
| Metric | Target |
|:---|:---|
| Questions per Close | < 3 for 5-node path |
| Inference Accuracy | > 0.85 |
| Path Completion Rate | > 0.75 |
| Tokens per node closed | < 200 |

**Validation:** Run `ship_inpact_lesson` path end-to-end. Must close with deliverable = lesson content merged into `apps/inpact/content/lessons/`.

---

### Phase 3 — Wire Into Atlas + InPACT (1–2 hours)
*Make the existing layers speak the contracts.*

**3a. Atlas → Directive emitter**
- Add `services/delta-kernel/src/atlas/directive.ts` — transforms current task queue output into `Directive.v1.json` shape
- Add `GET /api/atlas/next-directive` to delta-kernel
- Validate output against schema on emit

**3b. Cortex as Ghost Executor**
- Add `services/cortex/src/cortex/ghost_executor/` module
- `consume_directive(directive: Directive) -> TaskPrompt` — reformats for Claude Code
- `emit_build_output(result) -> BuildOutput` — structured return
- Document in `cortex/README.md` that Cortex plays the Ghost Executor role

**3c. InPACT Signal consumption**
- Add `apps/inpact/signals.js` — fetches from `/api/signals`
- Add `GET /api/signals` endpoint in delta-kernel (aggregates from all layers)
- today.html renders `approval_required` and `urgent` signals above the fold per Section 11 display rules
- No new design surfaces — reuse existing today.html blocks

**Success:** Trigger an Optogon path end-to-end from InPACT → today.html shows the close signal + deliverable link.

---

### Phase 4 — Close Signal Loop + Preference Store (1 hour)
*Completes the feedback cycle.*

**Deliverables:**
- `POST /api/atlas/close-signal` in delta-kernel — accepts `CloseSignal`, updates task queue
- `contracts/schemas/UserPreferenceStore.v1.json` + backing store in delta-kernel (SQLite)
- Optogon populates `context_residue.learned_preferences` on close
- Atlas writes them to preference store
- Cortex reads preferences when composing next `TaskPrompt`

**Success:** Run `ship_inpact_lesson` twice. Second run asks fewer questions because the preference store learned from the first.

---

## 4. What We Are NOT Building (scope discipline)

Per doctrine Part 8 ("do not build everything Optogon could be"):

- Learning Layer (Layer 6 in spec) — deferred until after 10 real path runs
- Cross-layer Interrupt Protocol — documented in Rosetta Stone, not coded until two paths race
- Sub-routine forking — structurally supported in schema, not wired in MVP
- Full 8-agent Atlas architecture — stay on existing delta-kernel leverage scoring
- Site Pull integration — stays external until Phase 5+

---

## 5. First Real Path — `ship_inpact_lesson`

This tests the doctrine against work you already do.

| Node | Type | Qualification Keys | Actions |
|:---|:---|:---|:---|
| `entry` | qualify | `lesson_number`, `content_source` | — |
| `load_skeleton` | execute | — | Read `apps/inpact/content/lessons/{N}.md` skeleton |
| `validate_content` | gate | — | Check content_source exists and is non-empty |
| `merge` | execute | — | Merge content into skeleton using shared `ls-*` CSS (per `feedback_one_lesson_template.md`) |
| `preview` | execute | — | Start preview server, render lesson |
| `em_dash_check` | gate | — | Scan for em dashes (per `feedback_no_em_dashes_in_ui.md`) — FAIL if found |
| `approve` | approval | — | Bundle: "Lesson N ready. Preview at :3006/lessons/N. Commit?" |
| `commit` | execute | — | Git commit with conventional message |
| `done` | close | — | Emit `CloseSignal` with deliverable = commit SHA |

**Why this path:** it exercises qualify, execute, gate, approval, close node types. It uses real repo rules (em dash ban, shared CSS). It produces a real deliverable (a shipped lesson).

---

## 6. Risk Register

| Risk | Likelihood | Mitigation |
|:---|:---|:---|
| LLM pacing layer drifts despite constraints | High | Start with strict token budgets; measure `Questions per Close` on every run |
| Contract schemas go stale as code evolves | Medium | CI check that loads every schema + validates every example on commit |
| Cortex/UASC confusion ("which one is Ghost Executor?") | Medium | Document in `services/cortex/README.md` explicitly; Cortex *is* the role |
| "Three-hour MVP" timeline slips (it will) | Certain | Accept it. Doctrine says "3 hours" — plan says four phases. Don't conflate. |
| Path JSON authoring is painful | High | Phase 2 includes `_template.json` + `test_path_ship_inpact_lesson.py` as the authoring example |
| Active lanes (Code Converter, inPACT curriculum) starve | High | Optogon is a new lane, not a replacement. Explicit choice: pause one, or parallelize. |

---

## 7. Lane Choice — Where Does Optogon Fit

Current active lanes per MEMORY.md:
- Code to Numeric Logic MVP (ACTIVE)
- Mosaic Phase 4 (PAUSED)
- inPACT curriculum embodiment (ACTIVE BUILD)
- inPACT product pivot (ACTIVE)

Adding Optogon makes 3 active lanes. Options:

- **Option A:** Defer Optogon until one active lane ships. Keeps focus. Cost: doctrine cools.
- **Option B:** Phase 1 only (contracts) now. Then decide. Low cost, preserves optionality.
- **Option C:** Full build starting now. Cost: slows inPACT curriculum + code converter.

Recommendation: **Option B** — do Phase 1 (contracts) this session. It's 1-2 hours and produces 10 schemas that don't cost anything if you defer the rest. Decide on Phase 2 after seeing the schemas land.

---

## 8. Ready-to-Run Next Step

When you say go, Phase 1 begins:

1. Generate all 10 JSON schemas under `contracts/schemas/` with proper `$schema` and `schema_version` fields
2. Generate one valid example per schema under `contracts/examples/`
3. Add a `validate.js` or `validate.py` script that loads every schema + example and asserts validity
4. Update `contracts/README.md` to document the Optogon + Rosetta Stone schemas
5. Commit as `feat(contracts): optogon stack schemas v1`

No service code. No wiring. Just the contracts.

---

*This plan is downstream of the doctrine. If the doctrine says something different, the doctrine wins.*


## DOCTRINE 05 - FEST PLAN (festival projection)

*Source: `doctrine/05_FEST_PLAN.md`*

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


## CONTRACT: OptogonNode.v1.json

*Source: `contracts/schemas/OptogonNode.v1.json`*

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "OptogonNode.v1",
  "title": "Optogon Node",
  "description": "The atomic unit of work in an Optogon path. Per 03_OPTOGON_SPEC.md Section 6.",
  "type": "object",
  "required": ["id", "type", "label", "schema_version"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0"
    },
    "id": {
      "type": "string",
      "minLength": 1
    },
    "type": {
      "type": "string",
      "enum": ["qualify", "execute", "gate", "fork", "approval", "close"]
    },
    "label": {
      "type": "string"
    },
    "qualification": {
      "type": "object",
      "properties": {
        "required": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["key", "source"],
            "properties": {
              "key": { "type": "string" },
              "description": { "type": "string" },
              "source": {
                "type": "string",
                "enum": ["user", "inferred", "system", "prior_node"]
              },
              "fallback": {},
              "confidence_floor": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
              }
            }
          }
        },
        "question": {
          "type": "object",
          "properties": {
            "text": { "type": "string" },
            "purpose": {
              "type": "array",
              "items": { "type": "string" }
            },
            "max_asks": {
              "type": "integer",
              "minimum": 0
            }
          }
        },
        "max_missing_keys_before_split": {
          "type": "integer",
          "minimum": 0
        }
      }
    },
    "inference_rules": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["key", "condition", "confidence"],
        "properties": {
          "key": { "type": "string" },
          "condition": { "type": "string" },
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          },
          "confidence_source": {
            "type": "string",
            "enum": ["static", "logprob", "learned"]
          },
          "reversible": { "type": "boolean" },
          "risk_tier": {
            "type": "string",
            "enum": ["low", "medium", "high"]
          }
        }
      }
    },
    "actions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "type"],
        "properties": {
          "id": { "type": "string" },
          "type": {
            "type": "string",
            "enum": ["tool_call", "code", "retrieval", "transform", "side_effect"]
          },
          "trigger": {
            "type": "string",
            "enum": ["on_entry", "on_qualified", "parallel"]
          },
          "spec": { "type": "object" },
          "reversible": { "type": "boolean" },
          "risk_tier": {
            "type": "string",
            "enum": ["low", "medium", "high"]
          },
          "retry_strategy": {
            "type": "string",
            "enum": ["immediate", "exponential_backoff", "none"]
          }
        }
      }
    },
    "contract": {
      "type": "object",
      "properties": {
        "required_outputs": {
          "type": "array",
          "items": { "type": "string" }
        },
        "validation": { "type": "string" },
        "completion_criteria": { "type": "string" },
        "max_retries": {
          "type": "integer",
          "minimum": 0
        },
        "failure_mode": {
          "type": "string",
          "enum": ["retry", "fallback", "escalate", "abort"]
        }
      }
    },
    "pacing": {
      "type": "object",
      "properties": {
        "surface": {
          "type": "array",
          "items": { "type": "string" }
        },
        "suppress": {
          "type": "array",
          "items": { "type": "string" }
        },
        "max_options_shown": {
          "type": "integer",
          "minimum": 0
        },
        "explain": { "type": "boolean" },
        "bundle_confirmations": { "type": "boolean" }
      }
    },
    "transitions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["to", "condition"],
        "properties": {
          "to": { "type": "string" },
          "condition": { "type": "string" },
          "priority": {
            "type": "integer",
            "minimum": 0
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "token_budget": {
          "type": "integer",
          "minimum": 0
        },
        "tags": {
          "type": "array",
          "items": { "type": "string" }
        }
      }
    }
  },
  "allOf": [
    {
      "if": { "properties": { "type": { "const": "approval" } } },
      "then": { "required": ["contract"] }
    },
    {
      "if": { "properties": { "type": { "const": "close" } } },
      "then": { "required": ["contract"] }
    }
  ]
}

```


## CODE: optogon/node_processor.py (core runtime)

*Source: `services/optogon/src/optogon/node_processor.py`*

```python
"""Node processor - dispatches a user turn to the correct node-type handler.

Per doctrine/03_OPTOGON_SPEC.md Section 14. Six node types:
qualify, execute, gate, fork, approval, close.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .action_handlers import ActionError, run_action
from .context import empty_context, missing_keys, promote_to_confirmed, resolve, set_tier
from .inference import apply_node_rules
from .preferences_client import post_close_signal
from .response_composer import compose
from . import signals


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def process_turn(
    session_state: dict[str, Any],
    path: dict[str, Any],
    user_message: Optional[str],
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    """Advance the session by one turn.

    Returns (new_state, response_text, emitted_signals).
    """
    current_id = session_state["current_node"]
    node = path["nodes"].get(current_id)
    if node is None:
        raise ValueError(f"Current node {current_id} not in path.nodes")

    # Merge node id into the node dict if not present (paths-as-examples store type/label only)
    node = dict(node)
    node.setdefault("id", current_id)
    node.setdefault("schema_version", "1.0")

    ntype = node.get("type")
    emitted: list[dict[str, Any]] = []

    if ntype == "qualify":
        return _handle_qualify(session_state, path, node, user_message, emitted)
    if ntype == "execute":
        return _handle_execute(session_state, path, node, emitted)
    if ntype == "gate":
        return _handle_gate(session_state, path, node, emitted)
    if ntype == "approval":
        return _handle_approval(session_state, path, node, user_message, emitted)
    if ntype == "close":
        return _handle_close(session_state, path, node, emitted)
    if ntype == "fork":
        raise NotImplementedError("fork nodes deferred per 04_BUILD_PLAN.md Section 4")

    raise ValueError(f"Unknown node type: {ntype}")


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _ensure_node_state(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    ns = state["node_states"].setdefault(node_id, {
        "status": "unqualified",
        "entered_at": _now(),
        "closed_at": None,
        "attempts": 0,
        "qualification_data": {},
        "action_results": {},
        "errors": [],
    })
    return ns


def _transition(state: dict[str, Any], path: dict[str, Any], from_id: str, condition: str) -> Optional[str]:
    """Pick the next node based on edges matching condition."""
    edges = [e for e in path.get("edges", []) if e.get("from") == from_id]
    # Exact match first, then 'default'
    matching = [e for e in edges if e.get("condition") == condition]
    if not matching:
        matching = [e for e in edges if e.get("condition") == "default"]
    if not matching:
        return None
    matching.sort(key=lambda e: e.get("priority", 0))
    return matching[0].get("to")


def _handle_qualify(state, path, node, user_message, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1

    # Seed user tier from the message if provided
    if user_message:
        # If there's exactly one missing key, attribute the message to it
        required_keys = [r.get("key") for r in (node.get("qualification") or {}).get("required") or []]
        missing = missing_keys(required_keys, state["context"])
        if len(missing) == 1:
            set_tier(state["context"], "user", missing[0], user_message.strip())

    # Run inference rules
    applied = apply_node_rules(node.get("inference_rules") or [], state["context"])
    state["metrics"]["total_inferences_made"] += len(applied)

    # Check if qualified now
    required_keys = [r.get("key") for r in (node.get("qualification") or {}).get("required") or []]
    missing = missing_keys(required_keys, state["context"])

    if not missing:
        ns["status"] = "qualified"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        # Promote all qualified keys to confirmed - the user supplied them
        # (directly or via initial_context, which is user-authored) and the
        # node's contract is satisfied. This is what makes them persistable
        # as preferences on close.
        for key in required_keys:
            promote_to_confirmed(state["context"], key)
        next_id = _transition(state, path, node["id"], "qualified") or _transition(state, path, node["id"], "default")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    # Still missing keys - compose a question
    text, tokens = compose(node, state)
    state["metrics"]["total_tokens"] += tokens
    state["metrics"]["total_questions_asked"] += 1 if "?" in text else 0
    return state, text, emitted


def _handle_execute(state, path, node, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1

    all_success = True
    last_error: str | None = None
    for action in node.get("actions") or []:
        action_id = action.get("id") or f"act_{uuid.uuid4().hex[:8]}"
        status = "success"
        result: dict = {}
        try:
            result = run_action(state, action)
        except ActionError as e:
            status = "failed"
            last_error = str(e)
            result = {"error": str(e)}
            all_success = False
        except Exception as e:  # defensive: bad handler shouldn't kill session
            status = "failed"
            last_error = f"{type(e).__name__}: {e}"
            result = {"error": last_error}
            all_success = False

        state["action_log"].append({
            "action_id": action_id,
            "node_id": node["id"],
            "type": action.get("type", "unknown"),
            "status": status,
            "executed_at": _now(),
            "result": result,
            "reversible": action.get("reversible", True),
            "reversed": False,
        })
        state["metrics"]["total_actions_fired"] += 1
        ns["action_results"][action_id] = result

        # Merge outputs into context.system tier so downstream gates can route on them.
        # system tier is informational and never overrides user intent.
        if isinstance(result, dict):
            for k, v in result.items():
                if k == "error":
                    continue
                set_tier(state["context"], "system", k, v)

        # Respect retry_strategy: for now, we don't auto-retry. 'retry' sets retry_requested.
        if not all_success and action.get("retry_strategy") == "none":
            break

    if not all_success:
        # Emit an error signal; block transition; stay on node.
        sig = signals.emit(
            source_layer="optogon",
            signal_type="error",
            priority="urgent",
            label=f"Execute failed at node {node.get('id')}",
            summary=last_error or "Action failed",
            data={"node_id": node["id"], "session_id": state["session_id"]},
            action_required=True,
            action_options=[
                {"id": "retry", "label": "Retry", "consequence": "run actions again", "risk_tier": "low"},
                {"id": "abandon", "label": "Abandon", "consequence": "close path as failed", "risk_tier": "low"},
            ],
        )
        emitted.append(sig)
        ns["status"] = "blocked"
        ns["errors"].append(last_error or "action failed")
        return state, "", emitted

    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1

    next_id = _transition(state, path, node["id"], "success") or _transition(state, path, node["id"], "default")
    if next_id:
        state["current_node"] = next_id
        _ensure_node_state(state, next_id)
    return state, "", emitted


def _handle_gate(state, path, node, emitted):
    ns = _ensure_node_state(state, node["id"])
    ns["attempts"] += 1
    # Evaluate the first true-branch edge; gates route silently.
    # For now: pick the highest-priority non-default edge whose condition expression
    # references only context. Safe eval via inference._safe_eval is reused.
    from .inference import _safe_eval  # local import to avoid cycles
    chosen_condition = None
    for edge in sorted(path.get("edges", []), key=lambda e: e.get("priority", 0)):
        if edge.get("from") != node["id"]:
            continue
        cond = edge.get("condition", "")
        if cond in ("", "default"):
            continue
        try:
            result = _safe_eval(cond, state["context"])
        except Exception:
            continue
        if result:
            chosen_condition = cond
            break
    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1

    next_id = _transition(state, path, node["id"], chosen_condition or "default")
    if next_id:
        state["current_node"] = next_id
        _ensure_node_state(state, next_id)
    return state, "", emitted


def _handle_approval(state, path, node, user_message, emitted):
    ns = _ensure_node_state(state, node["id"])

    # If user_message is an approval keyword, treat as resolved
    if user_message and user_message.strip().lower() in {"approve", "approved", "yes", "y", "confirm"}:
        ns["status"] = "closed"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        next_id = _transition(state, path, node["id"], "approved") or _transition(state, path, node["id"], "default")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    if user_message and user_message.strip().lower() in {"deny", "denied", "no", "n", "abandon"}:
        ns["status"] = "closed"
        ns["closed_at"] = _now()
        state["metrics"]["nodes_closed"] += 1
        next_id = _transition(state, path, node["id"], "denied") or _transition(state, path, node["id"], "abandon")
        if next_id:
            state["current_node"] = next_id
            _ensure_node_state(state, next_id)
        return state, "", emitted

    # First visit - emit approval signal, wait
    ns["status"] = "awaiting_approval"
    ns["attempts"] += 1
    sig = signals.emit(
        source_layer="optogon",
        signal_type="approval_required",
        priority="urgent",
        label=node.get("label", "Approval required"),
        summary=node.get("label", "Approval required"),
        data={"node_id": node["id"], "session_id": state["session_id"]},
        action_required=True,
        action_options=[
            {"id": "approve", "label": "Approve", "consequence": "Proceed with committed action", "risk_tier": "medium"},
            {"id": "deny", "label": "Deny", "consequence": "Abandon path", "risk_tier": "low"},
        ],
    )
    emitted.append(sig)
    text, tokens = compose(node, state)
    state["metrics"]["total_tokens"] += tokens
    return state, text, emitted


def _handle_close(state, path, node, emitted):
    """Close the session: build a CloseSignal and mark the session closed."""
    ns = _ensure_node_state(state, node["id"])
    ns["status"] = "closed"
    ns["closed_at"] = _now()
    state["metrics"]["nodes_closed"] += 1
    state["metrics"]["nodes_total"] = len(path.get("nodes", {}))

    # Build CloseSignal
    total_q = state["metrics"]["total_questions_asked"]
    total_inf = state["metrics"]["total_inferences_made"]
    accuracy = 1.0  # Phase 2 placeholder; Phase 4 measures actual
    time_to_close = 0.0
    try:
        started = datetime.fromisoformat(state.get("started_at", _now()).replace("Z", "+00:00"))
        time_to_close = (datetime.now(timezone.utc) - started).total_seconds()
    except Exception:
        pass

    # Build learned_preferences: confirmed values that are re-usable across runs.
    # Path-specific keys (those authors mark as non-shareable) should be excluded via
    # metadata; for now, include everything confirmed except transient per-run inputs.
    transient_keys = set((path.get("close_state", {}) or {}).get("transient_keys", []))
    learned_preferences: dict = {
        k: v for k, v in state["context"]["confirmed"].items() if k not in transient_keys
    }

    close_signal = {
        "schema_version": "1.0",
        "id": f"close_{uuid.uuid4().hex[:12]}",
        "session_id": state["session_id"],
        "path_id": state["path_id"],
        "closed_at": _now(),
        "status": "completed",
        "deliverables": [
            {"type": "confirmation", "label": "path closed", "value": True, "location": None},
        ],
        "session_summary": {
            "total_tokens": state["metrics"]["total_tokens"],
            "total_questions_asked": total_q,
            "total_inferences_made": total_inf,
            "inference_accuracy": accuracy,
            "nodes_closed": state["metrics"]["nodes_closed"],
            "nodes_total": state["metrics"]["nodes_total"],
            "time_to_close_seconds": time_to_close,
            "path_completion_rate": 1.0,
        },
        "decisions_made": [
            {"key": k, "value": v, "source": "user", "node_id": state["current_node"]}
            for k, v in state["context"]["confirmed"].items()
        ] + [
            {"key": k, "value": v, "source": "inferred", "node_id": state["current_node"]}
            for k, v in state["context"]["inferred"].items()
        ],
        "unblocked": [],
        "context_residue": {
            "confirmed": {k: v for k, v in state["context"]["confirmed"].items() if k not in transient_keys},
            "learned_preferences": learned_preferences,
        },
        "interrupt_log": [],
    }

    # Validate before emit
    from .contract_validator import validate
    validate(close_signal, "CloseSignal")

    # Phase 4: POST to delta-kernel so Atlas can persist preferences.
    # Fails silently if delta-kernel unreachable (dev mode).
    try:
        post_close_signal(close_signal)
    except Exception:
        pass

    sig = signals.emit(
        source_layer="optogon",
        signal_type="completion",
        priority="normal",
        label=f"Path {state['path_id']} closed",
        summary=f"Completed in {time_to_close:.1f}s, {total_q} questions asked",
        data={"close_signal_id": close_signal["id"]},
        task_id=state.get("task_id"),
    )
    emitted.append(sig)

    # Stash the close signal on the state for /session/{id} consumers
    state["_close_signal"] = close_signal
    state["current_node"] = node["id"]  # terminal
    return state, "", emitted

```


## CODE: optogon/action_handlers.py (real side effects)

*Source: `services/optogon/src/optogon/action_handlers.py`*

```python
"""Action handlers - real side-effect implementations for execute nodes.

Per doctrine/03_OPTOGON_SPEC.md Section 6 (execute node actions).

Registry pattern: paths reference action handlers by action.id. Each handler
receives the session state and the action dict, returns a dict of outputs
that get merged into the session context's 'system' tier so downstream
gates can route on them.

Safety rules:
- git_commit refuses if more than the expected file is staged
- read_file refuses paths outside the repo root unless absolute-allowed
- All handlers are deterministic where possible; retries are safe
"""
from __future__ import annotations
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from .config import REPO_ROOT

log = logging.getLogger("optogon.actions")


class ActionError(Exception):
    """Raised when an action fails in a way that should halt the node."""


HandlerResult = dict[str, Any]
Handler = Callable[[dict[str, Any], dict[str, Any]], HandlerResult]

_REGISTRY: dict[str, Handler] = {}


def register(action_id: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _REGISTRY[action_id] = fn
        return fn
    return deco


def get_handler(action_id: str) -> Handler | None:
    return _REGISTRY.get(action_id)


def _resolve_path(raw: str) -> Path:
    """Resolve a path. Relative paths are resolved against REPO_ROOT."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    else:
        p = p.resolve()
    return p


def _within_repo(p: Path) -> bool:
    try:
        p.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@register("read_content")
def read_content(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Read a file referenced by context.file_path. Stores content + metadata."""
    ctx = session_state["context"]
    file_path = (ctx["confirmed"].get("file_path")
                 or ctx["user"].get("file_path")
                 or ctx["system"].get("file_path"))
    if not file_path:
        raise ActionError("read_content: no file_path in context")
    p = _resolve_path(str(file_path))
    if not _within_repo(p):
        raise ActionError(f"read_content: path outside repo root: {p}")
    if not p.exists():
        return {
            "file_exists": False,
            "file_size": 0,
            "content": "",
            "resolved_path": str(p),
        }
    if not p.is_file():
        raise ActionError(f"read_content: not a file: {p}")
    content = p.read_text(encoding="utf-8")
    return {
        "file_exists": True,
        "file_size": p.stat().st_size,
        "file_size_ok": p.stat().st_size > 0,
        "content": content,
        "resolved_path": str(p),
    }


@register("scan_em_dashes")
def scan_em_dashes(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Count em-dashes in the read content. Per feedback_no_em_dashes_in_ui.md."""
    ctx = session_state["context"]
    content = ctx["system"].get("content")
    if content is None:
        # Also fall back to action_results in case a prior node stored it
        for node_id, results in session_state.get("node_states", {}).items():
            for _aid, result in (results.get("action_results") or {}).items():
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    break
            if content is not None:
                break
    if content is None:
        raise ActionError("scan_em_dashes: no content in context; run read_content first")

    # Count em-dashes (U+2014). Record line numbers.
    lines_with_em_dash: list[int] = []
    for i, line in enumerate((content or "").splitlines(), start=1):
        if "\u2014" in line:
            lines_with_em_dash.append(i)
    count = sum(line.count("\u2014") for line in (content or "").splitlines())
    return {
        "em_dash_count": count,
        "em_dash_lines": lines_with_em_dash,
        "em_dash_clean": count == 0,
    }


@register("git_commit")
def git_commit(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Git-commit the file at context.file_path with context.commit_message.

    Safety checks:
    - Refuses if repo has uncommitted changes to files OTHER than target
    - Uses `git add -- <file>` (explicit path)
    - Verifies only the target file is staged before commit
    - Runs with cwd = REPO_ROOT
    """
    ctx = session_state["context"]
    file_path = (ctx["confirmed"].get("file_path")
                 or ctx["user"].get("file_path"))
    commit_message = (ctx["confirmed"].get("commit_message")
                      or ctx["user"].get("commit_message"))
    if not file_path or not commit_message:
        raise ActionError("git_commit: missing file_path or commit_message")

    p = _resolve_path(str(file_path))
    if not _within_repo(p):
        raise ActionError(f"git_commit: path outside repo: {p}")

    dry_run = bool((action.get("spec") or {}).get("dry_run", False))

    rel_path = str(p.relative_to(REPO_ROOT)).replace("\\", "/")

    def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        log.debug("git %s (cwd=%s)", " ".join(args), REPO_ROOT)
        return subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=check,
        )

    # 1. Pre-check: find currently staged files; abort if anything else is staged
    staged = run_git(["diff", "--cached", "--name-only"], check=False).stdout.splitlines()
    unexpected = [s for s in staged if s and s.strip() != rel_path]
    if unexpected:
        raise ActionError(f"git_commit: other files are staged, refusing: {unexpected}")

    if dry_run:
        return {
            "dry_run": True,
            "would_commit": rel_path,
            "commit_message": commit_message,
            "commit_success": False,
            "commit_sha": None,
        }

    # 2. Stage only the target file
    run_git(["add", "--", rel_path])

    # 3. Verify staging is exactly the target
    staged_after = run_git(["diff", "--cached", "--name-only"], check=False).stdout.splitlines()
    if staged_after != [rel_path]:
        # Unstage to avoid leaving the repo in a weird state
        run_git(["reset", "--", rel_path], check=False)
        raise ActionError(f"git_commit: staging mismatch (got {staged_after}), refusing")

    # 4. Commit
    commit = run_git(["commit", "-m", commit_message], check=False)
    if commit.returncode != 0:
        raise ActionError(f"git_commit: commit failed: {commit.stderr or commit.stdout}")

    # 5. Grab SHA
    sha = run_git(["rev-parse", "HEAD"], check=False).stdout.strip()
    return {
        "commit_success": True,
        "commit_sha": sha,
        "committed_path": rel_path,
        "commit_message": commit_message,
        "dry_run": False,
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run_action(session_state: dict[str, Any], action: dict[str, Any]) -> HandlerResult:
    """Look up and invoke the handler for action.id. Returns result dict."""
    action_id = action.get("id")
    if not action_id:
        raise ActionError("action missing id")
    handler = get_handler(action_id)
    if handler is None:
        # Unknown action - fall back to stub so unregistered paths still "work"
        log.warning("no handler registered for action id=%s; stubbing", action_id)
        return {"stub": True}
    return handler(session_state, action)

```


## PATH: commit_a_file.json (first real path)

*Source: `services/optogon/paths/commit_a_file.json`*

```json
{
  "schema_version": "1.0",
  "id": "commit_a_file",
  "name": "Commit a file",
  "version": "1.0",
  "description": "Reads a file, scans it for em dashes, asks for approval, commits with a user-supplied message. Real side effects.",
  "entry": {
    "node_id": "entry",
    "match_conditions": [
      { "signal": "intent", "operator": "contains", "value": "commit file" }
    ],
    "match_threshold": 0.6,
    "tie_break": "priority"
  },
  "nodes": {
    "entry": {
      "type": "qualify",
      "label": "Gather file_path and commit_message",
      "qualification": {
        "required": [
          { "key": "file_path", "source": "user", "description": "Repo-relative path to the file" },
          { "key": "commit_message", "source": "user", "description": "Conventional-commit message" }
        ],
        "question": {
          "text": "Which file should I commit, and what is the commit message?",
          "purpose": ["identify file", "identify message"],
          "max_asks": 1
        },
        "max_missing_keys_before_split": 2
      },
      "metadata": { "token_budget": 120, "tags": ["commit_a_file"] }
    },
    "read_file": {
      "type": "execute",
      "label": "Read file content",
      "actions": [
        { "id": "read_content", "type": "retrieval", "trigger": "on_entry", "reversible": true, "risk_tier": "low", "retry_strategy": "none" }
      ]
    },
    "validate_file": {
      "type": "gate",
      "label": "Ensure file exists and has content"
    },
    "em_dash_scan": {
      "type": "execute",
      "label": "Scan for em dashes",
      "actions": [
        { "id": "scan_em_dashes", "type": "transform", "trigger": "on_entry", "reversible": true, "risk_tier": "low", "retry_strategy": "none" }
      ]
    },
    "em_dash_gate": {
      "type": "gate",
      "label": "Gate: no em dashes allowed in committed content"
    },
    "approve": {
      "type": "approval",
      "label": "Approve commit",
      "contract": { "required_outputs": ["decision"], "completion_criteria": "user decision received", "failure_mode": "abort" }
    },
    "commit": {
      "type": "execute",
      "label": "Git commit the file",
      "actions": [
        { "id": "git_commit", "type": "side_effect", "trigger": "on_entry", "reversible": false, "risk_tier": "medium", "retry_strategy": "none", "spec": { "dry_run": false } }
      ]
    },
    "done": {
      "type": "close",
      "label": "Emit CloseSignal with commit SHA",
      "contract": { "required_outputs": ["commit_sha"], "completion_criteria": "commit landed", "failure_mode": "escalate" }
    }
  },
  "edges": [
    { "from": "entry", "to": "read_file", "condition": "qualified", "priority": 1 },
    { "from": "read_file", "to": "validate_file", "condition": "success", "priority": 1 },
    { "from": "validate_file", "to": "em_dash_scan", "condition": "system.get('file_exists') and system.get('file_size_ok')", "priority": 1 },
    { "from": "validate_file", "to": "done", "condition": "default", "priority": 2 },
    { "from": "em_dash_scan", "to": "em_dash_gate", "condition": "success", "priority": 1 },
    { "from": "em_dash_gate", "to": "approve", "condition": "system.get('em_dash_clean')", "priority": 1 },
    { "from": "em_dash_gate", "to": "done", "condition": "default", "priority": 2 },
    { "from": "approve", "to": "commit", "condition": "approved", "priority": 1 },
    { "from": "approve", "to": "done", "condition": "denied", "priority": 2 },
    { "from": "commit", "to": "done", "condition": "success", "priority": 1 }
  ],
  "close_state": {
    "description": "File committed (or abandoned cleanly)",
    "deliverables": ["commit_sha"],
    "transient_keys": ["file_path", "commit_message"]
  },
  "defaults": {
    "pacing": { "max_options_shown": 3, "bundle_confirmations": true },
    "inference_confidence_floor": 0.7
  }
}

```


---

*End of audit bundle.*

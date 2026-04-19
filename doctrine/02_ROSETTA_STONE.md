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

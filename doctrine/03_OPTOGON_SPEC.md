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

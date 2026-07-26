# Atlas Consolidation — Fable Operating Runbook (token-cheap delegation)

**Pairs with:** `ATLAS_CONSOLIDATION_PRESEARCH.md` (the map) + fest `atlas-consolidation-AC0002` (the what).
**This doc = the HOW:** how Fable executes the fest *without coding and without burning tokens*.

---

## The rule of the harness

> **Fable looks and reasons. Fable never codes. Cheap tiers do the work.**

- **Fable (eyes + brain)** drives the deterministic recon stack — `/bearings`, `/delta-scp`, `/code-recon`, `/groundwork`, `/seam`. These run CLI tools (es, rg, ast-grep, git) and return tight evidence, so Fable *looks precisely* instead of reading whole files. Reasoning + routing is the only generation Fable does.
- **Sonnet (hands — real code)** executes TS/Python changes: edits, new scripts, wiring.
- **Haiku (hands — mechanical)** executes deletes, `.gitignore` edits, scheduled-task tweaks, doc regeneration.
- **Fable writes zero implementation.** If a task needs code, Fable hands a precise brief to Sonnet/Haiku and verifies the result.

**Token economy:** the expensive act (writing code) is always the cheapest tier; the expensive model (Fable) only does what deterministic tools + judgment require. Recon is tool-bound, not token-bound.

---

## The loop (run per task)

```
1. LOOK   Fable runs the assigned recon tool (see itinerary) to confirm the file:line anchor
          and gather the exact evidence. Cheap: es/rg/ast-grep do the work, not a file dump.
2. REASON Fable decides the exact change (or: is this blocked by a deferred decision?).
          This is the only step where Fable "thinks" — the point of using Fable at all.
3. DELEGATE Fable spawns a worker at the assigned tier (Haiku|Sonnet) with a SELF-CONTAINED brief:
          the file:line, the exact change, and the tool-provable Done-When from the task file.
4. VERIFY Fable runs `/groundwork verify` (code-recon verify mode) against the Done-When.
          Only on proof → `fest task complete`. No proof → bounce back to the worker.
```

**Session bookends:** start each wave-session with `/bearings` (where am I, what changed) and one `/seam` perceive pass over the repo to seed content-addressed receipts the recon tools reuse.

---

## Tier rules (how Fable routes step 3)

| Route to | When | Examples in this fest |
|---|---|---|
| **Haiku** | Mechanical, low-ambiguity, no design judgment | delete files, edit `.gitignore`, un/re-register a scheduled task, regenerate a doc from a list |
| **Sonnet** | Real code with local judgment | edit `.ts`/`.py`, write a PowerShell script with logic, rewire a data source |
| **Fable (no delegation)** | Pure reasoning / a decision gate | pick the canonical pipeline trigger; resolve the two-repo split; finish-vs-shelve a partial |

**Escalation, not default:** start a task at the lowest plausible tier. Only escalate Haiku→Sonnet if the worker hits real ambiguity. Never escalate to Fable-as-coder — Fable re-scopes and re-delegates instead.

---

## The itinerary (per-task routing)

Legend — **Eyes** = recon tool Fable uses to look · **Hands** = executor tier · **Mode**: `DO` (execute now) · `GATE` (blocked on a deferred decision).

### Wave 0 — litter (zero code risk, fully parallel)
| Task | Eyes (look) | Hands (do) | Mode | Note |
|---|---|---|---|---|
| 0.1 root litter sweep | `es` / `git status` | **Haiku** | DO | verify untracked before delete |
| 0.2 gitignore blobs | `git check-ignore` | **Haiku** | DO | ignore only, keep generators |
| 0.3 reap orphans | (none) | **Sonnet** | DO | script has process-match logic |
| 0.4 fix optogon task | `Get-ScheduledTask` | **Haiku** | DO | repoint or unregister |

### Wave 1 — visibility
| Task | Eyes | Hands | Mode | Note |
|---|---|---|---|---|
| 1.1 daemon on/off switch | `/code-recon locate` server.ts:81 | **Sonnet** | DO | env-gate; default posture is decision #3 |
| 1.2 dedup morning pipeline | `/code-recon trace` run_daily.py vs cycleboard_push.py | **Fable→Sonnet** | DO | Fable picks canonical trigger, Sonnet disables the rest |
| 1.3 unified status surface | `/code-recon` status_atlas.ps1 + atlas_status | **Sonnet** | DO | reuse 0.3 orphan logic |
| 1.4 rationalize launch/spam | `/code-recon` read start.bat files | **Haiku + Sonnet** | DO | Haiku prunes launch.json; Sonnet rewrites start.bat |

### Wave 2 — maps (intra-wave order: 2.1 → 2.2 → 2.3; 2.4 parallel)
| Task | Eyes | Hands | Mode | Note |
|---|---|---|---|---|
| 2.1 canonical inventory | `/delta-scp` shape + `/code-recon` build_system_index.py | **Sonnet** | DO | exclude vendored blob; fix port bug |
| 2.2 collapse map/wall forks | `/code-recon` confirm root reads live | **Haiku** | DO | confirm-before-delete |
| 2.3 point views at gateway | `/code-recon` gateway endpoints | **Sonnet** | DO | rewire to :3072 |
| 2.4 quarantine scaffolding | `/code-recon prior-art` (es machine-wide) | **Sonnet** | DO | tag+delete vs exclude = decision #4 |

### Wave 3 — harness
| Task | Eyes | Hands | Mode | Note |
|---|---|---|---|---|
| 3.1 enable ui invocation | `/code-recon` gateway.py 422 path | **Sonnet** | DO | the keystone brick |
| 3.2 refresh docs to 40 | `atlas_describe_list()` | **Haiku** | DO | regenerate list, edit 3 docs |
| 3.3 resolve two-repo split | `/groundwork brownfield` on `C:\Users\bruke\atlas` | **Fable→Sonnet** | GATE | blocked on decision #1 |
| 3.4 finish/shelve partials | `/code-recon` each partial | **Fable→Sonnet/Haiku** | GATE | Fable judges finish-vs-shelve per service |

---

## Machine-readable itinerary

```json
{
  "festival": "atlas-consolidation-AC0002",
  "orchestrator": "fable",
  "orchestrator_role": "recon+reason+route+verify; never codes",
  "recon_tools": ["/bearings", "/delta-scp", "/code-recon", "/groundwork", "/seam"],
  "verify_gate": "/groundwork verify (code-recon verify) against each task Done-When before fest task complete",
  "tasks": [
    {"id":"0.1","seq":"01_wave0_litter","eyes":["es","git status"],"hands":"haiku","mode":"do"},
    {"id":"0.2","seq":"01_wave0_litter","eyes":["git check-ignore"],"hands":"haiku","mode":"do"},
    {"id":"0.3","seq":"01_wave0_litter","eyes":[],"hands":"sonnet","mode":"do"},
    {"id":"0.4","seq":"01_wave0_litter","eyes":["Get-ScheduledTask"],"hands":"haiku","mode":"do"},
    {"id":"1.1","seq":"02_wave1_visibility","eyes":["code-recon:locate server.ts:81"],"hands":"sonnet","mode":"do","decision":"#3 sets default only"},
    {"id":"1.2","seq":"02_wave1_visibility","eyes":["code-recon:trace run_daily.py|cycleboard_push.py"],"hands":"fable->sonnet","mode":"do"},
    {"id":"1.3","seq":"02_wave1_visibility","eyes":["code-recon:status_atlas.ps1+atlas_status"],"hands":"sonnet","mode":"do"},
    {"id":"1.4","seq":"02_wave1_visibility","eyes":["code-recon:start.bat"],"hands":"haiku+sonnet","mode":"do"},
    {"id":"2.1","seq":"03_wave2_maps","eyes":["delta-scp","code-recon:build_system_index.py"],"hands":"sonnet","mode":"do"},
    {"id":"2.2","seq":"03_wave2_maps","eyes":["code-recon:confirm-live-read"],"hands":"haiku","mode":"do"},
    {"id":"2.3","seq":"03_wave2_maps","eyes":["code-recon:gateway-endpoints"],"hands":"sonnet","mode":"do"},
    {"id":"2.4","seq":"03_wave2_maps","eyes":["code-recon:prior-art"],"hands":"sonnet","mode":"do","decision":"#4 delete-vs-quarantine"},
    {"id":"3.1","seq":"04_wave3_harness","eyes":["code-recon:gateway.py-422"],"hands":"sonnet","mode":"do"},
    {"id":"3.2","seq":"04_wave3_harness","eyes":["atlas_describe_list"],"hands":"haiku","mode":"do"},
    {"id":"3.3","seq":"04_wave3_harness","eyes":["groundwork:brownfield C:/Users/bruke/atlas"],"hands":"fable->sonnet","mode":"gate","decision":"#1 merge/declare/retire"},
    {"id":"3.4","seq":"04_wave3_harness","eyes":["code-recon:each-partial"],"hands":"fable->sonnet|haiku","mode":"gate","decision":"finish-vs-shelve per service"}
  ]
}
```

---

## Two ways to run the hands (pick one — see the open question)

- **A · Native Claude Code subagents (recommended).** Fable runs as the session; each `do` task is an `agent(brief, {model:"haiku"|"sonnet"})` call (Workflow tool) or a subagent (Agent tool). Model overrides are built in; tokens metered under your account; no new infra. This is what "offload to Fable to fan out" naturally means.
- **B · Standalone Python agent itinerary.** A `orchestrate.py` reads `routing.json`, calls the recon tools, and dispatches Haiku/Sonnet workers via the API (like `binre orchestrate` / `seam`). Headless + schedulable, but new infra to build and maintain.

Either way, the itinerary above is the contract. Wave 0 is safe to start immediately.

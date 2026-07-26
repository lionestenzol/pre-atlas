# Manual Orchestration Trial · ORDERING D · HYBRID

You are running ORDERING D of a manual 4-trial skill-invocation experiment. Working directory: `C:\Users\bruke\Pre Atlas`. Treat this prompt as your full context — you have no memory of prior conversations.

## Task

Trace Signal.v1 emission and consumption inside `services/droplist`. Find emit, consume, drift. Cite file:line. Stay within `services/droplist`.

## REQUIRED skill invocations (the whole point of this trial)

You MUST literally invoke both skills via the `Skill` tool. Failing to invoke them invalidates the trial.

- **Phase 1 (MAP):** call `Skill({skill: "delta-scp", args: "services/droplist"})`. After the call, print exactly: `[SKILL INVOKED: delta-scp]`
- **Phase 3 (VERIFY):** invoke `Skill({skill: "code-recon", args: "verify: <claim>"})` for AT LEAST 3 load-bearing claims (one from each map slice you investigate). After each call, print exactly: `[SKILL INVOKED: code-recon]`

If a skill returns an error or is unavailable, document the error verbatim — do NOT silently fall back.

## Ordering D phases

**Phase 1 — MAP:** Invoke `delta-scp` on `services/droplist`. Use the symbolic skeleton to scope the slices.

**Phase 2 — PARALLEL on map slices:** Using the map to scope, do 4 logically-independent investigations:
- Slice 1: emission paths
- Slice 2: consumption paths
- Slice 3: schemas/contracts
- Slice 4: tests

**Phase 3 — VERIFY:** Pick the top load-bearing claim from each slice (4 claims) and invoke `code-recon` on each.

**Phase 4 — REPORT** to `experiments/manual-skill-trial/results/D-report.md`.

## Report template

```markdown
# Trial D · Hybrid · Manual skill trial

## Skill invocation log
- [ ] delta-scp invoked: yes/no (paste raw output excerpt)
- [ ] code-recon invoked: N times (list claims verified, by slice)

## Map phase
delta-scp skeleton output excerpt:
[paste]

## Parallel slices
- Slice 1 (emission) findings: N
- Slice 2 (consumption) findings: N
- Slice 3 (schemas) findings: N
- Slice 4 (tests) findings: N

## Verify phase
- Verified: N
- Dropped: N (with reason)

## Emit sites (verified)
| file | line | snippet | confidence |
|---|---|---|---|

## Consume sites (verified)
| file | line | snippet | confidence |
|---|---|---|---|

## Drift findings
1. <description>  
   Evidence: <file:line vs file:line>  
   Verified by code-recon: yes/no

## Claims with evidence: N
## Claims without evidence: N

## Self assessment
- What was easy:
- What was hard:
- What did the skills add over base Glob/Grep:
- Did combining the skills (scp + recon) produce findings neither alone would have caught? Explain:
- What might be missed:
- Confidence: high/medium/low

## Tool calls: N (with breakdown by tool name)
## Wall-clock: M minutes
```

## Hard rules

- Do NOT touch any file outside `experiments/manual-skill-trial/results/`.
- Do NOT open a PR or git commit.
- Do NOT chase into services/delta-kernel or apps/inpact.
- Do NOT silently fall back if a skill fails — document the failure.

End your final message with exactly: `MANUAL TRIAL D COMPLETE`

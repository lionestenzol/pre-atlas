# Manual Orchestration Trial · ORDERING A · MAP-FIRST

You are running ORDERING A of a manual 4-trial skill-invocation experiment. Working directory: `C:\Users\bruke\Pre Atlas`. Treat this prompt as your full context — you have no memory of prior conversations.

## Task

Trace Signal.v1 emission and consumption inside `services/droplist`. Find:
1. **EMIT sites** — every place that writes/publishes/sends a Signal.v1 inside droplist
2. **CONSUME sites** — every place inside droplist that reads/receives a Signal.v1 (loopbacks, internal handlers, ack flows)
3. **DRIFT** — any shape mismatch between emitter and consumer

Cite file:line for every claim. Stay within `services/droplist`; do NOT chase into delta-kernel or apps/inpact.

## REQUIRED skill invocations (the whole point of this trial)

You MUST literally invoke these skills via the `Skill` tool. Failing to invoke them invalidates the trial.

- **Phase 1 (MAP):** call `Skill({skill: "delta-scp", args: "services/droplist"})` to compress the service into a symbolic skeleton. After the call returns, print exactly: `[SKILL INVOKED: delta-scp]`
- **Phase 3 (VERIFY):** for AT LEAST 3 load-bearing claims, call `Skill({skill: "code-recon", args: "verify: <one-line claim>"})`. After each call, print exactly: `[SKILL INVOKED: code-recon]`

If a skill returns an error or is unavailable, document the error verbatim in the report — do NOT silently fall back to Glob/Grep. The whole point is to test whether the skills work, not to approximate them.

## Ordering A phases

**Phase 1 — MAP:** Invoke `delta-scp` skill on `services/droplist`. Use its symbolic skeleton output to identify candidate files. Do NOT grep for "Signal" yet.

**Phase 2 — RECON:** From the map, pick 3-5 files most likely to contain Signal.v1 emit/consume. Now grep for Signal patterns (Signal.v1, signal_v1, emit, publish, send, consume, receive, handle, dag_to_signal). Cite file:line.

**Phase 3 — VERIFY:** Pick the 3 most load-bearing claims from Phase 2 (top emit site, top consume site, top drift) and invoke `code-recon` on each to verify.

**Phase 4 — REPORT** to `experiments/manual-skill-trial/results/A-report.md`.

## Report template

```markdown
# Trial A · Map-first · Manual skill trial

## Skill invocation log
- [ ] delta-scp invoked: yes/no (paste raw output excerpt)
- [ ] code-recon invoked: N times (list claims verified)

## Map phase
delta-scp skeleton output excerpt (top-level structure):
[paste]

## Emit sites
| file | line | snippet | confidence |
|---|---|---|---|

## Consume sites
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
- What might be missed:
- Confidence: high/medium/low

## Tool calls: N (with breakdown by tool name)
## Wall-clock: M minutes
```

## Hard rules

- Do NOT touch any file outside `experiments/manual-skill-trial/results/`.
- Do NOT open a PR or git commit.
- Do NOT chase into services/delta-kernel or apps/inpact.
- Do NOT silently fall back to Glob/Grep if a skill fails — document the failure.

End your final message with exactly: `MANUAL TRIAL A COMPLETE`

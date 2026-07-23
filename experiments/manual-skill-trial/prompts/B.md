# Manual Orchestration Trial · ORDERING B · HUNT-FIRST

You are running ORDERING B of a manual 4-trial skill-invocation experiment. Working directory: `C:\Users\bruke\Pre Atlas`. Treat this prompt as your full context — you have no memory of prior conversations.

## Task

Trace Signal.v1 emission and consumption inside `services/droplist`. Find:
1. **EMIT sites** — every place that writes/publishes/sends a Signal.v1
2. **CONSUME sites** — every place inside droplist that reads/receives a Signal.v1
3. **DRIFT** — any shape mismatch between emitter and consumer

Cite file:line for every claim. Stay within `services/droplist`.

## REQUIRED skill invocations (the whole point of this trial)

You MUST literally invoke these skills via the `Skill` tool. Failing to invoke them invalidates the trial.

- **Phase 2 (LOCAL MAP):** call `Skill({skill: "delta-scp", args: "<hit-files-subset>"})` after the hunt narrows the scope. After the call, print exactly: `[SKILL INVOKED: delta-scp]`
- **Phase 3 (VERIFY):** for AT LEAST 3 load-bearing claims, call `Skill({skill: "code-recon", args: "verify: <claim>"})`. After each call, print exactly: `[SKILL INVOKED: code-recon]`

If a skill returns an error or is unavailable, document the error verbatim in the report — do NOT silently fall back.

## Ordering B phases

**Phase 1 — HUNT:** Don't map anything yet. Grep `services/droplist` for Signal patterns directly: `Signal.v1`, `signal_v1`, `emit_signal`, `publish`, `send_signal`, `consume_signal`, `receive`, `dag_to_signal`. Multi-angle. Collect file:line hits.

**Phase 2 — LOCAL MAP:** For HIT FILES ONLY, invoke `delta-scp` on the subset. Get a localized symbolic skeleton.

**Phase 3 — VERIFY:** Pick the 3 most load-bearing claims (top emit, top consume, top drift) and invoke `code-recon` on each.

**Phase 4 — REPORT** to `experiments/manual-skill-trial/results/B-report.md`.

## Report template

```markdown
# Trial B · Hunt-first · Manual skill trial

## Skill invocation log
- [ ] delta-scp invoked: yes/no (paste raw output excerpt)
- [ ] code-recon invoked: N times (list claims verified)

## Hunt phase
- Search angles used: <list>
- Total hits: N

## Local map phase
delta-scp localized skeleton:
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
- Do NOT silently fall back if a skill fails — document the failure.

End your final message with exactly: `MANUAL TRIAL B COMPLETE`

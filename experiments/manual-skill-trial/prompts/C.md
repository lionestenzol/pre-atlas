# Manual Orchestration Trial · ORDERING C · SWEEP-FIRST

You are running ORDERING C of a manual 4-trial skill-invocation experiment. Working directory: `C:\Users\bruke\Pre Atlas`. Treat this prompt as your full context — you have no memory of prior conversations.

## Task

Trace Signal.v1 emission and consumption inside `services/droplist`. Find emit, consume, drift. Cite file:line. Stay within `services/droplist`.

## REQUIRED skill invocations (the whole point of this trial)

You MUST literally invoke `code-recon` via the `Skill` tool — the verify gate IS this ordering's whole personality. Failing to invoke it invalidates the trial.

- **Phase 2 (VERIFY):** invoke `Skill({skill: "code-recon", args: "verify: <claim>"})` for **every** load-bearing claim from the sweep. After each call, print exactly: `[SKILL INVOKED: code-recon]`
- **Optional but encouraged**: invoke `Skill({skill: "delta-scp", ...})` if you reach a point where a symbolic skeleton would help disambiguate. Note when you don't reach for it.

Strict gate: if a claim does not survive `code-recon` verification, **DROP it from the final report**. Be brutally honest about what died at verify.

## Ordering C phases

**Phase 1 — SWEEP:** Do 4 logically-independent investigations (don't let findings from one inform another's search):
- Investigation 1: emission sites (emit/publish/send/post patterns)
- Investigation 2: consumption sites (read/receive/handle/subscribe patterns)
- Investigation 3: schema/type defs for Signal.v1
- Investigation 4: tests exercising Signal flow

Pool findings. Note duplicates across investigations.

**Phase 2 — VERIFY:** Invoke `code-recon` on every load-bearing claim from the sweep. Mark each VERIFIED / UNVERIFIED / REFUTED. Drop everything that doesn't survive.

**Phase 3 — REPORT** to `experiments/manual-skill-trial/results/C-report.md`. Be brutally honest about which claims didn't survive verification.

## Report template

```markdown
# Trial C · Sweep-first · Manual skill trial

## Skill invocation log
- [ ] delta-scp invoked: yes/no/N-A (with reason)
- [ ] code-recon invoked: N times (one per load-bearing claim)

## Sweep phase
- Inv 1 hits: N
- Inv 2 hits: N
- Inv 3 hits: N
- Inv 4 hits: N
- Total before verify: N

## Verify phase
- Verified: N
- Unverified (dropped): N (list with reason)
- Refuted (dropped): N (list with reason)

## Emit sites (verified only)
| file | line | snippet | confidence |
|---|---|---|---|

## Consume sites (verified only)
| file | line | snippet | confidence |
|---|---|---|---|

## Drift findings
1. <description>  
   Evidence: <file:line vs file:line>  
   code-recon verdict: VERIFIED/UNVERIFIED/REFUTED

## Claims with evidence: N
## Claims without evidence: 0 (gate should enforce)

## Self assessment
- What was easy:
- What was hard:
- What did code-recon add over manual 2-angle verification:
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

End your final message with exactly: `MANUAL TRIAL C COMPLETE`

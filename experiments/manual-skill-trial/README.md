# Manual Skill-Invocation Trial · Handoff Package

## What this is

4 self-contained prompts (A, B, C, D) — one per orchestration ordering — that you paste into 4 **fresh** Claude Code windows. Each session is independent. Each MUST literally invoke `Skill({skill: "delta-scp"})` and `Skill({skill: "code-recon"})` — that's the whole point of this trial (the prior 3 runs never actually invoked the skills).

## How to run

For each ordering:

1. Open a fresh Claude Code window in `C:\Users\bruke\Pre Atlas`
2. Open the corresponding prompt file:
   - [prompts/A.md](prompts/A.md) — map-first
   - [prompts/B.md](prompts/B.md) — hunt-first
   - [prompts/C.md](prompts/C.md) — sweep-first
   - [prompts/D.md](prompts/D.md) — hybrid
3. Copy its **entire** contents into the new window as your first message
4. Let the session run. It will write its report to `results/X-report.md`
5. When done, the session will print `MANUAL TRIAL X COMPLETE`

Run all 4 in parallel (4 windows open at once) or sequentially — your call.

## Verifying skills actually got invoked

Each prompt requires the session to print exactly `[SKILL INVOKED: delta-scp]` and `[SKILL INVOKED: code-recon]` after each call. After the trials finish, check the report files for those markers. If they're missing, the skill wasn't called — that trial is invalid.

You can also grep transcripts:

```
es "[SKILL INVOKED" results/*.md
```

## Comparing results

After all 4 finish, the reports are at:

- `results/A-report.md`
- `results/B-report.md`
- `results/C-report.md`
- `results/D-report.md`

Compare emit counts, consume counts, drifts, and self-assessment between them.

## Task (same for all 4)

Trace Signal.v1 emission and consumption inside `services/droplist`. Find emit sites, consume sites, shape drift. Cite file:line. Stay within `services/droplist`.

Different orderings, same target.

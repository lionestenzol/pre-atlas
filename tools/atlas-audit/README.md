# Atlas Audit

Runs the DropList Search Tightening Protocol against Atlas-the-system on a schedule. Surfaces drift that would otherwise rot in the working tree (uncommitted doctrine, partial FSM coverage, missing state fields, schrödinger imports, broken Windows-reserved files, untested critical layers).

Pairs with [docs/search-protocol.md](../../docs/search-protocol.md) and the global skill at `~/.claude/skills/repo-search/SKILL.md`.

## What it checks

Six checks today. Adding new ones is one bash function in [`audit.sh`](audit.sh).

| # | Check | Severity | Detects |
|---|---|---|---|
| 1 | Reserved Windows device-name files | BLOCKER | `NUL`, `CON`, `PRN`, `AUX`, `COM1-3`, `LPT1-2` literal filenames |
| 2 | Imported but untracked | BLOCKER | `import X from '../atlas/Y'` where `Y.ts` isn't `git ls-files`'d |
| 3 | Mode FSM `Record<Mode, ...>` partial coverage | HIGH | Records missing some of the 6 modes — runtime `undefined` |
| 4 | Atlas TS layer test coverage | HIGH | >100 LOC of atlas/ code with zero test files |
| 5 | `mode_since` missing from `governance_state.json` | MED | Cockpit can't honestly report mode duration |
| 6 | Uncommitted long markdown in core paths | HIGH | Doctrine docs (>100 lines) that only exist in working tree |

## Usage

```bash
bash tools/atlas-audit/audit.sh
```

Writes to `tools/atlas-audit/runs/` (gitignored):

- `findings-<UTC-date>.json` — JSONL, one finding per line
- `report-<UTC-date>.md` — human-readable summary + diff vs previous run
- `snapshot-<UTC-date>.json` — raw snapshot for next-run diff

**Exit code = count of NEW findings since the most recent prior run.** `0` is the clean signal a scheduler can act on.

## Scheduling

### Windows Task Scheduler

```powershell
$action = New-ScheduledTaskAction `
  -Execute "C:\Program Files\Git\bin\bash.exe" `
  -Argument "-lc 'cd \"C:/Users/bruke/Pre Atlas\" && bash tools/atlas-audit/audit.sh'"
$trigger = New-ScheduledTaskTrigger -Daily -At 7am
Register-ScheduledTask -TaskName "AtlasAudit" -Action $action -Trigger $trigger
```

### macOS / Linux cron

```cron
0 7 * * * cd /path/to/repo && bash tools/atlas-audit/audit.sh
```

### Atlas-aware (when Atlas is running)

Post-process the JSONL into directives:

```bash
bash tools/atlas-audit/audit.sh
jq -c 'select(.severity=="BLOCKER" or .severity=="HIGH") |
  {type: "fix", label: .subject, description: .message, leverage_score: 0.9}' \
  tools/atlas-audit/runs/findings-$(date -u +%F).json |
while read d; do
  curl -s -X POST localhost:3001/api/atlas/directives -d "$d"
done
```

## Reading a report

The `report-<date>.md` opens with a one-line tally:

```
Findings: 3 (0 BLOCKER, 2 HIGH, 1 MED)
New since previous run (findings-2026-06-06.json): 1
```

Then lists findings grouped by severity, then a `diff` block of the snapshot vs the previous day's snapshot — so you see *what changed* in Atlas-substrate shape, not just "what's there today."

## Extending

Adding a check is one bash function that calls `emit <severity> <check_id> <subject> <message>`. The `emit` helper composes the JSONL line and appends to `$FINDINGS`. Keep checks independent — each one should run in under a second and not depend on others.

Common shapes:

```bash
# A "find me X in the tree" check
while IFS= read -r f; do
  emit HIGH my_check "$f" "Reason"
done < <(fd <pattern> services/ 2>/dev/null)

# A "schema vs code" check
expected=$(jq -r '.properties.foo.enum[]' contracts/schemas/X.json)
actual=$(rg -o "type: '[^']+'" services/.../emitter.ts)
diff <(echo "$expected" | sort) <(echo "$actual" | sort) | \
  while read line; do emit HIGH schema_drift "X" "$line"; done
```

## Why JSONL and snapshot files

- **JSONL findings** = `comm`-able for diff, `jq`-able for queries, append-only friendly.
- **Markdown report** = the human surface. Open it in `bat` for highlighted reading.
- **Snapshot file** = the stable representation of "what Atlas-substrate looks like today" so a `diff` between two days surfaces *change*, which is more actionable than absolute state.

This is the 5-layer epistemics stack applied to itself: tools produce snapshots, snapshots compose into deltas, deltas become directives, directives become action.

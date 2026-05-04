# Thread Lifecycle

Every thread (ChatGPT conversation) has two orthogonal axes:

- **Verdict** — what it is: `MINE`, `KEEP`, `CLOSE`, `ARCHIVE`, `REVIEW`, `DROP`
- **Status** — how far through its lifecycle: `HARVESTED`, `PLANNED`, `BUILDING`, `REVIEWING`, `DONE`, `RESOLVED`, `DROPPED`

`thread_decisions.json` holds the verdict. `harvest/<id>_<slug>/manifest.json` holds the status (source of truth).

## States

| Status | Meaning | Next command |
|---|---|---|
| (no manifest) | not harvested yet | `atl harvest --convo <id>` |
| `HARVESTED` | concepts extracted; no scope yet | `atl plan <id>` |
| `PLANNED` | `build_plan.json` written (MUST/NICE/SKIP) | `atl start <id>` |
| `BUILDING` | artifact path recorded, build in progress | `atl review <id>` |
| `REVIEWING` | coverage computed, gate evaluated | `atl done <id>` |
| `DONE` | MINE shipped with artifact + coverage pass | (terminal) |
| `RESOLVED` | CLOSE verdict terminal (no artifact) | (terminal) |
| `DROPPED` | ARCHIVE verdict terminal (no artifact) | (terminal) |

## Allowed transitions

```
HARVESTED  -> PLANNED | RESOLVED | DROPPED
PLANNED    -> BUILDING | RESOLVED | DROPPED
BUILDING   -> REVIEWING | DROPPED
REVIEWING  -> DONE | BUILDING | DROPPED
DONE/RESOLVED/DROPPED -> (terminal)
```

Illegal transitions raise `LifecycleError`. `atl done --force` bypasses the coverage gate only.

## Commands

```bash
atl plan <id> [--auto-scope] [--yes]
atl start <id> [<artifact_path>] [--suggest]
atl review <id> [--auto] [--no-plan]
atl done <id> [--force]
atl resolve <id>           # CLOSE verdict -> RESOLVED
atl drop <id>              # ARCHIVE verdict -> DROPPED
atl lifecycle <id>         # show status + next command
atl in-progress            # list threads in PLANNED/BUILDING/REVIEWING
```

## Coverage gate

`atl done` requires:

1. Zero MUST items in `build_plan.json` have `status: missing`, **and**
2. Overall `(covered + partial) / (MUST + NICE)` ≥ `0.8`.

`--force` bypasses both and logs `[forced]` in `decisions.log`.

## Files written per thread

```
harvest/<id>_<slug>/
├── manifest.json       ← source of truth for status
├── concepts.json       ← raw extraction (all concepts)
├── build_plan.json     ← scoped: must/nice/skip (from `atl plan`)
├── coverage.json       ← audit result (from `atl review`)
├── coverage.md
├── code_blocks.md
├── key_quotes.md
├── final_output.md
└── summary.md
```

## Close payload

`atl done / resolve / drop` POSTs to `http://localhost:3001/api/law/close_loop`:

```json
{
  "loop_id": "487",
  "title": "Marketing for Beginners",
  "outcome": "closed",
  "artifact_path": "apps/ai-exec-pipeline",
  "coverage_score": 0.87,
  "status": "DONE"
}
```

`closures.json` and `loops_closed.json` both persist those extra fields, so the artifact link survives forever.

## auto_actor protection

`auto_actor.py` refuses to auto-close any thread whose manifest has status in `{PLANNED, BUILDING, REVIEWING, DONE, RESOLVED, DROPPED}`. Only threads with no manifest or `HARVESTED` status are eligible for automatic classification.

## Migration

Existing harvests (pre-lifecycle) get tagged via:

```bash
python services/cognitive-sensor/migrate_manifest_status.py           # dry run
python services/cognitive-sensor/migrate_manifest_status.py --apply   # write
```

Every existing manifest gains `status: "HARVESTED"`. Nothing else changes.

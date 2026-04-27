# Diff Harness · Plan D verification

## Purpose
Deterministic pass/fail check for each SPEC implementation against both synthetic fixtures and real-world URLs.

## Architecture
```
┌────────────────────────────────────────────────┐
│ diff-harness runner (node + playwright)        │
├────────────────────────────────────────────────┤
│   1. load target URL in Chromium               │
│   2. wait for settle (default 5s)              │
│   3. inject + run patch under test             │
│   4. capture serialized output                 │
│   5. open output in fresh Chromium tab         │
│   6. screenshot both at same viewport          │
│   7. compute metrics                           │
│   8. write JSON report                         │
└────────────────────────────────────────────────┘
```

## Metrics per run

| metric                              | how computed                                                   |
|-------------------------------------|----------------------------------------------------------------|
| `ssim`                              | SSIM between original-page screenshot and replay screenshot    |
| `shadow_root_count_delta`           | `abs(live_count - replay_parsed_count)`                        |
| `adopted_sheet_rule_count_delta`    | total rules live vs total rules replay                         |
| `canvas_nonblank_count`             | canvases that rendered visible content in replay               |
| `html_bytes`                        | byte length of serialized output                               |
| `capture_time_ms`                   | wall-clock of patch execution                                  |

## Pass criteria (per SPEC)

| spec | metric                                  | threshold              |
|------|-----------------------------------------|------------------------|
| 01   | `ssim`                                  | ≥ 0.92 on linear.app   |
| 01   | `adopted_sheet_rule_count_delta`        | ≤ 2                    |
| 02   | `shadow_root_count_delta`               | = 0                    |
| 02   | `ssim`                                  | ≥ 0.90 on notion.com   |
| 03   | `canvas_nonblank_count`                 | = live canvas count    |
| 03   | `ssim` (canvas subregion)               | ≥ 0.80 on excalidraw   |
| all  | `capture_time_ms`                       | ≤ 2000 on any URL      |

## Test corpus

See `TEST-CORPUS.md` for the full 50-URL list. Minimum pass-gate subset (before calling Phase 1 done):

| url                                | SPECs exercised          |
|------------------------------------|--------------------------|
| https://linear.app/homepage        | 01 (adopted), 02 (shadow)|
| https://notion.com/product         | 02 (shadow)              |
| https://excalidraw.com/            | 03 (canvas)              |
| https://www.anthropic.com/         | baseline (should not regress vs current extension) |
| https://www.figma.com/community    | baseline (authenticated-mode capture only) |

## Running the harness
```
node tools/anatomy-rewrite/harness/run.mjs --url <url> --spec <01|02|03|all>
```

Output: `tools/anatomy-rewrite/harness/reports/<timestamp>/<url-slug>.json`

## Gates
A SPEC implementation is NOT merged until the harness passes on every URL in its row of the minimum subset. Phase 1 exit = all three SPECs green on the full row.

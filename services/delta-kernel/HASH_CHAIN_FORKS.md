# Hash Chain Fork Report

**Date:** 2026-02-11
**File:** `.delta-fabric/deltas.json`

## Summary

10 fork points found in the delta hash chain. At each fork, exactly 2 deltas share the same `prev_hash`, creating a binary branch. This is a systemic pattern likely caused by concurrent daemon runs writing deltas simultaneously.

## Fork Points

| # | prev_hash (truncated) | Lines | Count |
|---|----------------------|-------|-------|
| 1 | `6e56ce4f1346...` | 39, 59 | 2 |
| 2 | `4b4cdce3e2d5...` | 119, 139 | 2 |
| 3 | `3465a5e806c3...` | 219, 239 | 2 |
| 4 | `4d579e3bf5fb...` | 419, 439 | 2 |
| 5 | `2d9f32efe5a9...` | 759, 779 | 2 |
| 6 | `1ca2789de8e5...` | 839, 859 | 2 |
| 7 | `729ef38caf0d...` | 977, 997 | 2 |
| 8 | `8ca15a6b8a74...` | 1017, 1037 | 2 |
| 9 | `3fa822aa20f3...` | 1057, 1077 | 2 |
| 10 | `70447d0e283f...` | 1137, 1157 | 2 |

## Risk Assessment

- **Data loss:** None observed. Both branches contain valid deltas.
- **State divergence:** Possible. When two deltas fork from the same parent, the "winning" state depends on which is read last.
- **Root cause:** Concurrent daemon processes (governance_daemon, server) both writing deltas without a write lock.

## Recommended Actions

1. **Add a file lock** to `deltas.json` writes so only one process can append at a time.
2. **Review forked deltas** manually to confirm no conflicting state patches exist.
3. **Consider rebasing** the chain if conflicting patches are found (requires manual merge).

No automated repair applied — this requires human review to decide if deltas should be rebased or if the system should tolerate forks.

## Resolution (2026-03-11)

Storage migrated from JSON files to **SQLite with WAL mode** (`sqlite-storage.ts`). This eliminates the root cause:

- `appendDelta()` is now an O(1) INSERT (was O(n) read-all + push + rewrite)
- All writes use `db.transaction()` for atomicity
- `PRAGMA busy_timeout = 5000` handles concurrent access from daemon cron jobs
- The 10 historical forks remain in the migrated data but no new forks can occur

The old `entities.json` and `deltas.json` files were renamed to `.bak` during migration.

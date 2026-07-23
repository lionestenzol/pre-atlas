# RETIRED — mosaic-dashboard

Retired 2026-07-06 (festival `finish-atlas-fleet-FA0001`, task 02).

**Successor:** none. Retired together with its backend — the dashboard was the
Next.js UI for `mosaic-orchestrator` (:3005), which was retired in task 01. Its API
proxy routes (`/api/mosaic` → :3005, `/api/mirofish` → :3003) pointed at services
that no longer exist.

Was running as a `next dev` server on **:3000** and self-healing via the
`Atlas-Autostart` scheduled task.

Removed from autostart in this task:
- Dropped the `mosaic-dashboard:3000` entry (and its console banner line) from `scripts/start_atlas.ps1`.
- Flipped `in_autostart` -> false + path -> `_retired/` in `audit/system-index.json` (`autostart_count` 11 -> 10).

Archived, not deleted (code-as-furniture). Re-home the operator UI onto a live
surface (delta-kernel / cortex / optogon) if a dashboard is wanted again.

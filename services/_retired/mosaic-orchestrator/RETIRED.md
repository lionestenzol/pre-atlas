# RETIRED — mosaic-orchestrator

Retired 2026-07-06 (festival `finish-atlas-fleet-FA0001`, task 01).

**Successor:** `optogon` + `cortex` (reasoning + work-prep split the old orchestrator's role).

Archived, not deleted (code-as-furniture). Was running as a zombie on **:3005**
and self-healing via the `Atlas-Autostart` scheduled task.

Removed from autostart in this same task:
- Dropped the `mosaic-orch:3005` entry from `scripts/start_atlas.ps1`.
- Flipped `in_autostart` -> false in `audit/system-index.json`.

Orphaned launcher `scripts/svc_orchestrator.ps1` also targets this service (:3005) and is
now dead — referenced by nothing. Left in place; retire it if it stays unused.

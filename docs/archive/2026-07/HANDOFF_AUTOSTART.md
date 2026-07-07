# Handoff: Fix delta-kernel autostart (CHORE-AUTOSTART)

**Created:** 2026-06-15 by previous session after PKT-008 shipped (commit `b40a36b`)
**Goal:** Close the "delta-kernel always has to be initialized" pain point.
**Estimated scope:** ~15 min · ~30 LOC · one new file + 1-2 commits.

---

## The problem in one sentence

`scripts/start_atlas.ps1` is referenced by 4 things (`start_atlas.bat`, the `Atlas-Autostart` scheduled task, Desktop `Atlas.lnk`, Start Menu `Atlas.lnk`) but **was never written**. Every login the scheduled task fires, errors instantly because the target script is missing, and nothing starts. The user has to manually run `.\scripts\run_delta_api.ps1` to bring delta-kernel up. That's the loop they want closed.

## Diagnosis already done

Verified during the previous session (2026-06-15):

| Check | Result |
|---|---|
| `Get-ScheduledTask Atlas-Autostart` | **Registered**, State: Ready, `LastRunTime` empty (never run successfully) |
| `Test-Path scripts\start_atlas.ps1` | **MISSING** — never created |
| `Test-Path scripts\_atlas_runner.ps1` | EXISTS — the inner per-service helper, but never called by anything |
| `scripts/install_atlas_autostart.ps1` line 10 | References the missing `scripts\start_atlas.ps1` |
| `start_atlas.bat` line 4 | Same reference |
| Desktop `Atlas.lnk` + Start Menu `Atlas.lnk` | Same reference (created by install_autostart) |
| Git tracking of the autostart bundle | **UNTRACKED since May 2** (~6 weeks rot) |
| delta-kernel runtime check | DOWN (port 3001 empty, HTTP 000) at handoff time |

## What exists today

Already-working manual scripts under `scripts/`:

- `run_delta_api.ps1` — boots ONLY delta-kernel (sets `DELTA_DATA_DIR=<repo>\.delta-fabric`, then `npm run api` from `services/delta-kernel`). This is the user's daily workaround.
- `run_all.ps1` — older multi-service launcher (delta + UASC + Cortex in separate windows + cognitive-sensor refresh sequence). Reference for what services to start.
- `_atlas_runner.ps1` — newer per-service wrapper. Takes `-Name -Cwd -LogFile -RunCmd`. Sets window title `atlas-<Name>`, writes header to log file, runs cmd with output tee'd. This IS the right inner helper to call.
- `status_atlas.ps1` — knows about 12 services and their ports. Use its service list as the canonical "what services exist."
- `stop_atlas.ps1` — kills listening processes on those 12 ports.
- `install_atlas_autostart.ps1` — registers `Atlas-Autostart` scheduled task + Desktop/Start Menu shortcuts. Already ran in the past (task is registered). Don't re-run unless rebuilding.
- `uninstall_atlas_autostart.ps1` — clean removal.
- `start_atlas.bat` / `stop_atlas.bat` — repo-root double-click entry points.

## What's missing — the load-bearing gap

`scripts/start_atlas.ps1` — the outer orchestrator. It should:

1. Determine which services from `status_atlas.ps1`'s 12-row table belong in autostart (probably the subset that has working start commands today — start with just **delta-kernel** for the minimal close, then expand)
2. For each, spawn a hidden background window via:
   ```powershell
   Start-Process powershell -WindowStyle Hidden -ArgumentList `
     "-NoProfile","-ExecutionPolicy","Bypass","-File","scripts\_atlas_runner.ps1", `
     "-Name","delta-kernel", `
     "-Cwd","services\delta-kernel", `
     "-LogFile","logs\atlas-delta-kernel.log", `
     "-RunCmd","`$env:DELTA_DATA_DIR='<repo>\.delta-fabric'; npm run api"
   ```
3. Optionally open `apps/inpact/index.html` in the default browser at the end (the `install_atlas_autostart.ps1` description says "Start Atlas and open inPACT")
4. Log a single "atlas startup at <timestamp>" line so we can see the task fired

**Minimum viable scope:** delta-kernel only. Get the loop closed. Expand to more services in a follow-up if the user wants.

## Test plan (in order)

1. **Manual launch** — `cd "C:\Users\bruke\Pre Atlas"; .\scripts\start_atlas.ps1`. Verify port 3001 listening within ~10s (`(Get-NetTCPConnection -State Listen -LocalPort 3001 -ErrorAction SilentlyContinue) -ne $null`).
2. **Stop test** — `.\scripts\stop_atlas.ps1`. Verify port 3001 freed.
3. **Bat test** — double-click `start_atlas.bat` from Explorer. Same outcome.
4. **Scheduled task test** — `Start-ScheduledTask -TaskName Atlas-Autostart`. Wait ~10s. Verify port 3001 listening AND `(Get-ScheduledTask Atlas-Autostart | Get-ScheduledTaskInfo).LastTaskResult` is `0`.
5. **Reboot/logout-login test** *(optional, user-driven)* — confirm autostart actually fires at next login. Without this, the loop isn't proven end-to-end.

## Files to commit (after build + test)

The 7 autostart files were never committed. After step 4 above passes, stage and commit the whole bundle:

```
git add scripts/_atlas_runner.ps1 scripts/install_atlas_autostart.ps1 \
        scripts/status_atlas.ps1 scripts/stop_atlas.ps1 \
        scripts/uninstall_atlas_autostart.ps1 scripts/start_atlas.ps1 \
        start_atlas.bat stop_atlas.bat
```

Suggested message: `chore(autostart): write missing start_atlas.ps1 + commit autostart bundle`. Body should note that the install_autostart task was already registered weeks ago but its target was missing — this commit closes that gap.

## Caveats / sharp edges

- The scheduled task `Atlas-Autostart` is registered at user-level (`-RunLevel Limited`), so no elevation needed. Good.
- `_atlas_runner.ps1` calls `Invoke-Expression "$RunCmd 2>&1" | Tee-Object`. If `$RunCmd` contains backtick or `$env:VAR` you must single-quote-string it carefully when spawning. Test with the actual `npm run api` line before scheduling.
- The `logs/` directory probably doesn't exist. Create it (or have `start_atlas.ps1` create it) before passing `-LogFile` paths.
- `npm run api` is `tsx src/api/server.ts` per `services/delta-kernel/package.json:13`. That's a foreground process; the hidden background window is what keeps it alive.
- The user runs Windows 11 Home with PowerShell 7+. PS scripts must use PS-flavored syntax (`-File`, not `-Command`, for clean process tree).
- Don't blow up on top of unrelated working-tree changes — at handoff there were many `M` files unrelated to PKT-008 / autostart (`apps/inpact/*`, `services/canvas-engine/*`, etc.). Use targeted `git add <file>` for the autostart bundle only.

## Related state at handoff

- **PKT-008 just shipped** (`b40a36b`) — backend wire of droplist signals into Lattice viewmodel. Unrelated to autostart but landed minutes before this handoff.
- **PKT-009 drafted** (`services/droplist/PACKETS/009_lattice_ui_droplist_consumer.md`) — UI consumer follow-up to PKT-008. Different work track entirely. Not blocking autostart.
- delta-kernel itself: TS-clean (`tsc --noEmit` → 0). No regression risk; the autostart change touches no `.ts` files.

## What the next session should NOT do

- Don't reopen droplist or signals-store (settled core per DropList Bible §10)
- Don't merge this into the PKT-009 packet — autostart is infra, not droplist
- Don't `git add -A` — there are unrelated working-tree changes from prior sessions
- Don't add force-elevation (Run as Administrator) — the existing task is Limited; keep it that way
- Don't introduce a Node/Python service-supervisor dependency. The whole point is keep this stack-native PowerShell + scheduled task. No PM2, no nssm, no Docker.

## One-shot success criterion

```powershell
Restart-Computer    # then log in
Start-Sleep 30
Invoke-WebRequest http://127.0.0.1:3001/api/state -UseBasicParsing | Select-Object StatusCode
```

→ Returns `200`. That's the close.

# Atlas Doors

Ways to reach Atlas without a Claude Code session. Ships from fest [`atlas-doors-AD0001`](../../festival-project/festivals/active/atlas-doors-AD0001/).

## The doors

| Door | For | Invoke | Requires |
|---|---|---|---|
| `atlas.exe` | Any terminal, any script | `atlas <cmd>` | delta-kernel :3001 running (for HTTP verbs); `ATLAS_REPO_ROOT` env |
| `AtlasTray.exe` (tray app) | You, at the desktop | Left-click "A" icon in system tray | atlas-map-api :3072 running (for full mission-control render) |
| `atlas-map` MCP | Claude Code / agents | Any `mcp__atlas-map__*` tool | CC session |
| REST | Anything that speaks HTTP | `curl http://localhost:3001/api/...` with bearer | delta-kernel :3001 |

Both binaries live at `C:\Users\bruke\bin\` and are on user PATH.

## `atlas.exe` — CLI door

Compiled from `services/delta-kernel/src/cli/atlas-ai.ts` via Node SEA (86 MB single-file exe, bundles the Node runtime).

**Common commands** (same schema as the source CLI):

```
atlas help                # command schema (JSON)
atlas capabilities        # machine-readable command schema
atlas state               # full snapshot
atlas next                # recommended action
atlas morning             # start-of-day compound
atlas wrap                # end-of-day compound
atlas task add "…"        # add task
atlas task done <id>      # complete task
atlas win "…"             # log momentum win
atlas journal add "…"     # journal entry
atlas close <loop_id>     # close a loop
atlas cognitive           # drift + compliance
atlas directive           # strategic directive + clusters
atlas loops               # open loops list
```

**Offline behavior:** if delta-kernel :3001 is down, prints one line — `atlas: delta-kernel offline at http://localhost:3001 (start with scripts/start_atlas.ps1)` — and exits 3. No Node stack trace.

**Env:**
- `ATLAS_REPO_ROOT` — absolute path to the Pre Atlas repo. Set at user scope so the exe finds `services/cognitive-sensor/` sidecars from its installed location.
- Optional: `MEMORY_HUB_URL` (default `http://127.0.0.1:3071/search`), `ATLAS_LLM_ENDPOINT`, `ATLAS_LLM_MODEL`, `ATLAS_DEBUG=1`.

**Rebuild** (after editing `atlas-ai.ts`):

```bash
cd services/delta-kernel
npx esbuild src/cli/atlas-ai.ts --bundle --platform=node --target=node20 --format=cjs --outfile=build/atlas.cjs
node --experimental-sea-config build/sea-config.json
node -e "require('fs').copyFileSync(process.execPath,'build/atlas.exe')"
npx postject build/atlas.exe NODE_SEA_BLOB build/sea-prep.blob --sentinel-fuse NODE_SEA_FUSE_fce680ab2cc467b6e072b8b5df1996b2
cp build/atlas.exe /c/Users/bruke/bin/atlas.exe
```

## `AtlasTray.exe` — tray app door

Tauri v2 shell wrapping `atlas-mission-control.html`. 4.5 MB (uses the system WebView2 runtime instead of bundling Chromium). Source: `apps/atlas-tray/`.

**Filename note:** the binary is `AtlasTray.exe`, not `Atlas.exe`. Windows filesystem lookups are case-insensitive, so `Atlas.exe` in the same directory as `atlas.exe` (the CLI door) overwrote the CLI when both were installed to `C:\Users\bruke\bin\`. The display name in the title bar and tray tooltip is still "Atlas" (set via `tauri.conf.json` `productName`); only the file name is different. See `apps/atlas-tray/src-tauri/Cargo.toml` `[[bin]]` block for the source-side rename.

**Behavior:**
- Tray icon: dark rounded square with white "A" glyph.
- Left-click on tray icon → restore window.
- Right-click on tray icon → menu with Open, Quit.
- X-button on window → hide to tray (process persists).
- On launch → window opens automatically once (so the first launch is visible confirmation).

**Autostart:** registered via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Atlas` pointing at `C:\Users\bruke\bin\AtlasTray.exe`. No admin needed.

**Rebuild:**

```bash
cd apps/atlas-tray
npx tauri build --no-bundle
# Cargo.toml [[bin]] name = "AtlasTray" -> release/AtlasTray.exe.
# Copy under the same name to avoid the case-collision that overwrites atlas.exe.
cp src-tauri/target/release/AtlasTray.exe /c/Users/bruke/bin/AtlasTray.exe
```

The mission-control HTML fetches `http://localhost:3072` (atlas-map-api). If that service is down, the page renders with a red `hub unreachable · Failed to fetch` status pill — that is the *page* reporting *service* status; the door itself is fine.

## Uninstall

```powershell
# Stop tray app
Stop-Process -Name AtlasTray -Force -ErrorAction SilentlyContinue

# Delete binaries
Remove-Item C:\Users\bruke\bin\AtlasTray.exe -ErrorAction SilentlyContinue
Remove-Item C:\Users\bruke\bin\atlas.exe -ErrorAction SilentlyContinue

# Remove autostart
Remove-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run -Name Atlas -ErrorAction SilentlyContinue

# Clear env vars
[Environment]::SetEnvironmentVariable('ATLAS_REPO_ROOT', $null, 'User')
# If C:\Users\bruke\bin exists only for atlas.exe, remove from PATH:
# $p = [Environment]::GetEnvironmentVariable('Path','User') -split ';' | Where-Object { $_ -ne 'C:\Users\bruke\bin' }
# [Environment]::SetEnvironmentVariable('Path', ($p -join ';'), 'User')
```

## Related

- `services/atlas-map-api/SELF_DESCRIBE.md` — role/clearance model behind the MCP door.
- `TRUST_BOUNDARY.md` — closed capability set; the doors invoke existing routes only.
- Fest: `festival-project/festivals/active/atlas-doors-AD0001/`.
- Note: `docs/CLI_REFERENCE.md` is auto-generated from `services/cognitive-sensor/cli_manifest.json`; it still lists only the `npx tsx` invocation of atlas-ai and will show `atlas.exe` once the manifest and generator are updated.

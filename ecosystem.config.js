// PM2 supervisor — one place, real health, auto-restart, log rotation.
// Boot flow: pm2-startup runs `pm2 resurrect` at login; PM2 keeps every entry
// alive from there. If one crashes it restarts (default 15 attempts, then STOPPED
// state — see `pm2 list`). Replaces scripts/start_atlas.ps1 + Atlas-Autostart cron.
//
// After editing this file:  pm2 reload ecosystem.config.js && pm2 save
// One service down:          pm2 restart <name>
// See live state:            pm2 list   (or /atlas/fleet page once wired)
//
// Windows-native pattern: for shims (.cmd like npm/npx/http-server), use
// interpreter: "none" so PM2 executes the shim directly instead of piping it
// through node (which yields SyntaxError on .cmd headers).

const REPO = "C:\\Users\\bruke\\Pre Atlas";
const LOGS = REPO + "\\.atlas-logs";
const HTTP_SERVER_CMD = "C:\\Users\\bruke\\AppData\\Roaming\\npm\\http-server.cmd";
const NPX_CMD = "C:\\Users\\bruke\\AppData\\Roaming\\npm\\npx.cmd";
const NPM_CMD = "C:\\Users\\bruke\\AppData\\Roaming\\npm\\npm.cmd";
const SYS_PYTHON = "C:\\Python313\\python.exe";

const common = {
  autorestart: true,
  max_restarts: 20,
  restart_delay: 3000,
  min_uptime: 10000,           // 10s — some servers take a beat to bind
  max_memory_restart: "800M",
  merge_logs: true,
  time: true,
  kill_timeout: 4000,
};

// Two spawn shapes:
//
// native() — direct .exe (python.exe, node.exe). PM2 spawns without a shell.
// shell()  — .cmd/.bat shim (npx.cmd, npm.cmd, http-server.cmd). Windows can't
//   CreateProcess a .cmd directly (spawn EINVAL) — must go through cmd.exe /c.
//   We wrap the whole invocation in a single /c "..." string so args survive.
const native = (name, port, cwd, script, args, env = {}) => ({
  ...common,
  name, cwd, script, args,
  interpreter: "none",
  env: { PORT: String(port), ...env },
  out_file:   `${LOGS}\\${name}.out.log`,
  error_file: `${LOGS}\\${name}.err.log`,
});
const shell = (name, port, cwd, cmdline, env = {}) => ({
  ...common,
  name, cwd,
  script: "cmd.exe",
  args: `/c ${cmdline}`,
  interpreter: "none",
  env: { PORT: String(port), ...env },
  out_file:   `${LOGS}\\${name}.out.log`,
  error_file: `${LOGS}\\${name}.err.log`,
});

module.exports = {
  apps: [
    shell("delta-kernel",     3001, `${REPO}\\services\\delta-kernel`,
        "npx tsx src/api/server.ts",
        { DELTA_REPO_ROOT: REPO, DELTA_DATA_DIR: `${REPO}\\.delta-fabric`, GOVERNANCE_DAEMON: "1" }),

    shell("aegis-fabric",     3002, `${REPO}\\services\\aegis-fabric`,
        "node --env-file=.env --import tsx/esm src/api/server.ts"),

    native("openclaw",        3004, `${REPO}\\services\\openclaw`,
        SYS_PYTHON, "-m uvicorn openclaw.api:app --host 127.0.0.1 --port 3004",
        { PYTHONPATH: "src" }),

    shell("inpact",           3006, `${REPO}\\apps\\inpact`,
        "http-server . -p 3006 -c-1 --cors"),

    native("code-converter",  3007, `${REPO}\\apps\\code-converter`,
        SYS_PYTHON, "server.py"),

    native("uasc",            3008, `${REPO}\\services\\uasc-executor`,
        SYS_PYTHON, "server.py --port 3008"),

    native("cortex",          3009, `${REPO}\\services\\cortex`,
        SYS_PYTHON, "-m uvicorn cortex.main:app --host 127.0.0.1 --port 3009",
        { PYTHONPATH: "src" }),

    native("optogon",         3010, `${REPO}\\services\\optogon`,
        SYS_PYTHON, "-m uvicorn optogon.main:app --host 127.0.0.1 --port 3010",
        { PYTHONPATH: "src", OPTOGON_SIGNAL_EMIT: "1" }),

    shell("canvas-engine",    3050, `${REPO}\\services\\canvas-engine`,
        "npm run dev"),

    native("memory-hub",      3071, `${REPO}\\services\\memory-hub`,
        `${REPO}\\services\\memory-hub\\.venv\\Scripts\\python.exe`,
        "-m memory_hub.server"),

    native("atlas-map-api",   3072, `${REPO}\\services\\atlas-map-api`,
        `${REPO}\\services\\atlas-map-api\\.venv\\Scripts\\python.exe`,
        "-m atlas_map_api.server"),

    native("droplist",        3073, `${REPO}\\services\\droplist`,
        SYS_PYTHON, "-m droplist.server",
        { PATH: `C:\\Python313;C:\\Python313\\Scripts;${process.env.PATH || ""}` }),

    shell("atlas-shell",      8888, REPO,
        "http-server . -p 8888 -c-1 --cors"),

    // fleet-api on :3080 — was :3074 briefly, but that collided with triangulation
    // (`fix(atlas): triangulation port drift — 3075 → 3074`). :3080 is unclaimed.
    native("fleet-api",       3080, `${REPO}\\services\\fleet-api`,
        "node.exe", "server.js"),

    // triangulation :3074 — DOM + spatial + visual verification sidecar.
    // Uses system python; module is installed via `pip install -e services/triangulation`.
    native("triangulation",   3074, `${REPO}\\services\\triangulation`,
        SYS_PYTHON, "-m uvicorn triangulation.api:app --host 127.0.0.1 --port 3074",
        { PYTHONPATH: "src" }),
  ],
};

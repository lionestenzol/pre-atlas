// fleet-api :3074 — honest readout of the PM2-supervised Atlas fleet.
// Reads `pm2 jlist` per request (no cached lies) and probes each service's port so
// tiles show BOTH pm2's opinion ("online") AND real HTTP reachability ("live").
// POST /restart requires X-Atlas-Token (shared with atlas-map-api / droplist).
//
// Local-only: binds 127.0.0.1. CORS lets atlas-shell (:8888) call it.

const http = require("http");
const net = require("net");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.PORT || 3074);
const REPO_ROOT = "C:\\Users\\bruke\\Pre Atlas";
const TOKEN_FILE = path.join(REPO_ROOT, ".atlas-write-token");

function readToken() {
  try { return fs.readFileSync(TOKEN_FILE, "utf-8").trim(); }
  catch { return null; }
}

function runPm2(args) {
  return new Promise((resolve) => {
    // On Windows PM2 is a .cmd shim — must go through cmd.exe.
    const p = spawn("cmd.exe", ["/c", "pm2", ...args], { windowsHide: true });
    let out = "", err = "";
    p.stdout.on("data", (c) => (out += c));
    p.stderr.on("data", (c) => (err += c));
    p.on("close", (code) => resolve({ code, out, err }));
  });
}

function probePort(port, timeoutMs = 400) {
  return new Promise((resolve) => {
    const s = net.createConnection({ host: "127.0.0.1", port }, () => {
      s.destroy(); resolve(true);
    });
    s.on("error", () => resolve(false));
    s.setTimeout(timeoutMs, () => { s.destroy(); resolve(false); });
  });
}

async function fleetSnapshot() {
  const { code, out, err } = await runPm2(["jlist"]);
  if (code !== 0) return { error: err || "pm2 jlist failed", services: [] };
  let arr;
  try { arr = JSON.parse(out); }
  catch { return { error: "pm2 jlist returned non-json", services: [] }; }

  const services = await Promise.all(arr.map(async (p) => {
    const port = Number(p.pm2_env?.env?.PORT || 0);
    const alive = port ? await probePort(port) : false;
    return {
      name: p.name,
      port,
      status: p.pm2_env?.status || "unknown",
      alive,
      pid: p.pid || null,
      uptime_ms: p.pm2_env?.pm_uptime ? Date.now() - p.pm2_env.pm_uptime : 0,
      restarts: p.pm2_env?.restart_time ?? 0,
      unstable_restarts: p.pm2_env?.unstable_restarts ?? 0,
      cpu: p.monit?.cpu ?? 0,
      mem_mb: Math.round(((p.monit?.memory ?? 0) / 1024 / 1024) * 10) / 10,
    };
  }));

  services.sort((a, b) => a.name.localeCompare(b.name));
  const online = services.filter((s) => s.status === "online" && s.alive).length;
  return { services, total: services.length, online, generated_at: new Date().toISOString() };
}

function jsonResponse(res, code, body) {
  const s = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(s),
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Atlas-Token",
    "Cache-Control": "no-store",
  });
  res.end(s);
}

const server = http.createServer(async (req, res) => {
  if (req.method === "OPTIONS") return jsonResponse(res, 204, {});
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "GET" && url.pathname === "/api/fleet") {
    return jsonResponse(res, 200, await fleetSnapshot());
  }

  const restartMatch = url.pathname.match(/^\/api\/fleet\/restart\/([a-zA-Z0-9_.-]+)$/);
  if (req.method === "POST" && restartMatch) {
    const token = readToken();
    if (!token || req.headers["x-atlas-token"] !== token) {
      return jsonResponse(res, 401, { error: "missing or invalid X-Atlas-Token" });
    }
    const name = restartMatch[1];
    const { code, out, err } = await runPm2(["restart", name, "--update-env"]);
    return jsonResponse(res, code === 0 ? 200 : 500, {
      name, ok: code === 0, code, out: out.slice(-800), err: err.slice(-800),
    });
  }

  if (url.pathname === "/health") return jsonResponse(res, 200, { ok: true });
  jsonResponse(res, 404, { error: "not found", path: url.pathname });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(JSON.stringify({ service: "fleet-api", port: PORT, msg: "listening" }));
});

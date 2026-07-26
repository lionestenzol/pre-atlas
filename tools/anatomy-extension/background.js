// Anatomy background service worker.
// Extension origin can bypass page-level CORS for asset fetches and is the only
// place that can call chrome.tabs.captureVisibleTab. Every async branch must
// `return true` from inside its own block so the message channel stays open.

const FETCH_TIMEOUT_MS = 15000;
const MAX_FETCH_BYTES = 8 * 1024 * 1024; // 8 MB per asset, hard cap to keep storage bounded

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (!msg || !msg.type) return false;

  if (msg.type === 'anatomy:capture') {
    handleCapture(sender, reply);
    return true;
  }

  if (msg.type === 'anatomy:fetch') {
    handleFetch(msg, reply);
    return true;
  }

  if (msg.type === 'anatomy:ensure-daemon') {
    ensureDaemonViaNative((msg && msg.base) || 'http://localhost:8088').then(reply);
    return true;
  }

  if (msg.type === 'anatomy:daemon-ping') {
    handleDaemonPing(msg, reply);
    return true;
  }

  if (msg.type === 'anatomy:daemon-post') {
    handleDaemonPost(msg, reply);
    return true;
  }

  return false;
});

// ── Zoom-style auto-launch (Anatomy v0.4.5) ───────────────────────────
// The sitepull daemon (web-audit `sitepull serve`, :8088) used to require a
// manual start in a terminal before any pull would work. Now, when the daemon
// is unreachable, we ask a native-messaging host to spawn it on demand — the
// same pattern Zoom uses to open its app from a browser link. If the host
// isn't installed (run native-host/install-native-host.ps1 once), this fails
// soft and the extension behaves exactly as before (manual daemon).
const NATIVE_HOST = 'com.bruke.anatomy';

function ensureDaemonViaNative(base) {
  return new Promise((resolve) => {
    let port;
    try {
      port = chrome.runtime.connectNative(NATIVE_HOST);
    } catch (e) {
      resolve({ ok: false, error: 'connectNative threw: ' + ((e && e.message) || e) });
      return;
    }
    let done = false;
    const finish = (r) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { port.disconnect(); } catch (_) {}
      resolve(r);
    };
    const timer = setTimeout(() => finish({ ok: false, error: 'native host timeout' }), 13000);
    port.onMessage.addListener((m) => finish(m || { ok: true }));
    port.onDisconnect.addListener(() => {
      const err = chrome.runtime.lastError;
      finish({ ok: false, error: (err && err.message) || 'native host disconnected (is it installed?)' });
    });
    const portNum = Number(String(base || '').split(':').pop()) || 8088;
    try {
      port.postMessage({ cmd: 'ensure', port: portNum });
    } catch (e) {
      finish({ ok: false, error: 'postMessage failed: ' + ((e && e.message) || e) });
    }
  });
}

// Lightweight liveness probe, factored out so ping AND post can reuse it.
async function probeHealth(base) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2000);
  try {
    const res = await fetch(base + '/health', { signal: controller.signal });
    const body = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, error: (e && e.message) || String(e) };
  } finally {
    clearTimeout(timer);
  }
}

function handleCapture(sender, reply) {
  const windowId = sender && sender.tab && sender.tab.windowId;
  const opts = { format: 'png' };
  const capture = windowId != null
    ? (cb) => chrome.tabs.captureVisibleTab(windowId, opts, cb)
    : (cb) => chrome.tabs.captureVisibleTab(opts, cb);
  capture((dataUrl) => {
    const err = chrome.runtime.lastError;
    if (err || !dataUrl) reply({ ok: false, error: (err && err.message) || 'capture failed' });
    else reply({ ok: true, dataUrl });
  });
}

// Fetch a same-origin OR cross-origin resource on behalf of the page.
// Returns base64 of the bytes plus content-type so the daemon can persist it
// without losing binary fidelity.
async function handleFetch(msg, reply) {
  const url = msg && msg.url;
  if (!url || typeof url !== 'string') {
    reply({ ok: false, error: 'missing url' });
    return;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: 'GET',
      credentials: msg.credentials === 'include' ? 'include' : 'omit',
      redirect: 'follow',
      signal: controller.signal,
    });
    const buf = await res.arrayBuffer();
    if (buf.byteLength > MAX_FETCH_BYTES) {
      reply({ ok: false, error: `asset too large (${buf.byteLength} bytes)`, status: res.status });
      return;
    }
    const b64 = bytesToBase64(new Uint8Array(buf));
    reply({
      ok: true,
      status: res.status,
      contentType: res.headers.get('content-type') || '',
      finalUrl: res.url || url,
      dataB64: b64,
      byteLength: buf.byteLength,
    });
  } catch (e) {
    reply({ ok: false, error: (e && e.message) || String(e) });
  } finally {
    clearTimeout(timer);
  }
}

// Health-check the local sitepull daemon. Used by the HUD before a pull so
// we can fail fast with a useful message instead of hanging on POST. If the
// daemon is down, we now try to auto-launch it via the native host and re-probe
// once, so the HUD reports "up" instead of "start your daemon first".
async function handleDaemonPing(msg, reply) {
  const base = (msg && msg.base) || 'http://localhost:8088';
  let result = await probeHealth(base);
  if (!result.ok && !(msg && msg.noLaunch)) {
    const launch = await ensureDaemonViaNative(base);
    if (launch && launch.ok) {
      result = await probeHealth(base);
      result.launched = launch.started === true;
    } else {
      result.launch = launch; // surface why auto-launch didn't help
    }
  }
  reply(result);
}

// Forward an ingest payload to the daemon. We could let content.js POST
// directly via fetch — going through the SW gives us one place to centralize
// the daemon URL and a clean error surface.
async function handleDaemonPost(msg, reply) {
  const base = (msg && msg.base) || 'http://localhost:8088';
  const path = (msg && msg.path) || '/ingest';
  const body = msg && msg.body;
  if (!body) {
    reply({ ok: false, error: 'missing body' });
    return;
  }
  // First attempt; if the connection is refused (daemon down), auto-launch via
  // the native host and retry exactly once before giving up.
  let res = await postOnce(base + path, body);
  if (!res.ok && res.connError) {
    const launch = await ensureDaemonViaNative(base);
    if (launch && launch.ok) {
      res = await postOnce(base + path, body);
      res.launched = launch.started === true;
    } else {
      res.launch = launch;
    }
  }
  reply(res);
}

// Single POST attempt. Distinguishes a connection failure (daemon down →
// worth auto-launching) from an HTTP error (daemon up but unhappy → don't).
async function postOnce(url, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const text = await res.text();
    let parsed;
    try { parsed = JSON.parse(text); } catch (_) { parsed = { raw: text }; }
    return { ok: res.ok, status: res.status, body: parsed };
  } catch (e) {
    return { ok: false, connError: true, error: (e && e.message) || String(e) };
  } finally {
    clearTimeout(timer);
  }
}

// Chunked base64 encoder — btoa() chokes on binary strings >~1MB and on
// characters above U+00FF. We feed it 32k-byte slices via String.fromCharCode.
function bytesToBase64(bytes) {
  const CHUNK = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += CHUNK) {
    const slice = bytes.subarray(i, Math.min(i + CHUNK, bytes.length));
    binary += String.fromCharCode.apply(null, slice);
  }
  return btoa(binary);
}

// ── dev hot-reload (Anatomy v0.3.2) ───────────────────────────────
// Polls the local sitepull daemon for a monotonic /dev/version counter.
// When Claude bumps the counter (`curl -X POST /dev/bump`), the extension
// reloads itself + refreshes every tab on the next service-worker wake.
//
// Why poll instead of Server-Sent Events: MV3 service workers get killed
// aggressively after ~30s of idle. Any long-lived connection dies. Chrome
// does wake the worker when an alarm fires, so alarms are the only reliable
// scheduler. Alarms minimum period is 1 minute in stable, 30s in dev — we
// use 30s so the loop feels snappy-enough without hammering the daemon.
const DEV_DAEMON_BASE = 'http://localhost:8088';
const DEV_POLL_ALARM = 'anatomy-dev-poll';
const DEV_POLL_PERIOD_MINUTES = 0.5; // 30 seconds
const DEV_LAST_VERSION_KEY = 'anatomy_dev_last_version';
const DEV_PENDING_RELOAD_KEY = 'anatomy_dev_pending_tab_refresh';

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(DEV_POLL_ALARM, { periodInMinutes: DEV_POLL_PERIOD_MINUTES });
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create(DEV_POLL_ALARM, { periodInMinutes: DEV_POLL_PERIOD_MINUTES });
});
// Idempotent registration at script parse time — first service-worker wake
// after install runs this, which seeds the alarm without waiting for onInstalled.
try { chrome.alarms.get(DEV_POLL_ALARM, (a) => { if (!a) chrome.alarms.create(DEV_POLL_ALARM, { periodInMinutes: DEV_POLL_PERIOD_MINUTES }); }); } catch (_) {}

// Warm the daemon on browser start / extension load so a pull never has to wait.
// Also exercises the native-launch path automatically (no manual pull needed).
// Fails soft if the native host isn't installed.
function warmDaemon() { try { ensureDaemonViaNative('http://localhost:8088').catch(() => {}); } catch (_) {} }
chrome.runtime.onStartup.addListener(warmDaemon);   // browser launch
chrome.runtime.onInstalled.addListener(warmDaemon); // install / reload

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === DEV_POLL_ALARM) devPoll().catch(() => {});
});

// Note: we deliberately do NOT auto-reload any tabs after runtime.reload().
// Chrome's "Confirm Form Resubmission" dialog fires on any page with POST
// state (login pages, search forms) and locks the user out of their tab
// until they manually dismiss it. The hot-reload's value is ensuring the
// NEXT page load uses the latest content script — that's enough. If the
// user wants immediate pickup on an open tab, they F5. Left the
// DEV_PENDING_RELOAD_KEY constant in place in case we reintroduce a
// narrower (opt-in, user-initiated) tab-refresh path later.
chrome.storage.local.remove([DEV_PENDING_RELOAD_KEY]).catch(() => {});

async function devPoll() {
  let data;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500);
    const res = await fetch(DEV_DAEMON_BASE + '/dev/version', { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return;
    data = await res.json();
  } catch (_) { return; /* daemon off or unreachable — skip quietly */ }

  if (!data || typeof data.version !== 'number') return;
  const seen = await chrome.storage.local.get([DEV_LAST_VERSION_KEY]);
  const last = (seen && seen[DEV_LAST_VERSION_KEY]);
  if (last == null) {
    await chrome.storage.local.set({ [DEV_LAST_VERSION_KEY]: data.version });
    return;
  }
  if (data.version === last) return;

  // Version bumped. Mark tabs for refresh, bump our stored version, reload.
  await chrome.storage.local.set({
    [DEV_LAST_VERSION_KEY]: data.version,
    [DEV_PENDING_RELOAD_KEY]: true,
  });
  console.log('[anatomy-dev] daemon bumped version', data.version, '→ reloading extension');
  chrome.runtime.reload();
}

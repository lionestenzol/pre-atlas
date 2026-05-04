"""Build anatomy/today.html — mockup + live-iframe modes."""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(r"C:/Users/bruke/Pre Atlas")
TEMPLATE = Path.home() / ".claude" / "skills" / "anatomy-map" / "template.html"
OUT = REPO / "anatomy" / "today.html"

SOURCE_FILES = [
    "apps/inpact/index.html",
    "apps/inpact/js/screens.js",
    "apps/inpact/js/today.js",
    "apps/inpact/js/signals.js",
    "apps/inpact/js/api.js",
    "apps/inpact/js/app.js",
    "apps/inpact/js/state.js",
    "services/delta-kernel/src/api/server.ts",
]

INPACT_URL = "http://localhost:3006/index.html"

TITLE = "today — anatomy map"
SUBTITLE = "inPACT Today / Daily / Tasks · live iframe + per-screen annotations"

# ---------------------------------------------------------------------------
# Mockup (default mode)
# ---------------------------------------------------------------------------
MOCKUP_HOME = '''
<div id="view-home" data-view="Home" style="display:flex;background:#fafafa;color:#0a0a0a;font-family:system-ui,sans-serif;border-radius:6px;overflow:hidden;min-height:640px;">
  <aside id="c-sidebar" style="width:200px;background:#f3f3f1;padding:14px 12px;border-right:1px solid #e5e5e3;display:flex;flex-direction:column;gap:10px;font-size:11px;">
    <div id="c-brand" style="font-weight:800;font-size:14px;letter-spacing:-0.02em;">inPACT</div>
    <div style="font-size:9px;color:#888;">Self-Sustaining Bullet Journal</div>
    <nav id="c-nav" style="display:flex;flex-direction:column;gap:2px;margin-top:8px;">
      <div style="padding:6px 8px;background:#0a0a0a;color:#fff;border-radius:4px;font-weight:600;">Home</div>
      <div style="padding:6px 8px;color:#555;">Daily</div>
      <div style="padding:6px 8px;color:#555;">Tasks</div>
      <div style="padding:6px 8px;color:#555;">History</div>
    </nav>
    <div id="c-progress" style="margin-top:auto;padding:8px;background:#fff;border-radius:4px;border:1px solid #eee;">
      <div style="font-size:9px;color:#888;text-transform:uppercase;">This week</div>
      <div style="display:flex;justify-content:space-between;margin-top:3px;"><span>Tasks</span><span style="font-weight:700;">3/7</span></div>
      <div style="height:3px;background:#eee;border-radius:2px;margin-top:4px;"><div style="width:43%;height:100%;background:#0a0a0a;border-radius:2px;"></div></div>
    </div>
    <div id="c-actions" style="display:flex;flex-direction:column;gap:2px;border-top:1px solid #e5e5e3;padding-top:8px;">
      <div style="padding:5px 8px;color:#555;">⚙ Settings</div>
      <div style="padding:5px 8px;color:#555;">⬇ Export</div>
    </div>
  </aside>

  <main style="flex:1;padding:24px 32px;overflow:auto;">
    <div id="c-title" style="margin-bottom:18px;">
      <h1 style="font-size:30px;font-weight:800;letter-spacing:-0.02em;margin:0;">Today</h1>
      <div style="color:#666;font-size:13px;margin-top:2px;">Tuesday, April 22, 2026</div>
    </div>
    <div id="c-mission" style="background:linear-gradient(135deg,#0a0a0a,#1a1a1a);color:#fff;padding:14px 16px;border-radius:8px;margin-bottom:14px;">
      <div style="font-size:9px;opacity:0.5;text-transform:uppercase;letter-spacing:0.08em;font-weight:700;">Your Why</div>
      <div style="font-size:13px;opacity:0.92;margin-top:4px;">Pay off the car. Stop trading hours for somebody else's plan.</div>
      <div style="font-size:15px;font-weight:700;margin-top:4px;">Move first, justify later.</div>
    </div>
    <div id="c-yesterday" style="display:inline-block;padding:5px 10px;background:#f3f3f1;border-radius:999px;font-size:11px;margin-bottom:18px;">
      Yesterday: <strong>finish optogon Phase 4</strong> · 3/3 min · 2/3 max
    </div>
    <div style="margin-bottom:6px;"><div style="font-weight:700;font-size:13px;">At a Glance</div></div>
    <div id="c-glance" style="background:#fff;border:1px solid #eee;border-radius:6px;padding:12px;margin-bottom:18px;font-size:11px;">
      <div>Win target: <strong>ship sitepull integration</strong> · Day type: <strong>A</strong></div>
      <div style="margin-top:4px;">A-Z tasks: <strong>12</strong> of <strong>26</strong> done</div>
    </div>
    <div style="margin-bottom:6px;"><div style="font-weight:700;font-size:13px;">Atlas Context</div></div>
    <div id="c-atlas" style="background:#fff;border:1px solid #eee;border-radius:6px;padding:12px;margin-bottom:18px;font-size:11px;">
      <div style="display:flex;gap:12px;"><span style="padding:2px 8px;background:#fef3c7;color:#92400e;border-radius:999px;font-weight:700;font-size:10px;">CLOSURE</span><span style="color:#666;">open loops: 1 · risk: HIGH</span></div>
    </div>
    <div id="c-cta" style="display:flex;justify-content:space-between;align-items:center;background:#0a0a0a;color:#fff;padding:14px 16px;border-radius:8px;margin-bottom:18px;">
      <div>
        <div style="font-weight:700;font-size:13px;">Plan your day</div>
        <div style="font-size:11px;opacity:0.7;">5 minutes. Set the win target before you move.</div>
      </div>
      <button style="padding:6px 14px;background:#fff;color:#0a0a0a;border:0;border-radius:6px;font-weight:700;font-size:11px;">Open Daily</button>
    </div>
    <div id="c-routines" style="background:#fff;border:1px solid #eee;border-radius:6px;padding:12px;margin-bottom:18px;font-size:11px;">
      <div>Morning: <strong>3/4</strong> steps · Shutdown: <strong>0/3</strong> steps</div>
    </div>
    <div id="c-inprogress" style="background:#fff;border:1px solid #eee;border-radius:6px;padding:12px;font-size:11px;">
      <div style="display:flex;align-items:center;gap:8px;"><span style="display:inline-flex;width:18px;height:18px;background:#0a0a0a;color:#fff;border-radius:50%;align-items:center;justify-content:center;font-size:10px;font-weight:700;">A</span><span style="flex:1;">Wire sitepull adapter into Optogon</span><span style="padding:2px 6px;background:#dbeafe;color:#1e40af;border-radius:4px;font-size:9px;font-weight:700;">ACTIVE</span></div>
    </div>
  </main>

  <div id="c-signals" style="position:absolute;bottom:14px;right:14px;background:#fff;border:1px solid #f59e0b;border-radius:6px;padding:8px 12px;font-size:10px;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
    <div style="font-weight:700;color:#92400e;">approval needed</div>
    <div>commit_a_file path waiting</div>
  </div>
</div>
'''

MOCKUP_DAILY = '''
<div id="view-daily" data-view="Daily" style="display:none;background:#fafafa;color:#0a0a0a;font-family:system-ui,sans-serif;border-radius:6px;overflow:hidden;min-height:640px;padding:32px;">
  <div id="d-title">
    <h1 style="font-size:30px;font-weight:800;letter-spacing:-0.02em;margin:0;">Daily Plan</h1>
    <div style="color:#666;font-size:13px;margin-top:2px;">Tuesday, April 22, 2026</div>
  </div>

  <div style="margin-top:22px;font-weight:700;font-size:13px;">Plan Your Day</div>
  <div id="d-win" style="margin-top:10px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;">Win Target</div>
    <input value="ship sitepull integration" style="width:100%;margin-top:6px;padding:8px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;" readonly />
  </div>

  <div id="d-prios" style="margin-top:14px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;">Top 3 Priorities</div>
    <div style="margin-top:6px;display:flex;gap:6px;align-items:center;"><span style="font-weight:700;color:#999;width:14px;">1</span><input value="Wire sitepull into Optogon" style="flex:1;padding:6px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;" readonly /></div>
    <div style="margin-top:6px;display:flex;gap:6px;align-items:center;"><span style="font-weight:700;color:#999;width:14px;">2</span><input value="Fix anatomy-map line refs" style="flex:1;padding:6px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;" readonly /></div>
    <div style="margin-top:6px;display:flex;gap:6px;align-items:center;"><span style="font-weight:700;color:#999;width:14px;">3</span><input value="Ship live mode" style="flex:1;padding:6px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;" readonly /></div>
  </div>

  <div id="d-ways" style="margin-top:14px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;">3 Ways to Win — min / max</div>
    <div style="margin-top:6px;display:flex;gap:6px;"><input value="Min: tests pass" style="flex:1;padding:5px 7px;border:1px solid #ddd;border-radius:4px;font-size:11px;" readonly /><input value="Max: live e2e" style="flex:1;padding:5px 7px;border:1px solid #ddd;border-radius:4px;font-size:11px;" readonly /></div>
  </div>

  <div id="d-lever" style="margin-top:14px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;">The Lever</div>
    <input value="Schema-validated adapter — Optogon trusts the input" style="width:100%;margin-top:6px;padding:8px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;" readonly />
  </div>

  <div id="d-reset" style="margin-top:14px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:#888;">Reset Move</div>
    <input value="walk + water" style="width:100%;margin-top:6px;padding:8px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;" readonly />
  </div>

  <div id="d-protocol" style="margin-top:22px;font-weight:700;font-size:13px;">Daily Operating Protocol</div>
  <div style="margin-top:6px;background:#fff;border:1px solid #eee;border-radius:6px;padding:14px;font-size:11px;color:#666;">Where you are right now in the day.</div>
</div>
'''

LIVE_FRAME = f'''
<div id="view-live" data-view="Live" style="display:none;border-radius:6px;overflow:hidden;background:#000;">
  <div style="padding:6px 10px;background:#111;color:#aaa;font-size:10px;font-family:monospace;display:flex;justify-content:space-between;">
    <span>iframe → <span id="iframe-url">{INPACT_URL}</span></span>
    <span id="iframe-status" style="color:#888;">●  not loaded</span>
  </div>
  <div id="live-iframe-slot" style="width:100%;height:640px;background:#fff;display:flex;align-items:center;justify-content:center;color:#888;font-size:11px;">click "Live (iframe)" again to load</div>
</div>
<script>
  window.__loadLiveIframe = function() {{
    var slot = document.getElementById('live-iframe-slot');
    if (!slot || slot.querySelector('iframe')) return;
    slot.innerHTML = '';
    var f = document.createElement('iframe');
    f.src = '{INPACT_URL}';
    f.style.cssText = 'width:100%;height:640px;border:0;background:#fff;';
    f.onload = function() {{ document.getElementById('iframe-status').style.color='#22c55e'; document.getElementById('iframe-status').textContent='●  live'; }};
    f.onerror = function() {{ document.getElementById('iframe-status').textContent='● offline (start inpact on :3006)'; }};
    slot.appendChild(f);
    document.getElementById('iframe-status').textContent='●  loading...';
  }};
</script>
'''

VIEW_SWITCHER = '''
<div style="display:flex;justify-content:center;gap:8px;margin-bottom:14px;">
  <button class="view-btn on" data-view="Home" onclick="switchView('Home')">Home</button>
  <button class="view-btn"    data-view="Daily" onclick="switchView('Daily')">Daily</button>
  <button class="view-btn"    data-view="Live"  onclick="switchView('Live')">Live (iframe)</button>
</div>
<style>
  .view-btn { padding: 6px 14px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); border-radius: 4px; color: #c8c8c8; font-size: 10px; font-family: inherit; letter-spacing: 1.5px; text-transform: uppercase; cursor: pointer; transition: all .15s ease; }
  .view-btn:hover { background: rgba(192,132,252,0.08); border-color: rgba(192,132,252,0.3); }
  .view-btn.on { background: rgba(192,132,252,0.18); border-color: rgba(192,132,252,0.5); color: #e0d0ff; }
  .callouts-set { display: none; }
  .callouts-set.on { display: contents; }
</style>
<script>
  window.switchView = function(name) {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('on', b.dataset.view === name));
    document.querySelectorAll('[data-view]').forEach(el => {
      if (el.id && el.id.startsWith('view-')) el.style.display = (el.dataset.view === name ? '' : 'none');
    });
    document.querySelectorAll('.callouts-set').forEach(s => s.classList.toggle('on', s.dataset.view === name));
    if (name === 'Live' && window.__loadLiveIframe) window.__loadLiveIframe();
    if (window.redrawLeaders) try { window.redrawLeaders(); } catch (e) {}
  };
</script>
'''

# ---------------------------------------------------------------------------
# Callouts
# ---------------------------------------------------------------------------
def callout(n, target, layer, hd, file, line, dsc):
    file_attr = f'data-file="{file}" data-line="{line}"' if file else ""
    pth = f'{Path(file).name} · L{line}' if file else "external"
    return f'''<div class="callout {layer} clickable" data-target="{target}" data-n="{n}" {file_attr}>
  <span class="no">{n}</span>
  <div class="hd">{hd}</div>
  <div class="pth">{pth}</div>
  <div class="dsc">{dsc}</div>
</div>'''


HOME_LEFT = [
    callout(1, "c-brand",     "ui", "Brand",         "apps/inpact/index.html", 27, "Static brand block in sidebar."),
    callout(2, "c-nav",       "ui", "Nav (dynamic)", "apps/inpact/js/app.js", 1,  "Nav links injected by app.js boot."),
    callout(3, "c-progress",  "ui", "Weekly stat",   "apps/inpact/index.html", 36, "Weekly tasks pill — read from CycleBoardState."),
    callout(4, "c-actions",   "ui", "Sidebar acts",  "apps/inpact/index.html", 53, "Settings + Export. Export dumps state to JSON."),
    callout(5, "c-title",     "ui", "Page title",    "apps/inpact/js/screens.js", 163, "<h1>Today</h1> + formatted date."),
    callout(6, "c-mission",   "ui", "Why pin",       "apps/inpact/js/screens.js", 166, "Mission + motto. Editable on Daily screen."),
    callout(7, "c-yesterday", "ui", "Yesterday",     "apps/inpact/js/screens.js", 174, "Recap pill: target + min/max from prior day."),
]
HOME_RIGHT = [
    callout(8,  "c-glance",     "ui", "At a glance",  "apps/inpact/js/screens.js", 181, "Win target, day type, A-Z totals, week stats."),
    callout(9,  "c-atlas",      "ui", "Atlas card",   "apps/inpact/js/screens.js", 210, "Live governance state. Cached 60s. Hidden if Atlas offline."),
    callout(10, "c-cta",        "ui", "Rhythm CTA",   "apps/inpact/js/screens.js", 218, "Context-aware next-action button."),
    callout(11, "c-routines",   "ui", "Routines",     "apps/inpact/js/screens.js", 234, "Per-routine completion counts. Read-only on Home."),
    callout(12, "c-inprogress", "ui", "In progress",  "apps/inpact/js/screens.js", 248, "First 5 active A-Z tasks. Hidden if none."),
    callout(13, "c-signals",    "ui", "Signal toast", "apps/inpact/js/signals.js", 218, "Boot polling on DOM ready."),
    callout(14, "c-sidebar",    "ui", "Sidebar root", "apps/inpact/index.html", 26, "Hidden on mobile; bottom-nav takes over."),
]

DAILY_LEFT = [
    callout("D1", "d-title",    "ui", "Page header",   "apps/inpact/js/screens.js", 277, "<h1>Daily Plan</h1>."),
    callout("D2", "d-win",      "ui", "Win target",    "apps/inpact/js/screens.js", 288, "input.blur calls saveTodayField('winTarget',...)."),
    callout("D3", "d-prios",    "ui", "Top 3 prios",   "apps/inpact/js/screens.js", 292, "3 priority rows + why field + A-Z / area link selects."),
    callout("D4", "d-ways",     "ui", "3 ways to win", "apps/inpact/js/screens.js", 309, "Min/max pairs per priority."),
]
DAILY_RIGHT = [
    callout("D5", "d-lever",    "ui", "The lever",     "apps/inpact/js/screens.js", 319, "The one outsized action for today."),
    callout("D6", "d-reset",    "ui", "Reset move",    "apps/inpact/js/screens.js", 323, "Cracked-day fallback action."),
    callout("D7", "d-protocol", "ui", "Operating protocol", "apps/inpact/js/screens.js", 328, "Time-block scaffolding for the day."),
]

CHAINS = [
    [
        ("ui",  13,   "c-signals", "Signal toast",                "apps/inpact/js/signals.js", 218, "Boot polling on DOM ready."),
        ("api", "a1", "c-signals", "GET /api/signals",            "apps/inpact/js/signals.js", 184, "Auth header + bounded polling."),
        ("lib", "a2", "c-signals", "delta-kernel /api/signals",   "services/delta-kernel/src/api/server.ts", 2004, "Active Signal.v1 ring buffer."),
        ("ext", "a3", "c-signals", "SQLite (state.db)",           "", 0, "Signals persisted in .delta-fabric/state.db."),
    ],
    [
        ("ui",  9,    "c-atlas", "Atlas card",                    "apps/inpact/js/screens.js", 210, "60s cache, async fill."),
        ("api", "b1", "c-atlas", "GET /api/state/unified",        "apps/inpact/js/api.js", 18,  "AtlasAPI._fetch wrapper."),
        ("lib", "b2", "c-atlas", "delta-kernel unified state",    "services/delta-kernel/src/api/server.ts", 306, "Merges delta + cognitive state."),
        ("ext", "b3", "c-atlas", "cognitive_state.json",          "", 0, "Written by cognitive-sensor refresh.py."),
    ],
    [
        ("ui",  "c0", "c-cta", "Plan field blur",                  "apps/inpact/js/today.js", 236, "input.blur -> save()."),
        ("lib", "c1", "c-cta", "CycleBoardState.update",           "apps/inpact/js/state.js", 1, "Mutates state, persists."),
        ("ext", "c2", "c-cta", "localStorage",                     "", 0, "Browser-local. Export to JSON for portability."),
    ],
    [
        ("ui",  "t1", "c-actions", "Auth fetch",                   "apps/inpact/js/api.js", 22, "_fetch /api/auth/token."),
        ("api", "t2", "c-actions", "GET /api/auth/token",          "apps/inpact/js/signals.js", 26, "Bearer token cached on client."),
        ("lib", "t3", "c-actions", "delta-kernel auth handler",    "services/delta-kernel/src/api/server.ts", 116, "Issues short-lived bearer token."),
    ],
]

# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def render_callout_set(view, items):
    return f'<div class="callouts-set{(" on" if view == "Home" else "")}" data-view="{view}">\n' + "\n".join(items) + "\n</div>"


def main():
    tpl = TEMPLATE.read_text(encoding="utf-8")
    cache = {f: (REPO / f).read_text(encoding="utf-8") for f in SOURCE_FILES}
    cache_json = json.dumps(cache, ensure_ascii=False).replace("</", "<\\/")

    mockup = VIEW_SWITCHER + MOCKUP_HOME + MOCKUP_DAILY + LIVE_FRAME

    left = (
        render_callout_set("Home", HOME_LEFT)
        + render_callout_set("Daily", DAILY_LEFT)
        + render_callout_set("Live", [
            f'<div class="callout ui" style="cursor:default;"><div class="hd">Live mode</div><div class="dsc">Real app embedded. Click around inside the iframe. Annotations are static — switch to Home or Daily to see per-screen callouts.</div></div>'
        ])
    )
    right = (
        render_callout_set("Home", HOME_RIGHT)
        + render_callout_set("Daily", DAILY_RIGHT)
        + render_callout_set("Live", [
            f'<div class="callout api" style="cursor:default;"><div class="hd">Backend</div><div class="dsc">Atlas + delta-kernel chains below stay accurate regardless of which view you are looking at.</div></div>'
        ])
    )

    chains_html = "\n".join(
        '<div class="chain">' + '<span class="chain-arrow">▶</span>'.join(
            callout(n, tgt, layer, hd, f, ln, d) for layer, n, tgt, hd, f, ln, d in chain
        ) + '</div>'
        for chain in CHAINS
    )

    out = (
        tpl.replace("<!-- TEMPLATE:TITLE -->", TITLE)
           .replace("<!-- TEMPLATE:SUBTITLE -->", SUBTITLE)
           .replace("<!-- TEMPLATE:MOCKUP -->", mockup)
           .replace("<!-- TEMPLATE:CALLOUTS_LEFT -->", left)
           .replace("<!-- TEMPLATE:CALLOUTS_RIGHT -->", right)
           .replace("<!-- TEMPLATE:CHAINS -->", chains_html)
           .replace("<!-- TEMPLATE:SOURCE_CACHE -->", cache_json)
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({len(out)} bytes)")


if __name__ == "__main__":
    main()

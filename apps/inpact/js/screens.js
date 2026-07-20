// inPACT Screens Module
// Consolidated 5-screen layout with flow bridges
const screens = [
  { id: 'Home', label: 'Home', icon: 'fa-home' },
  { id: 'Daily', label: 'Daily', icon: 'fa-calendar-day' },
  { id: 'Tasks', label: 'Tasks', icon: 'fa-tasks' },
  { id: 'History', label: 'History', icon: 'fa-history' },
  { id: 'Settings', label: 'Settings', icon: 'fa-cog' }
];

// Track which routine dropdowns are expanded (UI-only, not persisted)
const _expandedRoutines = new Set();

// Atlas governance data cache (60s TTL)
let _atlasCache = { data: null, fetchedAt: 0 };

// Projects data cache (60s TTL) - read from inPACT's same-origin projects.json (written by atlas/gen_github.py)
let _projectsCache = { data: null, fetchedAt: 0 };

// Cortex preparation cache (60s TTL) - powers the "Handle next" card on Home.
// Was previously only reachable inside the "Ask Atlas" modal (ai-actions.js);
// promoted to the main screen per the 2026-07-06 completeness assessment so the
// backend's queued work is visible without an extra click.
let _prepCache = { data: null, fetchedAt: 0 };

function _renderProjectsCard(projects) {
  if (!projects) return '<div style="color:var(--ip-gray-600);font-size:0.8125rem;">Loading projects...</div>';
  const active = projects.filter(p => p.band === 0);
  const list = (active.length ? active : projects).slice(0, 8);
  if (!list.length) return '<div style="color:var(--ip-gray-600);font-size:0.8125rem;">No recent projects found.</div>';
  return list.map(p => `
    <div style="display:flex;align-items:center;gap:0.75rem;padding:0.45rem 0;border-bottom:1px solid var(--ip-gray-100);">
      <div style="flex:1;min-width:0;">
        <div style="font-weight:600;font-size:0.875rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${UI.sanitize(p.name)}</div>
        <div style="font-size:0.75rem;color:var(--ip-gray-600);">${UI.sanitize(p.lang || '')} . ${UI.sanitize(p.updated || '')}</div>
      </div>
      <button class="td-btn" style="padding:0.25rem 0.625rem;font-size:0.75rem;flex-shrink:0;" data-name="${UI.sanitize(p.name)}" onclick="addProjectTask(this.dataset.name)">Add as task</button>
    </div>
  `).join('');
}

// Strategic HUD: command-center strip at the top of Home.
// Governance tiles (mode/risk/open-loops/closure/streak) come from the live Atlas
// backend via _atlasCache; execution tiles come from local state. Ported from
// CycleBoard's Strategic HUD, kept honest: only real, data-backed signals are shown.
function _renderStrategicHud() {
  // --- Governance (from Atlas cache, if loaded) ---
  const data = _atlasCache.data;
  const u = data && data.unified;
  const b = data && data.brief;
  const online = typeof AtlasAPI !== 'undefined' && AtlasAPI.online;

  // Governance lives in unified.derived: { mode, risk, open_loops, closure_ratio, streak_days, primary_order }.
  const d = u ? (u.derived || u.data?.derived || null) : null;
  const mode = d ? (d.mode || 'UNKNOWN') : null;
  const risk = d ? (d.risk || d.risk_level || null) : null;
  const openLoops = d ? (d.open_loops ?? null) : null;
  const closureRaw = d ? (d.closure_ratio ?? null) : null;
  // closure_ratio is a 0-1 ratio in derived; normalize to a percentage for display.
  const closurePct = closureRaw == null ? null : Math.round(closureRaw <= 1 ? closureRaw * 100 : closureRaw);
  const streak = d ? (d.streak_days ?? d.streak ?? null) : null;
  const directive = (d && d.primary_order) || (b ? (b.directive || b.data?.directive || b.data?.daily_directive || '') : '');

  const modeColors = {
    RECOVER: '#ef4444', CLOSURE: '#f59e0b', MAINTENANCE: '#6b7280',
    BUILD: '#3b82f6', COMPOUND: '#8b5cf6', SCALE: '#22c55e'
  };
  const modeColor = modeColors[mode] || 'var(--ip-gray-600)';

  const riskKey = (risk || '').toString().toUpperCase();
  const riskColor = riskKey === 'HIGH' ? '#ef4444'
    : (riskKey === 'MEDIUM' || riskKey === 'MED') ? '#f59e0b'
    : riskKey === 'LOW' ? '#22c55e' : 'var(--ip-black)';
  const redAlert = riskKey === 'HIGH';

  // --- Execution (always available from local state) ---
  const azDone = state.AZTask.filter(t => t.status === 'Completed').length;
  const azTotal = state.AZTask.length;
  const weekly = Helpers.getWeeklyStats();
  const todayDate = stateManager.getTodayDate();
  const todayData = state.Today?.daily?.[todayDate] || {};
  const winSet = !!todayData.winTarget;

  const tile = (label, value, color) => `
    <div style="text-align:center;padding:0.625rem 0.5rem;border-radius:0.625rem;background:var(--ip-gray-50);border:1px solid var(--ip-gray-100);">
      <div style="font-size:1.25rem;font-weight:800;line-height:1;color:${color || 'var(--ip-black)'};">${value}</div>
      <div style="font-size:0.625rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--ip-gray-600);margin-top:0.375rem;">${label}</div>
    </div>`;

  const govTiles = d ? [
    tile('Risk', riskKey || '--', riskColor),
    tile('Open loops', openLoops != null ? openLoops : '--'),
    tile('Closure', closurePct != null ? closurePct + '%' : '--'),
    tile('Streak', streak != null ? streak + 'd' : '--'),
  ].join('') : '';

  const execTiles = [
    tile('A-Z done', azTotal ? (azDone + '/' + azTotal) : '0'),
    tile('Week base', weekly.completed + '/' + weekly.total),
    tile('Today win', winSet ? 'set' : '—', winSet ? '#22c55e' : 'var(--ip-gray-300)'),
  ].join('');

  const statusNote = d ? '' : (online
    ? '<div style="font-size:0.75rem;color:var(--ip-gray-600);margin-top:0.75rem;">Syncing governance from Atlas...</div>'
    : '<div style="font-size:0.75rem;color:var(--ip-gray-600);margin-top:0.75rem;">Governance: local only (Atlas not connected). Execution metrics are live.</div>');

  return `
    <div style="border:1px solid ${redAlert ? 'rgba(239,68,68,0.5)' : 'var(--ip-gray-200)'};border-radius:0.875rem;padding:1.125rem;margin-bottom:2rem;${redAlert ? 'box-shadow:0 0 0 3px rgba(239,68,68,0.08);' : ''}">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.875rem;">
        <div style="display:flex;align-items:center;gap:0.5rem;">
          <i class="fas fa-satellite-dish" style="color:var(--ip-gray-600);font-size:0.8125rem;"></i>
          <span style="font-size:0.6875rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);">Strategic HUD</span>
        </div>
        ${mode ? `<span style="background:${modeColor};color:#fff;font-size:0.6875rem;font-weight:700;padding:0.1875rem 0.625rem;border-radius:9999px;letter-spacing:0.05em;">${mode}</span>` : '<span style="font-size:0.6875rem;color:var(--ip-gray-300);">no mode</span>'}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(4.5rem,1fr));gap:0.5rem;">
        ${govTiles}${execTiles}
      </div>
      ${directive ? `<div style="font-size:0.8125rem;line-height:1.4;margin-top:0.875rem;padding-top:0.75rem;border-top:1px solid var(--ip-gray-100);"><strong>Directive:</strong> ${typeof UI !== 'undefined' ? UI.sanitize(directive) : directive}</div>` : ''}
      ${redAlert ? '<div style="font-size:0.75rem;color:#b91c1c;margin-top:0.75rem;font-weight:600;"><i class="fas fa-triangle-exclamation" style="margin-right:0.375rem;"></i>Risk is HIGH. Close loops before opening new ones.</div>' : ''}
      ${statusNote}
    </div>`;
}

// Statistics section for the History screen. Pure views over local data
// (A-Z tasks, day plans, weekly stats, 7-day progress). No backend needed.
function _renderStatsSection() {
  const az = state.AZTask || [];
  const done = az.filter(t => t.status === 'Completed').length;
  const prog = az.filter(t => t.status === 'In Progress').length;
  const todo = az.filter(t => t.status === 'Not Started').length;
  const total = az.length;
  const weekly = Helpers.getWeeklyStats();
  const streak = Helpers.getProgressStreak();
  const planned = Object.keys(state.DayPlans || {}).length;
  const dayTypes = { A: 0, B: 0, C: 0 };
  Object.values(state.DayPlans || {}).forEach(p => { if (p && dayTypes[p.day_type] != null) dayTypes[p.day_type]++; });
  const hist = Helpers.getProgressHistory(7);

  const tile = (label, value) => `
    <div style="text-align:center;padding:0.75rem 0.5rem;border-radius:0.625rem;background:var(--ip-gray-50);border:1px solid var(--ip-gray-100);">
      <div style="font-size:1.375rem;font-weight:800;line-height:1;">${value}</div>
      <div style="font-size:0.625rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--ip-gray-600);margin-top:0.375rem;">${label}</div>
    </div>`;

  const bar = (label, value, max, color) => {
    const pct = max ? Math.round((value / max) * 100) : 0;
    return `
      <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;">
        <span style="width:6.5rem;font-size:0.8125rem;color:var(--ip-gray-700);">${label}</span>
        <div style="flex:1;height:0.5rem;background:var(--ip-gray-100);border-radius:9999px;overflow:hidden;">
          <div style="height:100%;width:${pct}%;background:${color};border-radius:9999px;"></div>
        </div>
        <span style="width:2.5rem;text-align:right;font-size:0.8125rem;font-weight:700;">${value}</span>
      </div>`;
  };

  const maxP = Math.max(10, ...hist.map(h => h.progress));
  const spark = hist.map(h => {
    const hpx = Math.max(2, Math.round((h.progress / maxP) * 36));
    return `<div title="${h.dateFormatted}: ${h.progress}%" style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:0.25rem;">
      <div style="width:100%;max-width:1.75rem;height:${hpx}px;background:${h.hasData ? 'var(--ip-black)' : 'var(--ip-gray-200)'};border-radius:0.25rem;"></div>
      <span style="font-size:0.5625rem;color:var(--ip-gray-600);">${h.date.slice(8)}</span>
    </div>`;
  }).join('');

  return `
    <div class="td-chapter" style="margin-top:0;">
      <span class="td-chapter-title">Statistics</span>
      <span class="td-chapter-sub">How you're trending.</span>
    </div>
    <div class="td-section">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(5rem,1fr));gap:0.5rem;margin-bottom:1.25rem;">
        ${tile('A-Z done', total ? done + '/' + total : '0')}
        ${tile('This week', weekly.completed + '/' + weekly.total)}
        ${tile('Streak', streak + 'd')}
        ${tile('Days planned', planned)}
      </div>
      <div style="font-size:0.6875rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--ip-gray-600);margin-bottom:0.5rem;">Task status</div>
      ${bar('Completed', done, total, '#22c55e')}
      ${bar('In progress', prog, total, 'var(--ip-gray-600)')}
      ${bar('Not started', todo, total, 'var(--ip-gray-300)')}
      <div style="font-size:0.6875rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--ip-gray-600);margin:1.25rem 0 0.5rem;">Day type usage</div>
      ${bar('A days', dayTypes.A, planned, 'var(--ip-black)')}
      ${bar('B days', dayTypes.B, planned, 'var(--ip-gray-600)')}
      ${bar('C days', dayTypes.C, planned, 'var(--ip-gray-300)')}
      <div style="font-size:0.6875rem;text-transform:uppercase;letter-spacing:0.06em;color:var(--ip-gray-600);margin:1.25rem 0 0.5rem;">Last 7 days</div>
      <div style="display:flex;align-items:flex-end;gap:0.375rem;height:3rem;">${spark}</div>
    </div>`;
}

// Activity timeline for the History screen. Reads state.History.timeline
// (populated by Helpers.logActivity, including AI actions).
function _renderTimelineSection() {
  const tl = (state.History && state.History.timeline) || [];
  const recent = tl.slice().reverse().slice(0, 20);
  const iconFor = (type) => {
    type = String(type || '');
    if (/complete/i.test(type)) return 'fa-check';
    if (/create|add/i.test(type)) return 'fa-plus';
    if (/ai_/i.test(type)) return 'fa-robot';
    if (/status/i.test(type)) return 'fa-arrows-rotate';
    return 'fa-circle';
  };
  const relTime = (iso) => {
    const d = new Date(iso); const now = new Date();
    const mins = Math.round((now - d) / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return mins + 'm ago';
    const hrs = Math.round(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    const days = Math.round(hrs / 24);
    if (days < 7) return days + 'd ago';
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  const rows = recent.length ? recent.map(a => `
    <div style="display:flex;align-items:flex-start;gap:0.75rem;padding:0.5rem 0;border-bottom:1px solid var(--ip-gray-100);">
      <div style="flex-shrink:0;width:1.75rem;height:1.75rem;border-radius:50%;background:var(--ip-gray-100);display:flex;align-items:center;justify-content:center;color:var(--ip-gray-600);font-size:0.6875rem;"><i class="fas ${iconFor(a.type)}"></i></div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:0.875rem;line-height:1.4;">${UI.sanitize(a.description || a.type || 'activity')}</div>
        <div style="font-size:0.6875rem;color:var(--ip-gray-600);">${relTime(a.timestamp)}</div>
      </div>
    </div>`).join('') : '<div style="color:var(--ip-gray-600);font-size:0.8125rem;">No activity yet. Actions you and Atlas take will appear here.</div>';

  return `
    <div class="td-chapter">
      <span class="td-chapter-title">Activity Timeline</span>
      <span class="td-chapter-sub">What you and Atlas have done${recent.length ? ' (recent ' + recent.length + ')' : ''}.</span>
    </div>
    <div class="td-section">${rows}</div>`;
}

function toggleRoutineDropdown(blockId) {
  if (_expandedRoutines.has(blockId)) {
    _expandedRoutines.delete(blockId);
  } else {
    _expandedRoutines.add(blockId);
  }
  render();
}

function renderNav() {
  const nav = document.getElementById('nav');
  if (!nav) return;

  nav.innerHTML = screens
    .filter(s => s.id !== 'Settings') // Settings is in sidebar footer
    .map(s => `
    <button
      onclick="navigate('${s.id}')"
      class="sb-nav-item${state.screen === s.id ? ' active' : ''}"
    >
      <i class="fas ${s.icon}"></i>
      <span>${s.label}</span>
    </button>
  `).join('') + `
    <a href="http://127.0.0.1:8887/pages/github.html" class="sb-nav-item" aria-label="Go to Projects">
      <i class="fas fa-folder-open"></i>
      <span>Projects</span>
    </a>
  `;

  // Atlas connection status
  const statusEl = document.getElementById('atlas-status');
  if (statusEl) {
    const on = typeof AtlasAPI !== 'undefined' && AtlasAPI.online;
    statusEl.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.375rem;font-size:0.75rem;color:var(--ip-gray-600);">
        <span style="width:6px;height:6px;border-radius:50%;background:${on ? '#22c55e' : '#eab308'};"></span>
        ${on ? 'Synced' : 'Local only'}
      </div>
    `;
  }

  // Update weekly progress
  const weeklyStats = Helpers.getWeeklyStats();
  const weeklyTasksEl = document.getElementById('weekly-tasks');
  const weeklyProgressBarEl = document.getElementById('weekly-progress-bar');
  if (weeklyTasksEl) weeklyTasksEl.textContent = `${weeklyStats.completed}/${weeklyStats.total}`;
  if (weeklyProgressBarEl) weeklyProgressBarEl.style.width = `${weeklyStats.percentage}%`;

  // Highlight active mobile tab
  document.querySelectorAll('.sb-mobile-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === state.screen);
  });
}

function navigate(screen) {
  // Map old screen IDs to new ones for backward compat
  const screenMap = { AtoZ: 'Tasks', WeeklyFocus: 'Tasks', Routines: 'Daily', Journal: 'History', Reflections: 'History', Calendar: 'History' };
  const target = screenMap[screen] || screen;
  state.screen = target;
  stateManager.update({ screen: state.screen });
  render();

  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.classList.contains('block')) {
    sidebar.classList.remove('block');
    sidebar.classList.add('hidden');
  }
}

// Escape a value used as a quoted JS argument inside an inline handler attribute.
// UI.sanitize is not enough here: it escapes & < > only (textContent -> innerHTML),
// so a quote in the value breaks out of both the JS string and the attribute.
// Routine names are free user text (functions.js:941) and also arrive from synced
// state, so they get escaped rather than trusted.
function _jsAttrArg(value) {
  return String(value)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// Helper: find routine match for a time block title
function _findRoutineMatch(blockTitle) {
  return Object.keys(state.Routine).find(name =>
    blockTitle.toLowerCase().includes(name.toLowerCase())
  );
}

// Collapsible chapters. Daily stacks ~30 inputs in one column; opening all of it at
// once is the density problem. Each chapter remembers its own open/closed state, so
// the page you come back to is the page you left. Native <details> does the work.
const _CHAP_KEY = 'inpact-chapters-open';

function _chapterState() {
  try { return JSON.parse(localStorage.getItem(_CHAP_KEY)) || {}; } catch (e) { return {}; }
}

function _setChapterOpen(key, isOpen) {
  const m = _chapterState();
  m[key] = isOpen;
  try { localStorage.setItem(_CHAP_KEY, JSON.stringify(m)); } catch (e) { /* quota: forget it */ }
}

function _chapterOpen(key, title, sub, defaultOpen) {
  const saved = _chapterState()[key];
  const open = saved === undefined ? !!defaultOpen : saved;
  return `
    <details class="td-chap" data-chap="${key}"${open ? ' open' : ''}>
      <summary class="td-chapter td-chap-summary">
        <span class="td-chapter-title">${title}</span>
        <span class="td-chapter-sub">${sub}</span>
        <span class="td-chap-caret" aria-hidden="true"></span>
      </summary>
      <div class="td-section">`;
}

function _chapterClose() {
  return `</div></details>`;
}

// 'toggle' doesn't bubble, so capture it. Registered once, survives every re-render.
document.addEventListener('toggle', function (e) {
  const d = e.target;
  if (!d || !d.matches || !d.matches('details.td-chap[data-chap]')) return;
  _setChapterOpen(d.getAttribute('data-chap'), d.open);
}, true);

// Helper: the [ Minimal ] [ Full Plan ] lens toggle inside the Daily header
function _dailyViewToggle(active) {
  const btn = (view, label) => `
    <button onclick="setDailyView('${view}')" class="td-btn-pill ${active === view ? 'active' : ''}"
            aria-pressed="${active === view}">${label}</button>
  `;
  return `
    <div class="ip-view-toggle" role="group" aria-label="Daily view">
      ${btn('minimal', 'Minimal')}${btn('medium', 'Medium')}${btn('full', 'Full Plan')}
    </div>
  `;
}

// Helper: bridge links at bottom of screen
function _bridges(links) {
  return `
    <div style="display:flex;flex-direction:column;gap:0.25rem;margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--ip-gray-200);">
      ${links.map(l => `<a href="#" onclick="event.preventDefault();navigate('${l.screen}')" style="font-size:0.8125rem;color:var(--ip-gray-600);text-decoration:none;border-bottom:1px dotted var(--ip-gray-300);">${l.text}</a>`).join('')}
    </div>
  `;
}

const ScreenRenderers = {
  // =========================================================================
  // HOME
  // =========================================================================
  Home() {
    // Auto-redirect new users to onboarding
    if (!state.onboardingDone && (!state.AZTask || state.AZTask.length <= 2)) {
      window.location.href = 'onboarding.html';
      return '<div style="padding:3rem;color:var(--ip-gray-600);">Redirecting to setup...</div>';
    }

    const todayPlan = Helpers.getDayPlan();
    const todayDate = stateManager.getTodayDate();
    const todayData = state.Today?.daily?.[todayDate] || {};

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yStr = yesterday.toISOString().slice(0, 10);
    const yData = state.Today?.daily?.[yStr] || null;

    const mission = state.Today?.mission || '';
    const motto = state.Today?.motto || '';
    const weeklyStats = Helpers.getWeeklyStats();

    let yesterdayHtml = '<span style="font-style:italic;color:var(--ip-gray-600)">No entry yesterday. Start fresh.</span>';
    if (yData && yData.winTarget) {
      const wins = ['x1','x2','x3'].filter(k => yData[k]).length;
      const stretches = ['y1','y2','y3'].filter(k => yData[k]).length;
      yesterdayHtml = `Yesterday: <strong>${UI.sanitize(yData.winTarget).slice(0, 40)}</strong> . ${wins}/3 min . ${stretches}/3 max`;
    }

    return `
      <div style="max-width:48rem;">
        <h1 style="font-size:2.25rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:0.25rem;">Today</h1>
        <div style="color:var(--ip-gray-600);font-size:0.9375rem;margin-bottom:1.75rem;">${Helpers.formatDate(todayDate)}</div>

        ${mission || motto ? `
          <div class="td-mission" style="margin-bottom:1.75rem;">
            <span class="td-mission-eyebrow">Your Why</span>
            ${mission ? `<div style="font-size:0.9375rem;line-height:1.4;font-weight:500;opacity:0.92;">${UI.sanitize(mission)}</div>` : ''}
            ${motto ? `<div style="font-size:1.0625rem;line-height:1.3;font-weight:700;letter-spacing:-0.01em;">${UI.sanitize(motto)}</div>` : ''}
          </div>
        ` : ''}

        <div class="td-pill" style="margin-bottom:2rem;">${yesterdayHtml}</div>

        <div id="strategic-hud">${_renderStrategicHud()}</div>

        <div id="handle-next-card">${_renderHandleNext(_prepCache.data)}</div>
        ${(() => {
          const atlasOnline = typeof AtlasAPI !== 'undefined' && AtlasAPI.online;
          if (atlasOnline && Date.now() - _prepCache.fetchedAt > 60000) {
            AtlasAPI.getPreparation().then(prep => {
              _prepCache = { data: prep, fetchedAt: Date.now() };
              const el = document.getElementById('handle-next-card');
              if (el) el.innerHTML = _renderHandleNext(_prepCache.data);
            }).catch(() => {});
          }
          return '';
        })()}

        <div class="td-chapter" style="margin-top:1.5rem;">
          <span class="td-chapter-title">At a Glance</span>
          <span class="td-chapter-sub">Where things stand right now.</span>
        </div>

        <div class="td-section">
          <div class="td-stat">
            Win target: <strong>${todayData.winTarget ? UI.sanitize(todayData.winTarget) : '(not set)'}</strong>
            . Day type: <strong>${todayPlan.day_type || 'A'}</strong>
          </div>
          <div class="td-stat">
            A-Z tasks: <strong>${state.AZTask.filter(t => t.status === 'Completed').length}</strong> of <strong>${state.AZTask.length}</strong> done
            . Week: <strong>${weeklyStats.completed}</strong> of <strong>${weeklyStats.total}</strong> days met baseline
          </div>
        </div>

        ${(() => {
          // Strategic HUD data source: fetch live governance, then refresh the HUD in place.
          const atlasOnline = typeof AtlasAPI !== 'undefined' && AtlasAPI.online;
          if (atlasOnline && Date.now() - _atlasCache.fetchedAt > 60000) {
            Promise.all([
              AtlasAPI.getUnifiedState(),
              AtlasAPI.getDailyBrief(),
            ]).then(([unified, brief]) => {
              _atlasCache = { data: { unified, brief }, fetchedAt: Date.now() };
              const el = document.getElementById('strategic-hud');
              if (el) el.innerHTML = _renderStrategicHud();
            }).catch(() => {});
          }
          return '';
        })()}

        ${(() => {
          if (Date.now() - _projectsCache.fetchedAt > 60000) {
            fetch('projects.json').then(r => r.ok ? r.json() : null).then(data => {
              if (!data) return;
              _projectsCache = { data, fetchedAt: Date.now() };
              const el = document.getElementById('projects-card');
              if (el) el.innerHTML = _renderProjectsCard(_projectsCache.data);
            }).catch(() => {});
          }
          const cached = _projectsCache.data ? _renderProjectsCard(_projectsCache.data) : '';
          return `
            <div class="td-chapter">
              <span class="td-chapter-title">Active Projects</span>
              <span class="td-chapter-sub">Recent work from your machine. Add one to your tasks.</span>
            </div>
            <div class="td-section" id="projects-card">
              ${cached || '<div style="color:var(--ip-gray-600);font-size:0.8125rem;">Loading projects...</div>'}
            </div>
          `;
        })()}

        ${(() => {
          const cta = getRhythmAction();
          return `
            <div class="td-cta">
              <div class="td-cta-text">
                <div class="td-cta-headline">${cta.headline}</div>
                <div class="td-cta-sub">${cta.subtext}</div>
              </div>
              <button class="td-btn" onclick="${cta.action}">${cta.buttonText}</button>
            </div>
          `;
        })()}

        <div class="td-chapter">
          <span class="td-chapter-title">Today's Routines</span>
          <span class="td-chapter-sub">Check off what you've done.</span>
        </div>

        <div class="td-section">
          ${Object.keys(state.Routine).map(name => {
            const steps = state.Routine[name];
            const completion = todayPlan.routines_completed?.[name] || { completed: false, steps: {} };
            const done = Object.values(completion.steps || {}).filter(Boolean).length;
            return `<div class="td-stat">${UI.sanitize(name)}: <strong>${done}/${steps.length}</strong> steps${completion.completed ? ' (done)' : ''}</div>`;
          }).join('')}
        </div>

        ${state.AZTask.filter(t => t.status === 'In Progress').length > 0 ? `
          <div class="td-chapter">
            <span class="td-chapter-title">In Progress</span>
            <span class="td-chapter-sub">Tasks you're working on.</span>
          </div>
          <div class="td-section">
            ${state.AZTask.filter(t => t.status === 'In Progress').slice(0, 5).map(t => `
              <div class="td-row">
                <div class="td-letter">${t.letter}</div>
                <span style="flex:1;font-size:0.9375rem;">${UI.sanitize(t.task)}</span>
                <span class="td-status td-status-progress">active</span>
              </div>
            `).join('')}
          </div>
        ` : ''}

        <!-- Stream: live Signal.v1 feed from the Optogon stack (Ship Target #1).
             Populated by apps/inpact/js/signals.js on poll. Rule 6: only signals
             that don't require attention are listed here; urgent/approval/error
             surface in the floating banner. -->
        <div class="td-chapter">
          <span class="td-chapter-title">Stream</span>
          <span class="td-chapter-sub">Recent activity from your stack.</span>
        </div>
        <div class="td-section" id="ip-stream-list" data-empty-text="Nothing flowing right now. The system will stream completions and status here as it works.">
          <div style="color:var(--ip-gray-600);font-size:0.8125rem;">Nothing flowing right now. The system will stream completions and status here as it works.</div>
        </div>
      </div>
    `;
  },

  // =========================================================================
  // DAILY (plan your day + execution scaffolding)
  // =========================================================================
  // Daily has two lenses over the same DayPlan. Minimal is the execution view
  // (what to do now); Full is the planning view. state.UI.dailyView picks.
  Daily() {
    const plan = Helpers.getDayPlan();
    if (state.UI?.dailyView === 'minimal') return this.renderDailyMinimal(plan);
    return this.renderDailyFull(plan);
  },

  renderDailyFull(todayPlan) {
    const todayDate = stateManager.getTodayDate();
    const dailyProgress = Helpers.calculateDailyProgress();
    const td = getTodayFields();
    const isMedium = state.UI?.dailyView === 'medium';

    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const yesterdayPlan = state.DayPlans[yesterday.toISOString().slice(0, 10)];

    return `
      <div style="max-width:48rem;">
        ${_dailyViewToggle(isMedium ? 'medium' : 'full')}
        <h1 style="font-size:2.25rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:0.25rem;">Daily Plan</h1>
        <div style="color:var(--ip-gray-600);font-size:0.9375rem;margin-bottom:1.75rem;">${Helpers.formatDate(todayPlan.date)}</div>

        <!-- Plan Your Day . the morning ritual fields -->
        ${_chapterOpen('plan', 'Plan Your Day', 'Set your target and priorities before you move.', true)}
          <div class="td-label">Win Target <span class="td-label-step">Step 5</span></div>
          <div class="td-help">What's the one thing that makes today count? Not a list. The thing.</div>
          <input type="text" class="td-input" value="${UI.sanitize(td.winTarget || '')}" placeholder="The one outcome that makes today a win." onblur="saveTodayField('winTarget', this.value)" style="margin-bottom:1.25rem;" />

          <div class="td-label">Top 3 Priorities <span class="td-label-step">Steps 3+7</span></div>
          <div class="td-help">What are you actually doing today? Link each to an A-Z task or PIGPEN area.</div>
          ${[1,2,3].map(i => `
            <div style="margin-bottom:0.75rem;">
              <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem;">
                <span style="font-size:0.875rem;font-weight:700;color:var(--ip-gray-300);width:1.25rem;">${i}</span>
                <input type="text" class="td-input" value="${UI.sanitize(td['p'+i] || '')}" placeholder="Priority ${i}" onblur="saveTodayField('p${i}', this.value)" style="flex:1;" />
                ${td['p'+i+'TaskId'] ? `<button class="td-btn" style="font-size:0.75rem;padding:0.3rem 0.625rem;flex-shrink:0;" title="Completes the real Atlas task, not just this text" onclick="completeSeededPriority(${i})">Done</button>` : ''}
              </div>
              ${isMedium ? '' : `<div style="display:flex;align-items:center;gap:0.5rem;padding-left:1.75rem;">
                <input type="text" class="td-input" value="${UI.sanitize(td['p'+i+'why'] || '')}" placeholder="Why this matters" onblur="saveTodayField('p${i}why', this.value)" style="flex:1;font-size:0.8125rem;padding:0.5rem 0.625rem;" />
                <span style="font-size:0.625rem;color:var(--ip-gray-300);text-transform:uppercase;letter-spacing:0.06em;">Link:</span>
                ${buildLinkSelect('az', i)}
                ${buildLinkSelect('area', i)}
              </div>`}
            </div>
          `).join('')}

          ${isMedium ? '' : `<div class="td-label" style="margin-top:1.25rem;">3 Ways to Win <span class="td-label-step">Min / Max</span></div>
          <div class="td-help">Three win conditions. Min is the floor, max is the stretch.</div>
          ${[1,2,3].map(i => `
            <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.375rem;">
              <span style="font-size:0.8125rem;font-weight:700;color:var(--ip-gray-300);width:1.25rem;">${i}</span>
              <input type="text" class="td-input" value="${UI.sanitize(td['x'+i] || '')}" placeholder="Min" onblur="saveTodayField('x${i}', this.value)" style="flex:1;font-size:0.8125rem;padding:0.5rem 0.625rem;" />
              <input type="text" class="td-input" value="${UI.sanitize(td['y'+i] || '')}" placeholder="Max" onblur="saveTodayField('y${i}', this.value)" style="flex:1;font-size:0.8125rem;padding:0.5rem 0.625rem;" />
            </div>
          `).join('')}`}

          <div class="td-label" style="margin-top:1.25rem;">The Lever</div>
          <div class="td-help">What are you pulling today? The one action with outsized impact.</div>
          <input type="text" class="td-input" value="${UI.sanitize(td.lever || '')}" placeholder="The lever you're pulling today" onblur="saveTodayField('lever', this.value)" style="margin-bottom:0.75rem;" />

          <div class="td-label">Reset Move</div>
          <div class="td-help">When the day cracks, what's your move? Walk, music, 5 breaths.</div>
          <input type="text" class="td-input" value="${UI.sanitize(td.resetMove || '')}" placeholder="Your reset move when things crack" onblur="saveTodayField('resetMove', this.value)" />
        ${_chapterClose()}

        <!-- Daily Operating Protocol . where you are in the day -->
        ${isMedium ? '' : `${_chapterOpen('protocol', 'Daily Operating Protocol', 'Where you are right now.', false)}
          ${(() => {
            const hour = new Date().getHours();
            const blocks = [
              { label: 'Morning Scan', time: '5-7am', start: 5, end: 7, desc: 'Dashboard review, red-alert check, priorities confirmed' },
              { label: 'Deep Work', time: '7-12pm', start: 7, end: 12, desc: 'High-leverage project execution (protected block)' },
              { label: 'Midday Check-in', time: '12-1pm', start: 12, end: 13, desc: 'Energy check, nutrition, micro-rest' },
              { label: 'Afternoon', time: '1-5pm', start: 13, end: 17, desc: 'Continuation or household navigation' },
              { label: 'Evening Ops', time: '5-7pm', start: 17, end: 19, desc: 'Finance tracking, mobility checks, household tasks' },
              { label: 'Night Audit', time: '7-9pm', start: 19, end: 21, desc: 'Daily audit, journal, prep tomorrow' },
              { label: 'Close', time: '9-10pm', start: 21, end: 22, desc: 'Energy recovery, plan next day' },
            ];
            return blocks.map(b => {
              const active = hour >= b.start && hour < b.end;
              return `
                <div class="td-row" style="padding:0.375rem 0;${active ? 'background:var(--ip-gray-50);margin:0 -0.5rem;padding:0.5rem;border-radius:0.375rem;' : ''}">
                  <span style="font-size:0.8125rem;font-weight:${active ? '700' : '500'};color:${active ? 'var(--ip-black)' : 'var(--ip-gray-600)'};width:5rem;flex-shrink:0;">${b.time}</span>
                  <span style="font-size:0.8125rem;font-weight:${active ? '700' : '500'};color:${active ? 'var(--ip-black)' : 'var(--ip-gray-700)'};">${b.label}${active ? ' (now)' : ''}</span>
                  ${active ? `<span style="font-size:0.75rem;color:var(--ip-gray-600);margin-left:auto;">${b.desc}</span>` : ''}
                </div>
              `;
            }).join('');
          })()}
        ${_chapterClose()}`}

        ${isMedium ? '' : `${_chapterOpen('daymode', 'Day Mode', 'What kind of day is it?', false)}
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;">
            ${['A', 'B', 'C'].map(type => `
              <button onclick="setDayType('${type}')" class="td-btn-pill ${todayPlan.day_type === type ? 'active' : ''}" style="padding:0.625rem 1.25rem;font-size:0.875rem;">
                ${type} Day ${type === 'A' ? '(Deep Focus)' : type === 'B' ? '(Balanced)' : '(Recovery)'}
              </button>
            `).join('')}
          </div>
        ${_chapterClose()}`}

        <!-- Time Blocks with routine dropdowns -->
        ${_chapterOpen('blocks', 'Time Blocks', 'Build the scaffolding for the day.', true)}
          <div class="td-help" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;">
            <span>Each block is a bet on what you'll do when. Check it off when it's done.</span>
            ${typeof CalendarSync !== 'undefined' ? CalendarSync.renderSyncButton() : ''}
          </div>
          ${todayPlan.time_blocks.map(block => {
            const routineMatch = _findRoutineMatch(block.title);
            const isExpanded = _expandedRoutines.has(block.id);
            const completion = routineMatch ? (todayPlan.routines_completed?.[routineMatch] || { completed: false, steps: {} }) : null;
            const routineSteps = routineMatch ? state.Routine[routineMatch] : [];

            return `
              <div class="td-row" style="flex-wrap:wrap;">
                <button onclick="toggleTimeBlockCompletion('${block.id}')" class="td-check ${block.completed ? 'checked' : ''}">
                  ${block.completed ? '<i class="fas fa-check" style="font-size:0.625rem"></i>' : ''}
                </button>
                <input type="time" value="${convertTo24Hour(block.time)}" onchange="updateTimeBlock('${block.id}', 'time', this.value)" class="td-input" style="width:7rem;padding:0.5rem;font-size:0.8125rem;font-family:monospace;" />
                <input type="text" value="${UI.sanitize(block.title)}" onchange="updateTimeBlock('${block.id}', 'title', this.value)" class="td-input" style="flex:1;" placeholder="What are you doing?" />
                ${routineMatch ? `
                  <button onclick="toggleRoutineDropdown('${block.id}')" style="background:none;border:none;cursor:pointer;color:var(--ip-gray-600);padding:0.25rem;font-size:0.75rem;" title="Expand ${routineMatch} routine">
                    <i class="fas fa-chevron-${isExpanded ? 'up' : 'down'}"></i>
                  </button>
                ` : ''}
                <button onclick="removeTimeBlock('${block.id}')" style="color:#dc2626;background:none;border:none;cursor:pointer;padding:0.25rem;font-size:0.75rem;">
                  <i class="fas fa-times"></i>
                </button>
                ${routineMatch && isExpanded ? `
                  <div style="width:100%;padding:0.5rem 0 0.5rem 3.5rem;">
                    <div style="font-size:0.6875rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);margin-bottom:0.5rem;">
                      ${UI.sanitize(routineMatch)} Routine . ${Object.values(completion.steps || {}).filter(Boolean).length}/${routineSteps.length} steps
                    </div>
                    ${routineSteps.map((step, idx) => `
                      <label style="display:flex;align-items:center;gap:0.5rem;padding:0.25rem 0;cursor:pointer;">
                        <input type="checkbox" ${completion.steps?.[idx] ? 'checked' : ''} onchange="toggleRoutineStep('${_jsAttrArg(routineMatch)}', ${idx}, this.checked)" style="width:0.875rem;height:0.875rem;accent-color:var(--ip-black);" />
                        <span style="font-size:0.8125rem;color:var(--ip-gray-700);${completion.steps?.[idx] ? 'text-decoration:line-through;opacity:0.5;' : ''}">${UI.sanitize(step)}</span>
                      </label>
                    `).join('')}
                  </div>
                ` : ''}
              </div>
            `;
          }).join('')}
          <div style="margin-top:0.75rem;">
            <button onclick="addTimeBlock()" class="td-btn-ghost" style="width:100%;text-align:center;">
              <i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>Add block
            </button>
          </div>
        ${_chapterClose()}

        <!-- Goals -->
        ${_chapterOpen('goals', 'Goals', 'X is the floor. Y is the stretch.', false)}
          <div class="td-label">Baseline (X) <span class="td-label-step">The minimum viable day</span></div>
          <div class="td-help">What's the one outcome that makes today count? Not ambitious. Real.</div>
          <div style="display:flex;align-items:center;gap:0.625rem;margin-bottom:1.25rem;">
            <button onclick="toggleGoalCompletion('baseline')" class="td-check ${todayPlan.baseline_goal.completed ? 'checked' : ''}">
              ${todayPlan.baseline_goal.completed ? '<i class="fas fa-check" style="font-size:0.625rem"></i>' : ''}
            </button>
            <textarea id="baseline-goal" class="td-input" style="flex:1;min-height:3rem;" placeholder="The minimum that makes today count.">${todayPlan.baseline_goal.text}</textarea>
          </div>
          <div class="td-label">Stretch (Y) <span class="td-label-step">If a lever pulls</span></div>
          <div class="td-help">If everything goes right and you get the time, what's the stretch?</div>
          <div style="display:flex;align-items:center;gap:0.625rem;margin-bottom:0.75rem;">
            <button onclick="toggleGoalCompletion('stretch')" class="td-check ${todayPlan.stretch_goal.completed ? 'checked' : ''}">
              ${todayPlan.stretch_goal.completed ? '<i class="fas fa-check" style="font-size:0.625rem"></i>' : ''}
            </button>
            <textarea id="stretch-goal" class="td-input" style="flex:1;min-height:3rem;" placeholder="The stretch if everything lines up.">${todayPlan.stretch_goal.text}</textarea>
          </div>
          <div style="text-align:right;">
            <button onclick="saveGoals()" class="td-btn" style="padding:0.5rem 1rem;font-size:0.8125rem;">Save goals</button>
          </div>
        ${_chapterClose()}

        ${isMedium ? '' : `<!-- Contingencies (collapsed) -->
        <details style="margin-bottom:1.5rem;">
          <summary style="cursor:pointer;font-size:0.6875rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--ip-gray-600);padding:0.5rem 0;">
            Contingencies . When the plan breaks. Pick the play.
          </summary>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;padding:0.75rem 0;">
            <button onclick="activateContingency('runningLate')" class="td-btn-ghost" style="text-align:left;padding:0.75rem;">
              <div style="font-weight:600;font-size:0.8125rem;">Running Late</div>
              <div style="font-size:0.75rem;color:var(--ip-gray-600);">Skip non-essentials, first task only</div>
            </button>
            <button onclick="activateContingency('lowEnergy')" class="td-btn-ghost" style="text-align:left;padding:0.75rem;">
              <div style="font-weight:600;font-size:0.8125rem;">Low Energy</div>
              <div style="font-size:0.75rem;color:var(--ip-gray-600);">Switch to B-Day, baseline only</div>
            </button>
            <button onclick="activateContingency('freeTime')" class="td-btn-ghost" style="text-align:left;padding:0.75rem;">
              <div style="font-weight:600;font-size:0.8125rem;">Free Time</div>
              <div style="font-size:0.75rem;color:var(--ip-gray-600);">Quick wins, prep tomorrow</div>
            </button>
            <button onclick="activateContingency('disruption')" class="td-btn-ghost" style="text-align:left;padding:0.75rem;">
              <div style="font-weight:600;font-size:0.8125rem;">Disruption</div>
              <div style="font-size:0.75rem;color:var(--ip-gray-600);">Reassess, one task only</div>
            </button>
          </div>
        </details>`}

        <!-- Progress summary -->
        <div class="td-stat" style="padding:1rem 0;border-top:1px solid var(--ip-gray-200);">
          Time Blocks: <strong>${dailyProgress.timeBlocks.completed}/${dailyProgress.timeBlocks.total}</strong>
          . Goals: <strong>${dailyProgress.goals.completed}/${dailyProgress.goals.total}</strong>
          . Routines: <strong>${dailyProgress.routines.completed}/${dailyProgress.routines.total}</strong>
          . Overall: <strong>${dailyProgress.overall}%</strong>
        </div>

        ${yesterdayPlan ? `
          <div class="td-pill" style="margin-top:0.5rem;">
            Yesterday's baseline: "${UI.sanitize(yesterdayPlan.baseline_goal.text || '(none)')}"
            ${yesterdayPlan.baseline_goal.completed ? ' . Done.' : ' . Not completed.'}
          </div>
        ` : ''}

        ${_bridges([
          { screen: 'Tasks', text: 'See your monthly tasks' },
          { screen: 'History', text: 'Write a journal entry or review' },
          { screen: 'Home', text: 'Back to overview' }
        ])}
      </div>
    `;
  },

  // Minimal Mode: the act-now lens over the same DayPlan. Everything the morning
  // ritual decided is read-only here. The only writes are the ones you make while
  // executing: block completion, routine steps, reset move.
  renderDailyMinimal(plan) {
    if (!Helpers.isPlanReady(plan)) {
      return `
        <div class="ip-minimal">
          ${_dailyViewToggle('minimal')}
          <div class="ip-minimal-empty">
            <div class="ip-minimal-empty-title">No plan for today yet.</div>
            <div class="ip-minimal-empty-sub">Minimal Mode shows the block you're in. Build the day first.</div>
            <button class="td-btn ip-minimal-open" onclick="setDailyView('full')">Plan your day</button>
          </div>
        </div>
      `;
    }

    const td = getTodayFields();
    const progress = Helpers.calculateDailyProgress();
    const current = Helpers.getCurrentTimeBlock(plan);
    const next = Helpers.getNextTimeBlock(plan);
    const routine = Helpers.getActiveRoutine(plan);
    // Keep the original slot number: a filled p2 with an empty p1 is still "2".
    const priorities = [1, 2, 3].map(i => ({ num: i, text: td['p' + i] })).filter(p => p.text);

    const nowCard = current ? `
      <div class="ip-now-label">Now</div>
      <div class="ip-now-title">${UI.sanitize(current.title)}</div>
      <div class="ip-now-meta">Started ${UI.sanitize(current.time)}</div>
      <button class="ip-now-check ${current.completed ? 'is-done' : ''}"
              onclick="toggleTimeBlockCompletion('${current.id}')">
        ${current.completed ? '<i class="fas fa-check"></i> Done' : 'Mark done'}
      </button>
    ` : `
      <div class="ip-now-label">Now</div>
      <div class="ip-now-title">The day hasn't started.</div>
      <div class="ip-now-meta">${next ? `First block: ${UI.sanitize(next.title)} at ${UI.sanitize(next.time)}` : 'Nothing scheduled.'}</div>
    `;

    return `
      <div class="ip-minimal">
        ${_dailyViewToggle('minimal')}

        <div class="ip-now">${nowCard}</div>

        ${routine ? `
          <div class="ip-min-card">
            <div class="ip-min-label">${UI.sanitize(routine.name)} routine . ${routine.done}/${routine.total} steps</div>
            ${routine.steps.map((step, idx) => `
              <label class="ip-min-step">
                <input type="checkbox" ${routine.completion.steps?.[idx] ? 'checked' : ''}
                       onchange="toggleRoutineStep('${_jsAttrArg(routine.name)}', ${idx}, this.checked)" />
                <span class="${routine.completion.steps?.[idx] ? 'is-done' : ''}">${UI.sanitize(step)}</span>
              </label>
            `).join('')}
          </div>
        ` : ''}

        ${td.winTarget ? `
          <div class="ip-min-card">
            <div class="ip-min-label">Today counts if</div>
            <div class="ip-min-hero">${UI.sanitize(td.winTarget)}</div>
          </div>
        ` : ''}

        ${priorities.length ? `
          <div class="ip-min-card">
            <div class="ip-min-label">Top 3</div>
            ${priorities.map(p => `
              <div class="ip-min-priority">
                <span class="ip-min-priority-num">${p.num}</span>
                <span>${UI.sanitize(p.text)}</span>
              </div>
            `).join('')}
          </div>
        ` : ''}

        ${td.lever ? `
          <div class="ip-min-card">
            <div class="ip-min-label">The lever</div>
            <div class="ip-min-body">${UI.sanitize(td.lever)}</div>
          </div>
        ` : ''}

        ${td.resetMove ? `
          <div class="ip-min-card">
            <div class="ip-min-label">Reset move</div>
            <div class="ip-min-body">${UI.sanitize(td.resetMove)}</div>
            <button class="td-btn-ghost ip-min-reset" onclick="activateResetMove()">I used it</button>
          </div>
        ` : ''}

        ${next ? `
          <div class="ip-min-card ip-min-next">
            <div class="ip-min-label">Next</div>
            <div class="ip-min-body">${UI.sanitize(next.time)} . ${UI.sanitize(next.title)}</div>
          </div>
        ` : ''}

        <div class="ip-min-progress">
          Blocks <strong>${progress.timeBlocks.completed}/${progress.timeBlocks.total}</strong>
          . Goals <strong>${progress.goals.completed}/${progress.goals.total}</strong>
          . Overall <strong>${progress.overall}%</strong>
        </div>

        <button class="td-btn ip-minimal-open" onclick="setDailyView('full')">Open Full Plan</button>
      </div>
    `;
  },

  // =========================================================================
  // TASKS (merged A-Z + Weekly Focus)
  // =========================================================================
  Tasks() {
    const currentFilter = getAzFilter();
    const currentSearch = getAzSearch();

    const filteredTasks = state.AZTask.filter(task => {
      const matchesStatus = currentFilter === 'all' ||
        (currentFilter === 'completed' && task.status === TASK_STATUS.COMPLETED) ||
        (currentFilter === 'in-progress' && task.status === TASK_STATUS.IN_PROGRESS) ||
        (currentFilter === 'not-started' && task.status === TASK_STATUS.NOT_STARTED);
      const searchLower = currentSearch.toLowerCase();
      const matchesSearch = !currentSearch ||
        task.task.toLowerCase().includes(searchLower) ||
        task.letter.toLowerCase().includes(searchLower) ||
        (task.notes && task.notes.toLowerCase().includes(searchLower));
      return matchesStatus && matchesSearch;
    });

    const stats = {
      total: state.AZTask.length,
      completed: state.AZTask.filter(t => t.status === 'Completed').length,
      inProgress: state.AZTask.filter(t => t.status === 'In Progress').length,
      notStarted: state.AZTask.filter(t => t.status === 'Not Started').length
    };

    // Weekly plan data
    const wp = state.WeeklyPlan || {};
    const monday = getWeekMonday();
    const sunday = getWeekSunday(monday);
    const rollup = getWeeklyRollup();
    const isCurrentWeek = wp.weekOf === monday;
    const primaryTask = wp.primaryLetter ? state.AZTask.find(t => t.id === wp.primaryLetter) : null;
    const primaryDays = primaryTask ? (rollup.azDays[primaryTask.id] || 0) : 0;

    const mondayFmt = new Date(monday + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const sundayFmt = new Date(sunday + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

    return `
      <div style="max-width:48rem;">
        <h1 style="font-size:2.25rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:0.25rem;">Tasks</h1>
        <div class="td-help" style="margin-bottom:1.75rem;">Your monthly objectives and focus areas.</div>

        <!-- This Week -->
        <div class="td-chapter" style="margin-top:0;">
          <span class="td-chapter-title">This Week</span>
          <span class="td-chapter-sub">${mondayFmt} \u2013 ${sundayFmt}${wp.closed ? ' (closed)' : ''}</span>
        </div>
        <div class="td-section">
          <div class="td-label">Primary Letter <span class="td-label-step">The A-Z task you're attacking this week</span></div>
          <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;">
            <select id="wp-primary" class="td-input" style="width:auto;max-width:20rem;">
              <option value="">None selected</option>
              ${state.AZTask.filter(t => t.status !== 'Completed').map(t =>
                `<option value="${t.id}" ${wp.primaryLetter === t.id ? 'selected' : ''}>${t.letter}: ${UI.sanitize(t.task)}</option>`
              ).join('')}
            </select>
            ${primaryTask ? `<span class="td-stat" style="margin-bottom:0;">Moved <strong>${primaryDays}</strong> day${primaryDays !== 1 ? 's' : ''} this week</span>` : ''}
          </div>

          <div class="td-label">Week Counts If</div>
          <div class="td-help">What makes this week a win? One sentence.</div>
          <input type="text" id="wp-counts-if" class="td-input" value="${UI.sanitize(wp.weekCountsIf || '')}" placeholder="This week counts if..." style="margin-bottom:1.25rem;">

          <div class="td-label">PIGPEN Focus</div>
          <div class="td-help">Which areas are you hitting this week? Leave blank to skip.</div>
          ${(state.FocusArea || []).map(area => {
            const note = (wp.pigpenFocus || {})[area.name] || '';
            const count = rollup.areaCounts[area.id] || 0;
            return `
              <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
                <span class="td-dot" style="background-color:${area.color};"></span>
                <span style="font-size:0.8125rem;font-weight:600;width:6rem;">${UI.sanitize(area.name)}</span>
                <input type="text" id="wp-pigpen-${area.id}" class="td-input" value="${UI.sanitize(note)}" placeholder="Focus note..." style="flex:1;font-size:0.8125rem;padding:0.375rem 0.625rem;">
                <span style="font-size:0.6875rem;color:var(--ip-gray-600);">${count} linked</span>
              </div>
            `;
          }).join('')}

          <div style="display:flex;gap:0.5rem;margin-top:1rem;">
            <button onclick="saveWeeklyPlan()" class="td-btn">Save Week</button>
            ${!wp.closed ? `<button onclick="closeWeek()" class="td-btn-ghost">Close Week</button>` : ''}
          </div>
        </div>

        <!-- A-Z Tasks -->
        <div class="td-chapter" style="margin-top:0;">
          <span class="td-chapter-title">A-Z Tasks</span>
          <span class="td-chapter-sub">Each letter is one focused objective.</span>
        </div>

        <div class="td-stat">
          ${stats.total} tasks: <strong>${stats.completed}</strong> done, <strong>${stats.inProgress}</strong> in progress, <strong>${stats.notStarted}</strong> not started
        </div>

        <div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center;margin-bottom:1.5rem;">
          <button onclick="openCreateModal()" class="td-btn"><i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>Add Task</button>
          <button onclick="sortTasks()" class="td-btn-ghost"><i class="fas fa-sort-alpha-down" style="margin-right:0.375rem;"></i>Sort</button>
          <select onchange="filterTasks(this.value)" class="td-input" style="width:auto;padding:0.5rem 0.75rem;font-size:0.8125rem;" aria-label="Filter tasks">
            <option value="all" ${currentFilter === 'all' ? 'selected' : ''}>All</option>
            <option value="completed" ${currentFilter === 'completed' ? 'selected' : ''}>Completed</option>
            <option value="in-progress" ${currentFilter === 'in-progress' ? 'selected' : ''}>In Progress</option>
            <option value="not-started" ${currentFilter === 'not-started' ? 'selected' : ''}>Not Started</option>
          </select>
          <input type="text" id="az-search-input" value="${UI.sanitize(currentSearch)}" placeholder="Search..." onkeyup="searchTasks(this.value)" class="td-input" style="width:auto;min-width:10rem;padding:0.5rem 0.75rem;font-size:0.8125rem;" />
        </div>

        ${filteredTasks.length === 0 ? `
          <div style="text-align:center;padding:3rem 0;color:var(--ip-gray-600);">
            <div style="font-size:1rem;margin-bottom:0.5rem;">No tasks found.</div>
            ${state.AZTask.length === 0 ? '<button onclick="openCreateModal()" class="td-btn">Create your first task</button>' : '<div class="td-help">Try adjusting your filter or search.</div>'}
          </div>
        ` : `
          <div>
            ${filteredTasks.map(task => `
              <div class="td-row" style="padding:0.75rem 0;">
                <div class="td-letter">${task.letter}</div>
                <div style="flex:1;min-width:0;">
                  <div style="font-size:0.9375rem;font-weight:500;">${UI.sanitize(task.task)}</div>
                  ${task.notes ? `<div style="font-size:0.75rem;color:var(--ip-gray-600);margin-top:0.125rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${UI.sanitize(task.notes)}</div>` : ''}
                </div>
                <span class="td-status ${task.status === 'Completed' ? 'td-status-done' : task.status === 'In Progress' ? 'td-status-progress' : 'td-status-pending'}">${task.status === 'Not Started' ? 'pending' : task.status === 'In Progress' ? 'active' : 'done'}</span>
                <div style="display:flex;gap:0.25rem;">
                  <button onclick="completeTask('${task.id}')" style="background:none;border:none;cursor:pointer;color:#16a34a;padding:0.25rem;" title="Complete"><i class="fas fa-check"></i></button>
                  <button onclick="openEditModal('${task.id}')" style="background:none;border:none;cursor:pointer;color:var(--ip-gray-600);padding:0.25rem;" title="Edit"><i class="fas fa-edit"></i></button>
                  <button onclick="deleteTask('${task.id}')" style="background:none;border:none;cursor:pointer;color:#dc2626;padding:0.25rem;" title="Delete"><i class="fas fa-trash"></i></button>
                </div>
              </div>
            `).join('')}
          </div>
        `}

        <!-- Focus Areas -->
        <div class="td-chapter">
          <span class="td-chapter-title">Focus Areas</span>
          <span class="td-chapter-sub">Balance your effort. Don't let one dominate or starve.</span>
        </div>

        ${[...state.FocusArea].sort((a, b) => (b.leverageWeight || 0) - (a.leverageWeight || 0)).map(area => {
          const areaTasks = area.tasks || [];
          const completedTasks = areaTasks.filter(t => t.completed).length;

          return `
            <div class="td-section">
              <div class="td-label" style="font-size:0.75rem;">
                <span class="td-dot" style="background-color:${area.color};"></span>
                ${UI.sanitize(area.name)}
                <span style="font-weight:400;color:var(--ip-gray-600);text-transform:none;letter-spacing:normal;">${completedTasks}/${areaTasks.length} tasks</span>
              </div>
              <div class="td-help">${UI.sanitize(area.definition)}</div>
              ${areaTasks.map(task => `
                <div class="td-row">
                  <button onclick="toggleFocusTask('${area.id}', '${task.id}')" class="td-check ${task.completed ? 'checked' : ''}">
                    ${task.completed ? '<i class="fas fa-check" style="font-size:0.625rem"></i>' : ''}
                  </button>
                  <span style="flex:1;font-size:0.9375rem;${task.completed ? 'text-decoration:line-through;opacity:0.5;' : ''}">${UI.sanitize(task.text)}</span>
                  <button onclick="removeFocusTask('${area.id}', '${task.id}')" style="background:none;border:none;cursor:pointer;color:#dc2626;padding:0.25rem;font-size:0.75rem;"><i class="fas fa-times"></i></button>
                </div>
              `).join('')}
              <button onclick="addFocusTask('${area.id}')" class="td-btn-ghost" style="width:100%;text-align:center;margin-top:0.375rem;padding:0.375rem;">
                <i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>Add task
              </button>
            </div>
          `;
        }).join('')}

        ${_bridges([
          { screen: 'Daily', text: 'Plan today' },
          { screen: 'History', text: 'Review what happened' }
        ])}
      </div>
    `;
  },

  // =========================================================================
  // HISTORY (merged Calendar + Journal + Reflections)
  // =========================================================================
  History() {
    const view = state.calendarView || 'month';
    const selectedDate = state.calendarDate || stateManager.getTodayDate();
    const today = stateManager.getTodayDate();
    const [selYear, selMonth, selDay] = selectedDate.split('-').map(Number);
    const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

    function getDayData(dateStr) {
      const plan = state.DayPlans[dateStr];
      if (!plan) return null;
      const progress = Helpers.calculateDailyProgress(dateStr);
      return { plan, progress };
    }

    function renderDayCell(dateStr, dayNum, isCurrentMonth) {
      const isToday = dateStr === today;
      const isSelected = dateStr === selectedDate;
      const data = getDayData(dateStr);
      const dayType = data?.plan?.day_type;
      const progress = data?.progress?.overall || 0;
      const hasData = !!data;
      const clickAction = hasData ? `calendarSelectDate('${dateStr}')` : `showCreatePlanModal('${dateStr}')`;

      return `
        <button onclick="${clickAction}"
          style="position:relative;padding:0.375rem;height:4.5rem;border-radius:0.375rem;border:1px solid ${isSelected ? 'var(--ip-black)' : 'var(--ip-gray-100)'};text-align:left;cursor:pointer;background:${isCurrentMonth ? 'var(--ip-white)' : 'var(--ip-gray-50)'};opacity:${isCurrentMonth ? '1' : '0.4'};font-family:var(--ip-font);${isToday ? 'box-shadow:inset 0 0 0 2px var(--ip-black);' : ''}">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.8125rem;font-weight:${isToday ? '700' : '500'};">${dayNum}</span>
            ${dayType ? `<span style="font-size:0.625rem;font-weight:700;color:var(--ip-gray-600);">${dayType}</span>` : ''}
          </div>
          ${hasData ? `<div style="font-size:0.625rem;color:var(--ip-gray-600);margin-top:0.25rem;">${progress}%</div>` : ''}
        </button>`;
    }

    function renderMonthView() {
      const firstDay = new Date(selYear, selMonth - 1, 1);
      const lastDay = new Date(selYear, selMonth, 0);
      const startDow = firstDay.getDay();
      const daysInMonth = lastDay.getDate();
      const prevMonth = new Date(selYear, selMonth - 1, 0);
      const prevDays = prevMonth.getDate();
      let cells = '';
      for (let i = startDow - 1; i >= 0; i--) {
        const d = prevDays - i;
        const pm = selMonth - 1 < 1 ? 12 : selMonth - 1;
        const py = selMonth - 1 < 1 ? selYear - 1 : selYear;
        cells += renderDayCell(`${py}-${String(pm).padStart(2,'0')}-${String(d).padStart(2,'0')}`, d, false);
      }
      for (let d = 1; d <= daysInMonth; d++) {
        cells += renderDayCell(`${selYear}-${String(selMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`, d, true);
      }
      const totalCells = startDow + daysInMonth;
      const remaining = (7 - (totalCells % 7)) % 7;
      for (let d = 1; d <= remaining; d++) {
        const nm = selMonth + 1 > 12 ? 1 : selMonth + 1;
        const ny = selMonth + 1 > 12 ? selYear + 1 : selYear;
        cells += renderDayCell(`${ny}-${String(nm).padStart(2,'0')}-${String(d).padStart(2,'0')}`, d, false);
      }
      return `
        <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:0.25rem;margin-bottom:0.5rem;">
          ${dayNames.map(d => `<div style="text-align:center;font-size:0.6875rem;font-weight:700;color:var(--ip-gray-600);padding:0.5rem 0;text-transform:uppercase;letter-spacing:0.08em;">${d}</div>`).join('')}
        </div>
        <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:0.25rem;">${cells}</div>
      `;
    }

    // Navigation label
    let navLabel = '';
    if (view === 'month') {
      navLabel = `${monthNames[selMonth - 1]} ${selYear}`;
    } else if (view === 'week') {
      const sel = new Date(selYear, selMonth - 1, selDay);
      const weekStart = new Date(sel);
      weekStart.setDate(sel.getDate() - sel.getDay());
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 6);
      navLabel = `${weekStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} \u2013 ${weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    } else {
      navLabel = new Date(selYear, selMonth - 1, selDay).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    }

    // Journal entries
    const sortedEntries = [...state.Journal].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Reflections
    const activeTab = state.reflectionTab || 'weekly';
    const reflections = state.Reflections[activeTab] || [];
    const sortedReflections = [...reflections].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const promptLabels = {
      weekly: { wins: '3 Biggest Wins', challenges: 'Challenges', lessons: 'Lessons Learned', priorities: 'Next Week Priorities' },
      monthly: { accomplishments: 'Accomplishments', goals_progress: 'Goal Progress', improvements: 'Improvements', focus: 'Next Month Focus' },
      quarterly: { milestones: 'Milestones', trends: 'Trends', growth: 'Growth Areas', strategy: 'Strategy' },
      yearly: { top5: 'Top 5 Achievements', transformation: 'Transformation', gratitude: 'Gratitude', vision: 'Vision' }
    };

    return `
      <div style="max-width:56rem;">
        <h1 style="font-size:2.25rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:0.25rem;">History</h1>
        <div class="td-help" style="margin-bottom:1.75rem;">What happened. What you learned.</div>

        ${_renderStatsSection()}
        ${_renderTimelineSection()}

        <!-- Calendar -->
        <div class="td-chapter" style="margin-top:0;">
          <span class="td-chapter-title">Calendar</span>
          <span class="td-chapter-sub">See your days. Click one to view or create a plan.</span>
        </div>
        <div class="td-section">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <div style="display:flex;gap:0.375rem;">
              ${['month', 'week', 'day'].map(v => `
                <button onclick="calendarSetView('${v}')" class="td-btn-pill ${view === v ? 'active' : ''}">${v.charAt(0).toUpperCase() + v.slice(1)}</button>
              `).join('')}
            </div>
            <button onclick="calendarGoToday()" class="td-btn-pill">Today</button>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.25rem;">
            <button onclick="calendarPrev()" style="background:none;border:none;cursor:pointer;padding:0.5rem;color:var(--ip-gray-600);"><i class="fas fa-chevron-left"></i></button>
            <span style="font-size:1.125rem;font-weight:700;">${navLabel}</span>
            <button onclick="calendarNext()" style="background:none;border:none;cursor:pointer;padding:0.5rem;color:var(--ip-gray-600);"><i class="fas fa-chevron-right"></i></button>
          </div>
          ${view === 'month' ? renderMonthView() : ''}
        </div>

        <!-- Journal -->
        <div class="td-chapter">
          <span class="td-chapter-title">Journal</span>
          <span class="td-chapter-sub">What happened. What you thought about it. For you, tomorrow.</span>
        </div>
        <div class="td-section">
          <div style="margin-bottom:1rem;">
            <button onclick="openJournalModal()" class="td-btn"><i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>New Entry</button>
          </div>
          ${sortedEntries.length === 0 ? `
            <div class="td-help">No entries yet. Start documenting. Wins, lessons, whatever's on your mind.</div>
          ` : sortedEntries.slice(0, 5).map(entry => `
            <div style="padding:1rem 0;border-bottom:1px solid var(--ip-gray-100);">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.375rem;">
                <div>
                  <div style="font-size:0.9375rem;font-weight:700;">${UI.sanitize(entry.title || 'Untitled')} ${entry.mood ? entry.mood : ''}</div>
                  <div style="font-size:0.75rem;color:var(--ip-gray-600);">${new Date(entry.timestamp).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                </div>
                <div style="display:flex;gap:0.25rem;">
                  <button onclick="editJournalEntry('${entry.id}')" style="background:none;border:none;cursor:pointer;color:var(--ip-gray-600);padding:0.25rem;"><i class="fas fa-edit"></i></button>
                  <button onclick="deleteJournalEntry('${entry.id}')" style="background:none;border:none;cursor:pointer;color:#dc2626;padding:0.25rem;"><i class="fas fa-trash"></i></button>
                </div>
              </div>
              <div style="font-size:0.875rem;color:var(--ip-gray-700);line-height:1.55;white-space:pre-wrap;max-height:4rem;overflow:hidden;">${UI.sanitize(entry.content)}</div>
            </div>
          `).join('')}
          ${sortedEntries.length > 5 ? `<div class="td-stat" style="margin-top:0.5rem;">${sortedEntries.length - 5} more entries.</div>` : ''}
        </div>

        <!-- Reflections -->
        <div class="td-chapter">
          <span class="td-chapter-title">Reflections</span>
          <span class="td-chapter-sub">Zoom out. The day-to-day is noise without periodic review.</span>
        </div>
        <div class="td-section">
          <div style="display:flex;gap:0.375rem;margin-bottom:1rem;flex-wrap:wrap;">
            ${['weekly','monthly','quarterly','yearly'].map(tab => `
              <button onclick="setReflectionTab('${tab}')" class="td-btn-pill ${activeTab === tab ? 'active' : ''}">
                ${tab.charAt(0).toUpperCase() + tab.slice(1)} (${(state.Reflections[tab] || []).length})
              </button>
            `).join('')}
            <button onclick="openReflectionModal('${activeTab}')" class="td-btn" style="margin-left:auto;"><i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>New Review</button>
          </div>
          ${sortedReflections.length === 0 ? `
            <div class="td-help">No ${activeTab} reflections yet. Take time to review. The doing matters, but so does the seeing.</div>
          ` : sortedReflections.slice(0, 3).map(reflection => `
            <div style="padding:1rem 0;border-bottom:1px solid var(--ip-gray-100);">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
                <div style="font-size:0.9375rem;font-weight:700;">
                  ${new Date(reflection.timestamp).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                  ${reflection.mood ? ` . ${reflection.mood}` : ''}
                </div>
                <button onclick="deleteReflection('${activeTab}', '${reflection.id}')" style="background:none;border:none;cursor:pointer;color:#dc2626;padding:0.25rem;"><i class="fas fa-trash"></i></button>
              </div>
              ${Object.entries(reflection.responses).map(([key, value]) => `
                <div style="margin-bottom:0.5rem;">
                  <div class="td-label" style="margin-bottom:0.125rem;">${promptLabels[activeTab][key] || key}</div>
                  <div style="font-size:0.875rem;color:var(--ip-gray-700);line-height:1.5;white-space:pre-wrap;">${UI.sanitize(value)}</div>
                </div>
              `).join('')}
            </div>
          `).join('')}
          ${sortedReflections.length > 3 ? `<div class="td-stat" style="margin-top:0.5rem;">${sortedReflections.length - 3} more ${activeTab} reflections.</div>` : ''}
        </div>

        ${_bridges([
          { screen: 'Daily', text: 'Plan today' },
          { screen: 'Tasks', text: 'See your tasks' }
        ])}
      </div>
    `;
  },

  // =========================================================================
  // SETTINGS
  // =========================================================================
  Settings() {
    return `
      <div style="max-width:48rem;">
        <h1 style="font-size:2.25rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;margin-bottom:0.25rem;">Settings</h1>
        <div class="td-help" style="margin-bottom:1.75rem;">Preferences and data management.</div>

        <div class="td-chapter" style="margin-top:0;">
          <span class="td-chapter-title">Preferences</span>
        </div>
        <div class="td-section">
          <div class="td-row" style="justify-content:space-between;">
            <div>
              <div style="font-weight:600;font-size:0.9375rem;">Dark Mode</div>
              <div class="td-help" style="margin-bottom:0;">Switch between light and dark theme.</div>
            </div>
            <div class="td-toggle ${state.Settings.darkMode ? 'on' : ''}" onclick="toggleDarkMode()"></div>
          </div>
          <div class="td-row" style="justify-content:space-between;">
            <div>
              <div style="font-weight:600;font-size:0.9375rem;">Notifications</div>
              <div class="td-help" style="margin-bottom:0;">Reminder notifications when available.</div>
            </div>
            <div class="td-toggle ${state.Settings.notifications ? 'on' : ''}" onclick="toggleSetting('notifications')"></div>
          </div>
          <div class="td-row" style="justify-content:space-between;">
            <div>
              <div style="font-weight:600;font-size:0.9375rem;">Auto-save</div>
              <div class="td-help" style="margin-bottom:0;">Save changes automatically as you work.</div>
            </div>
            <div class="td-toggle ${state.Settings.autoSave ? 'on' : ''}" onclick="toggleSetting('autoSave')"></div>
          </div>
          <div style="padding:0.75rem 0;">
            <div class="td-label">Default Day Type</div>
            <select onchange="updateSetting('defaultDayType', this.value)" class="td-input" style="width:auto;">
              ${['A', 'B', 'C'].map(type => `
                <option value="${type}" ${state.Settings.defaultDayType === type ? 'selected' : ''}>
                  ${type} Day ${type === 'A' ? '(Deep Focus)' : type === 'B' ? '(Balanced)' : '(Recovery)'}
                </option>
              `).join('')}
            </select>
          </div>
        </div>

        <div class="td-chapter">
          <span class="td-chapter-title">Day Type Templates</span>
          <span class="td-chapter-sub">Customize the schedule for each day type.</span>
        </div>
        <div class="td-section">
          ${['A', 'B', 'C'].map(type => {
            const template = state.DayTypeTemplates?.[type] || {};
            return `
              <div class="td-row" style="justify-content:space-between;padding:0.75rem 0;">
                <div>
                  <div style="font-weight:700;font-size:0.9375rem;">${type} Day . ${UI.sanitize(template.name || '')}</div>
                  <div style="font-size:0.75rem;color:var(--ip-gray-600);">${template.timeBlocks?.length || 0} blocks . ${template.routines?.join(', ') || 'no routines'}</div>
                </div>
                <button onclick="openDayTypeTemplateEditor('${type}')" class="td-btn-ghost">Edit</button>
              </div>
            `;
          }).join('')}
        </div>

        <div class="td-chapter">
          <span class="td-chapter-title">Routines</span>
          <span class="td-chapter-sub">Edit your routine templates. Steps show inside time blocks on the Daily screen.</span>
        </div>
        <div class="td-section">
          ${Object.keys(state.Routine).map(routineName => {
            const routine = state.Routine[routineName];
            return `
              <details style="margin-bottom:1rem;">
                <summary style="cursor:pointer;display:flex;align-items:center;justify-content:space-between;padding:0.5rem 0;">
                  <span style="font-weight:600;font-size:0.9375rem;">${UI.sanitize(routineName)} Routine <span style="font-weight:400;color:var(--ip-gray-600);">${routine.length} steps</span></span>
                  <button onclick="event.stopPropagation();deleteRoutineType('${routineName}')" style="background:none;border:none;cursor:pointer;color:#dc2626;font-size:0.75rem;"><i class="fas fa-trash"></i></button>
                </summary>
                <div style="padding:0.5rem 0 0.5rem 1rem;">
                  ${routine.map((step, index) => `
                    <div class="td-row">
                      <span style="color:var(--ip-gray-300);font-weight:700;font-size:0.875rem;width:1.5rem;text-align:center;">${index + 1}</span>
                      <input type="text" value="${UI.sanitize(step)}" onchange="updateRoutineStep('${routineName}', ${index}, this.value)" class="td-input" style="flex:1;" placeholder="Step..." />
                      <div style="display:flex;gap:0.125rem;">
                        ${index > 0 ? `<button onclick="moveRoutineStep('${routineName}', ${index}, 'up')" style="background:none;border:none;cursor:pointer;color:var(--ip-gray-600);padding:0.25rem;font-size:0.625rem;"><i class="fas fa-chevron-up"></i></button>` : ''}
                        ${index < routine.length - 1 ? `<button onclick="moveRoutineStep('${routineName}', ${index}, 'down')" style="background:none;border:none;cursor:pointer;color:var(--ip-gray-600);padding:0.25rem;font-size:0.625rem;"><i class="fas fa-chevron-down"></i></button>` : ''}
                        <button onclick="deleteRoutineStep('${routineName}', ${index})" style="background:none;border:none;cursor:pointer;color:#dc2626;padding:0.25rem;font-size:0.625rem;"><i class="fas fa-times"></i></button>
                      </div>
                    </div>
                  `).join('')}
                  <button onclick="addRoutineStep('${routineName}')" class="td-btn-ghost" style="width:100%;text-align:center;margin-top:0.375rem;padding:0.375rem;">
                    <i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>Add step
                  </button>
                </div>
              </details>
            `;
          }).join('')}
          <button onclick="addNewRoutineType()" class="td-btn-ghost" style="width:100%;text-align:center;">
            <i class="fas fa-plus" style="margin-right:0.375rem;font-size:0.625rem;"></i>New Routine
          </button>
        </div>

        <div class="td-chapter">
          <span class="td-chapter-title">Atlas Connection</span>
          <span class="td-chapter-sub">Sync with your Atlas governance system.</span>
        </div>
        <div class="td-section">
          <div style="padding:0.75rem 0;">
            <div class="td-label">API URL</div>
            <input type="text" class="td-input" value="${state.Settings.atlasApiUrl || 'http://localhost:3001'}"
              onchange="updateSetting('atlasApiUrl', this.value)" placeholder="http://localhost:3001" />
          </div>
          <div class="td-row" style="justify-content:space-between;">
            <div>
              <div style="font-weight:600;font-size:0.9375rem;">Status</div>
              <div class="td-help" style="margin-bottom:0;">
                ${typeof AtlasAPI !== 'undefined' && AtlasAPI.online ? 'Connected' : 'Offline'}
                ${typeof AtlasAPI !== 'undefined' && AtlasAPI.lastSyncAt ? ' . Last sync: ' + new Date(AtlasAPI.lastSyncAt).toLocaleTimeString() : ''}
              </div>
            </div>
          </div>
          <div style="display:flex;gap:0.5rem;margin-top:0.5rem;">
            <button onclick="testAtlasConnection()" class="td-btn-ghost">Test Connection</button>
            <button onclick="syncAtlasNow()" class="td-btn-ghost">Sync Now</button>
          </div>
        </div>

        <div class="td-chapter">
          <span class="td-chapter-title">Data</span>
        </div>
        <div class="td-section">
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <button onclick="exportState()" class="td-btn-ghost"><i class="fas fa-download" style="margin-right:0.375rem;"></i>Export</button>
            <button onclick="showImportModal()" class="td-btn-ghost"><i class="fas fa-upload" style="margin-right:0.375rem;"></i>Import</button>
            <button onclick="resetToDefaults()" class="td-btn-ghost"><i class="fas fa-redo" style="margin-right:0.375rem;"></i>Reset defaults</button>
            <button onclick="clearData()" class="td-btn-danger"><i class="fas fa-trash-alt" style="margin-right:0.375rem;"></i>Clear all data</button>
          </div>
          <div class="td-stat" style="margin-top:1rem;">Data size: <strong>${(JSON.stringify(state).length / 1024).toFixed(1)} KB</strong></div>
        </div>

        <div class="td-chapter">
          <span class="td-chapter-title">About</span>
        </div>
        <div class="td-section">
          <div style="font-size:0.9375rem;font-weight:600;margin-bottom:0.25rem;">in-PACT Self-Sustaining Bullet Journal</div>
          <div class="td-help">Version 2.0. All data stored locally in your browser.</div>
        </div>
      </div>
    `;
  },

  // Backward-compat aliases for old screen IDs
  AtoZ() { return ScreenRenderers.Tasks(); },
  WeeklyFocus() { return ScreenRenderers.Tasks(); },
  Routines() { return ScreenRenderers.Daily(); },
  Journal() { return ScreenRenderers.History(); },
  Reflections() { return ScreenRenderers.History(); },
  Calendar() { return ScreenRenderers.History(); },
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { screens, renderNav, navigate, ScreenRenderers };
}

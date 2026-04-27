// inPACT Today Module
// Powers the Today view (today.html) using CycleBoardState
// Adapted from inPACT-site/today.html inline script

(function () {
  // Only initialize on Today page
  if (!document.querySelector('.td-wrap')) return;

  // Ensure stateManager + state accessor exist (standalone today.html doesn't load app.js)
  if (typeof window.stateManager === 'undefined') {
    window.stateManager = new CycleBoardState();
  }
  if (!('state' in window) || typeof window.state === 'undefined') {
    Object.defineProperty(window, 'state', {
      get() { return window.stateManager.state; },
      set(value) { Object.keys(window.stateManager.state).forEach(key => delete window.stateManager.state[key]); Object.assign(window.stateManager.state, value); },
      configurable: true
    });
  }

  // -- Date helpers --
  const todayISO = () => new Date().toISOString().slice(0, 10);
  const yesterdayISO = () => {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  };
  const fmtDate = (d) =>
    d.toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });

  // -- Blank daily plan --
  const blank = () => ({
    date: todayISO(),
    winTarget: '',
    p1: '', p1why: '',
    p2: '', p2why: '',
    p3: '', p3why: '',
    x1: '', y1: '',
    x2: '', y2: '',
    x3: '', y3: '',
    lever: '',
    resetMove: '',
    reflection: '',
    updated_at: null,
  });

  // -- Ensure state.Today exists --
  if (!state.Today) {
    state.Today = { mission: '', motto: '', daily: {} };
    stateManager.update({ Today: state.Today });
  }

  // -- Load today's plan from state --
  const today = todayISO();
  let plan = { ...blank(), ...(state.Today.daily[today] || {}) };

  // -- Flash saved pill --
  function flashSavedPill() {
    const pill = document.getElementById('saved-pill');
    if (!pill) return;
    pill.classList.add('show');
    clearTimeout(flashSavedPill._t);
    flashSavedPill._t = setTimeout(() => pill.classList.remove('show'), 1500);
  }

  // -- Save today's plan --
  function save() {
    plan.updated_at = new Date().toISOString();
    state.Today.daily[today] = plan;
    stateManager.update({ Today: state.Today });
    flashSavedPill();
  }

  // -- Render mission/motto pin --
  function renderMission() {
    const missionEl = document.getElementById('mission-display');
    const mottoEl = document.getElementById('motto-display');
    if (!missionEl || !mottoEl) return;

    const mission = state.Today.mission || '';
    const motto = state.Today.motto || '';

    if (mission) {
      missionEl.innerHTML =
        '<span style="opacity:0.55;font-size:0.625rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">Mission</span> &nbsp; ' +
        mission.replace(/</g, '&lt;');
    } else {
      missionEl.innerHTML =
        '<span class="td-mission-empty">Mission: write what you\'re chasing. The concrete one. Not "freedom". The car note.</span>';
    }

    if (motto) {
      mottoEl.innerHTML = motto.replace(/</g, '&lt;');
    } else {
      mottoEl.innerHTML =
        '<span class="td-mission-empty">Motto: the line you say when shit cracks.</span>';
    }
  }

  // -- Render yesterday pill --
  function renderYesterday() {
    const y = state.Today.daily[yesterdayISO()] || null;
    const pill = document.getElementById('yesterday-pill');
    if (!pill) return;

    if (y) {
      const wins = ['x1', 'x2', 'x3'].filter((k) => y[k]).length;
      const stretches = ['y1', 'y2', 'y3'].filter((k) => y[k]).length;
      const target = y.winTarget
        ? '<strong>' + y.winTarget.replace(/</g, '&lt;').slice(0, 40) + '</strong>'
        : '<strong>(no target set)</strong>';
      pill.innerHTML = 'Yesterday: ' + target + ' · ' + wins + '/3 min · ' + stretches + '/3 max';
    }
    // else leave the default "No entry yesterday. Start fresh." from HTML
  }

  // -- Populate inputs from plan --
  function populateInputs() {
    document.querySelectorAll('[data-field]').forEach((el) => {
      el.value = plan[el.dataset.field] || '';
    });
  }

  // -- Build linkage select (A-Z or PIGPEN) --
  function buildLinkSelect(type, prioNum) {
    const field = type === 'az' ? 'p' + prioNum + 'az' : 'p' + prioNum + 'area';
    const current = plan[field] || '';

    let options = '<option value="">—</option>';
    if (type === 'az') {
      (state.AZTask || []).filter(t => t.status !== 'Completed').forEach(t => {
        const sel = current === t.id ? ' selected' : '';
        options += '<option value="' + t.id + '"' + sel + '>' + t.letter + ': ' + t.task.replace(/</g, '&lt;').slice(0, 30) + '</option>';
      });
    } else {
      (state.FocusArea || []).forEach(a => {
        const sel = current === a.id ? ' selected' : '';
        options += '<option value="' + a.id + '"' + sel + '>' + a.name.replace(/</g, '&lt;') + '</option>';
      });
    }

    const label = type === 'az' ? 'A-Z' : 'Area';
    return '<select data-link="' + field + '" style="font-family:var(--ip-font);font-size:0.6875rem;color:var(--ip-gray-600);background:var(--ip-gray-50);border:1px solid var(--ip-gray-100);border-radius:0.375rem;padding:0.25rem 0.375rem;cursor:pointer;" title="Link to ' + label + '">' + options + '</select>';
  }

  // -- Render linkage selectors under each priority --
  function renderLinkSelectors() {
    for (let i = 1; i <= 3; i++) {
      const whyInput = document.querySelector('[data-field="p' + i + 'why"]');
      if (!whyInput) continue;

      // Don't duplicate
      const existing = whyInput.parentElement.querySelector('.td-link-row');
      if (existing) existing.remove();

      const row = document.createElement('div');
      row.className = 'td-link-row';
      row.style.cssText = 'display:flex;gap:0.375rem;align-items:center;margin-top:0.25rem;';
      row.innerHTML =
        '<span style="font-size:0.625rem;color:var(--ip-gray-300);text-transform:uppercase;letter-spacing:0.06em;">Link:</span>' +
        buildLinkSelect('az', i) +
        buildLinkSelect('area', i);
      whyInput.parentElement.appendChild(row);
    }

    // Wire change events
    document.querySelectorAll('[data-link]').forEach(function (sel) {
      sel.addEventListener('change', function () {
        plan[sel.dataset.link] = sel.value;
        save();
      });
    });
  }

  // -- Build plaintext plan for clipboard --
  function buildPlanText() {
    const dateStr = fmtDate(new Date());
    const lines = ['Today · ' + dateStr];
    if (state.Today.motto) lines.push(state.Today.motto);
    lines.push('');
    if (plan.winTarget) lines.push('Win: ' + plan.winTarget);

    const prios = [
      plan.p1 ? '1. ' + plan.p1 + (plan.p1why ? ' · ' + plan.p1why : '') : null,
      plan.p2 ? '2. ' + plan.p2 + (plan.p2why ? ' · ' + plan.p2why : '') : null,
      plan.p3 ? '3. ' + plan.p3 + (plan.p3why ? ' · ' + plan.p3why : '') : null,
    ].filter(Boolean);
    if (prios.length) {
      lines.push('');
      lines.push('Priorities');
      lines.push(...prios);
    }

    const ways = [];
    for (let i = 1; i <= 3; i++) {
      const min = plan['x' + i];
      const max = plan['y' + i];
      if (min || max) ways.push(i + '. min ' + (min || '-') + ' · max ' + (max || '-'));
    }
    if (ways.length) {
      lines.push('');
      lines.push('3 Ways to Win');
      lines.push(...ways);
    }

    if (plan.lever) {
      lines.push('');
      lines.push('Lever: ' + plan.lever);
    }

    return lines.join('\n');
  }

  // -- Initialize on DOM ready --
  document.addEventListener('DOMContentLoaded', function () {
    // Date display
    const dateEl = document.getElementById('today-date');
    if (dateEl) dateEl.textContent = fmtDate(new Date());

    // Render mission + yesterday + inputs + linkage selectors
    renderMission();
    renderYesterday();
    populateInputs();
    renderLinkSelectors();

    // Wire blur save on every data-field input
    document.querySelectorAll('[data-field]').forEach((el) => {
      el.addEventListener('input', () => {
        plan[el.dataset.field] = el.value;
      });
      el.addEventListener('blur', save);
    });

    // Mission edit flow
    const editBtn = document.getElementById('mission-edit-btn');
    const saveBtn = document.getElementById('mission-save-btn');
    const editForm = document.getElementById('mission-edit-form');

    if (editBtn) {
      editBtn.addEventListener('click', () => {
        const isOpen = editForm.classList.toggle('show');
        if (isOpen) {
          document.getElementById('mission-input').value = state.Today.mission || '';
          document.getElementById('motto-input').value = state.Today.motto || '';
          document.getElementById('mission-input').focus();
        }
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        state.Today.mission = document.getElementById('mission-input').value.trim();
        state.Today.motto = document.getElementById('motto-input').value.trim();
        stateManager.update({ Today: state.Today });
        editForm.classList.remove('show');
        renderMission();
        flashSavedPill();
      });
    }

    // Copy plan button
    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(buildPlanText());
          copyBtn.textContent = 'Copied';
          copyBtn.classList.add('copied');
          setTimeout(() => {
            copyBtn.textContent = 'Copy plan';
            copyBtn.classList.remove('copied');
          }, 1500);
        } catch (e) {
          copyBtn.textContent = 'Copy failed';
          setTimeout(() => {
            copyBtn.textContent = 'Copy plan';
          }, 1500);
        }
      });
    }

    // Save button (explicit, though blur already auto-saves)
    const saveTodayBtn = document.getElementById('save-btn');
    if (saveTodayBtn) {
      saveTodayBtn.addEventListener('click', save);
    }
  });
})();

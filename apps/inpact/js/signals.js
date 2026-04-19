/**
 * inPACT signal consumer - Phase 3c of doctrine/04_BUILD_PLAN.md.
 *
 * Polls delta-kernel /api/signals, renders approval_required and urgent
 * signals as a floating banner above #main-content. Fails silently if
 * delta-kernel is not running (common during local dev without the backend).
 *
 * Rules:
 *   - No em dashes anywhere (per feedback_no_em_dashes_in_ui.md).
 *   - Reuses Tailwind utility classes that exist in index.html.
 *   - Bounded polling: exponential backoff on network error, reset on recovery.
 *   - Approval actions POST to /api/signals/:id/resolve then re-fetch.
 */
(function () {
  'use strict';

  var DELTA_BASE = 'http://localhost:3001';
  var ENDPOINT = DELTA_BASE + '/api/signals';
  var TOKEN_ENDPOINT = DELTA_BASE + '/api/auth/token';
  var RESOLVE_ENDPOINT = function (id) { return DELTA_BASE + '/api/signals/' + encodeURIComponent(id) + '/resolve'; };
  var CONTAINER_ID = 'ip-signals-banner';

  var _token = null;
  function fetchToken() {
    if (_token) return Promise.resolve(_token);
    return fetch(TOKEN_ENDPOINT)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (body) { if (body && body.token) { _token = body.token; } return _token; })
      .catch(function () { return null; });
  }
  function authHeaders() {
    return _token ? { 'Authorization': 'Bearer ' + _token } : {};
  }

  var BASE_INTERVAL_MS = 30000;   // 30s happy path
  var MAX_INTERVAL_MS = 120000;   // cap at 2 min
  var currentInterval = BASE_INTERVAL_MS;
  var pollTimer = null;

  function ensureContainer() {
    var existing = document.getElementById(CONTAINER_ID);
    if (existing) return existing;
    var el = document.createElement('div');
    el.id = CONTAINER_ID;
    el.style.cssText = [
      'position: fixed',
      'top: 0',
      'left: 0',
      'right: 0',
      'z-index: 45',
      'padding: 0.5rem',
      'display: flex',
      'flex-direction: column',
      'gap: 0.5rem',
      'pointer-events: none',
    ].join(';');
    document.body.appendChild(el);
    return el;
  }

  function priorityStyle(signal) {
    if (signal.signal_type === 'approval_required') {
      return { bg: '#fef3c7', border: '#f59e0b', text: '#78350f', label: 'Approval' };
    }
    if (signal.priority === 'urgent' || signal.signal_type === 'error') {
      return { bg: '#fee2e2', border: '#ef4444', text: '#7f1d1d', label: 'Urgent' };
    }
    if (signal.signal_type === 'completion') {
      return { bg: '#d1fae5', border: '#10b981', text: '#064e3b', label: 'Done' };
    }
    return { bg: '#e0e7ff', border: '#6366f1', text: '#312e81', label: 'Info' };
  }

  function renderSignal(signal) {
    var style = priorityStyle(signal);
    var card = document.createElement('div');
    card.setAttribute('data-signal-id', signal.id);
    card.style.cssText = [
      'background: ' + style.bg,
      'border-left: 4px solid ' + style.border,
      'color: ' + style.text,
      'padding: 0.75rem 1rem',
      'border-radius: 0.375rem',
      'box-shadow: 0 2px 8px rgba(0,0,0,0.08)',
      'pointer-events: auto',
      'font-family: ui-sans-serif, system-ui, sans-serif',
      'font-size: 0.875rem',
      'line-height: 1.4',
    ].join(';');

    var labelLine = document.createElement('div');
    labelLine.style.cssText = 'font-weight: 700; margin-bottom: 0.25rem';
    labelLine.textContent = style.label + ': ' + (signal.payload && signal.payload.label ? signal.payload.label : 'signal');
    card.appendChild(labelLine);

    if (signal.payload && signal.payload.summary) {
      var body = document.createElement('div');
      body.style.cssText = 'margin-bottom: 0.5rem';
      body.textContent = signal.payload.summary;
      card.appendChild(body);
    }

    var actions = (signal.payload && signal.payload.action_options) || [];
    if (actions.length > 0) {
      var row = document.createElement('div');
      row.style.cssText = 'display: flex; gap: 0.5rem; flex-wrap: wrap';
      actions.forEach(function (opt) {
        var btn = document.createElement('button');
        btn.textContent = opt.label || opt.id;
        btn.setAttribute('data-action-id', opt.id);
        var riskBg = opt.risk_tier === 'high' ? '#dc2626' : (opt.risk_tier === 'medium' ? '#f59e0b' : '#10b981');
        btn.style.cssText = [
          'background: ' + riskBg,
          'color: white',
          'padding: 0.375rem 0.75rem',
          'border-radius: 0.25rem',
          'border: none',
          'cursor: pointer',
          'font-size: 0.8125rem',
          'font-weight: 600',
        ].join(';');
        btn.addEventListener('click', function () {
          resolveSignal(signal.id, opt.id).then(function () {
            card.remove();
            poll();
          });
        });
        row.appendChild(btn);
      });
      card.appendChild(row);
    } else {
      // No actions; auto-dismiss after 8s
      setTimeout(function () { card.remove(); }, 8000);
    }
    return card;
  }

  function render(signals) {
    var container = ensureContainer();
    // Track ids already rendered to avoid duplicates
    var existing = {};
    Array.prototype.forEach.call(container.children, function (child) {
      var id = child.getAttribute('data-signal-id');
      if (id) existing[id] = child;
    });

    // Only show top 3 above-the-fold
    var toShow = signals
      .filter(function (s) {
        return s.signal_type === 'approval_required' || s.priority === 'urgent' || s.signal_type === 'error' || s.signal_type === 'completion';
      })
      .slice(0, 3);

    var seenNow = {};
    toShow.forEach(function (signal) {
      seenNow[signal.id] = true;
      if (existing[signal.id]) return;
      container.appendChild(renderSignal(signal));
    });

    // Remove cards whose signal is no longer in the feed (resolved elsewhere, expired)
    Array.prototype.slice.call(container.children).forEach(function (child) {
      var id = child.getAttribute('data-signal-id');
      if (id && !seenNow[id]) child.remove();
    });
  }

  function resolveSignal(signalId, actionId) {
    return fetchToken().then(function () {
      var headers = authHeaders();
      headers['Content-Type'] = 'application/json';
      return fetch(RESOLVE_ENDPOINT(signalId), {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({ action_id: actionId }),
      }).catch(function () { /* silent */ });
    });
  }

  function poll() {
    // Always fetch full active list. Backend is a bounded ring buffer
    // and /api/signals returns ACTIVE signals (resolved ones are removed).
    fetchToken()
      .then(function () { return fetch(ENDPOINT, { headers: authHeaders() }); })
      .then(function (r) {
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      })
      .then(function (body) {
        var signals = (body && body.signals) || [];
        render(signals);
        currentInterval = BASE_INTERVAL_MS;
      })
      .catch(function () {
        // Network error or delta-kernel down. Back off.
        currentInterval = Math.min(currentInterval * 2, MAX_INTERVAL_MS);
      })
      .then(function () {
        schedule();
      });
  }

  function schedule() {
    if (pollTimer) clearTimeout(pollTimer);
    if (document.hidden) return;  // visibility-based pause
    pollTimer = setTimeout(poll, currentInterval);
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      if (pollTimer) clearTimeout(pollTimer);
    } else {
      currentInterval = BASE_INTERVAL_MS;
      poll();
    }
  });

  // Boot: wait for DOM, then first fetch.
  function boot() {
    ensureContainer();
    poll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // Expose for manual trigger / tests
  window.__inpactSignals = { poll: poll, render: render };
})();

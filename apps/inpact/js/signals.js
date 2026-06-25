/**
 * inPACT signal consumer · Phase 3c of doctrine/04_BUILD_PLAN.md
 * (Ship Target #1 of optogon-stack-three-gaps-handoff.md).
 *
 * Polls delta-kernel /api/signals every 5 s and renders:
 *   - approval_required, urgent priority, error  -> sticky banner above the fold
 *     (Rule 1: approval_required surfaces immediately and cannot scroll out
 *              of view until the user clicks an action option.
 *      Rule 2: urgent always above the fold.
 *      Rule 4: error always carries action_options.)
 *   - completion / status / insight              -> stream column on the
 *     Today screen (Rule 3: logged and linkable; Rule 6: only the banner
 *     surfaces "needs attention" things; everything else lives in the log).
 *
 * Hard rules:
 *   - No em dashes anywhere (feedback_no_em_dashes_in_ui.md).
 *   - Internal IDs (node_id, path_id, session_id) MUST NOT reach the DOM
 *     (Rule 5). The renderer only reads payload.label, payload.summary,
 *     payload.action_options[].label, action_options[].consequence.
 *     payload.data is intentionally NOT rendered.
 *   - source_layer is translated to plain language; never shown raw.
 *   - Bounded polling: 5 s base, exponential backoff to 30 s on error,
 *     reset on recovery, paused while document.hidden.
 *   - Approval actions POST to /api/signals/:id/resolve and re-fetch.
 */
(function () {
  'use strict';

  var DELTA_BASE = 'http://localhost:3001';
  var ENDPOINT = DELTA_BASE + '/api/signals';
  var TOKEN_ENDPOINT = DELTA_BASE + '/api/auth/token';
  var RESOLVE_ENDPOINT = function (id) {
    return DELTA_BASE + '/api/signals/' + encodeURIComponent(id) + '/resolve';
  };
  var BANNER_ID = 'ip-signals-banner';

  // Plain-language source-layer labels (Rule 5). Never expose raw enum values.
  var SOURCE_LABELS = {
    site_pull: 'Site capture',
    optogon: 'Conversation',
    atlas: 'Queue',
    ghost_executor: 'Executor',
    claude_code: 'Builder',
  };

  function sourceLabel(layer) {
    return SOURCE_LABELS[layer] || 'System';
  }

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

  var BASE_INTERVAL_MS = 5000;    // 5 s happy path (Ship #1 spec)
  var MAX_INTERVAL_MS = 30000;    // cap at 30 s
  var currentInterval = BASE_INTERVAL_MS;
  var pollTimer = null;

  // Latest signals snapshot · published for the stream-column renderer in screens.js.
  var latestSignals = [];
  var subscribers = [];

  function notifySubscribers() {
    for (var i = 0; i < subscribers.length; i++) {
      try { subscribers[i](latestSignals); } catch (e) { /* isolate listener crashes */ }
    }
  }

  function ensureBanner() {
    var existing = document.getElementById(BANNER_ID);
    if (existing) return existing;
    var el = document.createElement('div');
    el.id = BANNER_ID;
    el.setAttribute('role', 'region');
    el.setAttribute('aria-label', 'System signals requiring attention');
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
    return { bg: '#e0e7ff', border: '#6366f1', text: '#312e81', label: 'Info' };
  }

  function renderBannerCard(signal) {
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
    var labelText = (signal.payload && signal.payload.label) ? signal.payload.label : 'signal';
    labelLine.textContent = style.label + ': ' + labelText;
    card.appendChild(labelLine);

    var src = document.createElement('div');
    src.style.cssText = 'font-size: 0.75rem; opacity: 0.75; margin-bottom: 0.25rem';
    src.textContent = sourceLabel(signal.source_layer);
    card.appendChild(src);

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
        btn.textContent = opt.label || 'Action';
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
    } else if (signal.signal_type !== 'approval_required') {
      // Non-approval banners may auto-dismiss after 12 s (urgent/error).
      // approval_required is sticky until resolved (Rule 1).
      setTimeout(function () { card.remove(); }, 12000);
    }
    return card;
  }

  // Banner shows only what requires human attention (Rule 6).
  function bannerWorthy(s) {
    if (s.signal_type === 'approval_required') return true;
    if (s.signal_type === 'error') return true;
    if (s.priority === 'urgent') return true;
    return false;
  }

  function renderBanner(signals) {
    var container = ensureBanner();
    var existing = {};
    Array.prototype.forEach.call(container.children, function (child) {
      var id = child.getAttribute('data-signal-id');
      if (id) existing[id] = child;
    });

    // Approval cards always show; other banner-worthy capped at 3 to avoid wall.
    var approvals = signals.filter(function (s) { return s.signal_type === 'approval_required'; });
    var others = signals
      .filter(function (s) { return bannerWorthy(s) && s.signal_type !== 'approval_required'; })
      .slice(0, 3);
    var toShow = approvals.concat(others);

    var seenNow = {};
    toShow.forEach(function (signal) {
      seenNow[signal.id] = true;
      if (existing[signal.id]) return;
      container.appendChild(renderBannerCard(signal));
    });

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
    fetchToken()
      .then(function () { return fetch(ENDPOINT, { headers: authHeaders() }); })
      .then(function (r) {
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      })
      .then(function (body) {
        var signals = (body && body.signals) || [];
        latestSignals = signals;
        renderBanner(signals);
        notifySubscribers();
        currentInterval = BASE_INTERVAL_MS;
      })
      .catch(function () {
        currentInterval = Math.min(currentInterval * 2, MAX_INTERVAL_MS);
      })
      .then(function () {
        schedule();
      });
  }

  function schedule() {
    if (pollTimer) clearTimeout(pollTimer);
    if (document.hidden) return;
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

  // Render the stream column on the Today screen (Rule 3: completions logged
  // and linkable; Rule 6: ambient log, not a banner). The container is owned
  // by screens.js and may not exist when the user is on a different screen.
  function renderStreamList(signals) {
    var list = document.getElementById('ip-stream-list');
    if (!list) return;
    var streamItems = signals
      .filter(function (s) {
        // Banner already covers approval/urgent/error. Stream covers the rest.
        if (s.signal_type === 'approval_required') return false;
        if (s.signal_type === 'error') return false;
        if (s.priority === 'urgent') return false;
        return true;
      })
      .slice(0, 10);

    if (streamItems.length === 0) {
      var emptyText = list.getAttribute('data-empty-text') ||
        'Nothing flowing right now.';
      list.innerHTML = '<div style="color:var(--ip-gray-600);font-size:0.8125rem;">' +
        emptyText.replace(/[<>&]/g, function (c) {
          return ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c];
        }) +
        '</div>';
      return;
    }

    list.innerHTML = '';
    streamItems.forEach(function (s) {
      var row = document.createElement('div');
      row.style.cssText = [
        'display: flex',
        'gap: 0.75rem',
        'padding: 0.5rem 0',
        'border-bottom: 1px solid var(--ip-gray-200, #e5e7eb)',
        'font-size: 0.875rem',
      ].join(';');

      var dot = document.createElement('div');
      dot.style.cssText = [
        'flex: 0 0 auto',
        'width: 0.5rem',
        'height: 0.5rem',
        'border-radius: 50%',
        'margin-top: 0.4375rem',
        'background: ' + (s.signal_type === 'completion' ? '#10b981' : (s.signal_type === 'blocked' ? '#f59e0b' : '#6366f1')),
      ].join(';');
      row.appendChild(dot);

      var col = document.createElement('div');
      col.style.cssText = 'flex: 1; min-width: 0';

      var top = document.createElement('div');
      top.style.cssText = 'font-weight: 600; color: var(--ip-black, #0a0a0a)';
      // textContent escapes HTML; payload.label cannot smuggle markup.
      top.textContent = (s.payload && s.payload.label) ? s.payload.label : 'signal';
      col.appendChild(top);

      if (s.payload && s.payload.summary) {
        var sum = document.createElement('div');
        sum.style.cssText = 'color: var(--ip-gray-600, #525252); font-size: 0.8125rem; line-height: 1.35';
        sum.textContent = s.payload.summary;
        col.appendChild(sum);
      }

      var meta = document.createElement('div');
      meta.style.cssText = 'color: var(--ip-gray-500, #737373); font-size: 0.75rem; margin-top: 0.125rem';
      var when = '';
      try {
        var t = new Date(s.emitted_at);
        when = t.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
      } catch (e) { when = ''; }
      meta.textContent = sourceLabel(s.source_layer) + (when ? ' . ' + when : '');
      col.appendChild(meta);

      row.appendChild(col);
      list.appendChild(row);
    });
  }

  // Re-render the stream column on screen change. We avoid a MutationObserver
  // here because the renderer mutates #ip-stream-list itself, which would
  // create an infinite observe-render loop. Instead we poll for the element
  // identity once a second; cheap and bounded, paused while hidden.
  var _lastStreamListEl = null;
  function checkAndRenderStreamOnScreenChange() {
    var el = document.getElementById('ip-stream-list');
    if (el && el !== _lastStreamListEl) {
      _lastStreamListEl = el;
      renderStreamList(latestSignals);
    } else if (!el) {
      _lastStreamListEl = null;
    }
  }

  function boot() {
    ensureBanner();
    // Subscribe the stream renderer to live signal updates.
    subscribers.push(renderStreamList);
    // Catch screen-change re-mounts of the stream container.
    setInterval(function () {
      if (!document.hidden) checkAndRenderStreamOnScreenChange();
    }, 1000);
    poll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // Public surface for the Today-screen stream column and tests.
  window.__inpactSignals = {
    poll: poll,
    getLatest: function () { return latestSignals.slice(); },
    sourceLabel: sourceLabel,
    subscribe: function (fn) {
      if (typeof fn === 'function') {
        subscribers.push(fn);
        try { fn(latestSignals); } catch (e) { /* ignore */ }
      }
      return function unsubscribe() {
        var i = subscribers.indexOf(fn);
        if (i >= 0) subscribers.splice(i, 1);
      };
    },
    resolve: resolveSignal,
  };
})();

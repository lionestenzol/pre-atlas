/* Atlas item backbone in inPACT — renders the unified /items feed (droplist +
 * cycleboard + inpact) from atlas-map-api :3072 into the main content, so the
 * face Bruke lives in shows ALL his stuff in one place. Read-only for now.
 * Survives the navigate() screen router by re-mounting on an interval. */
(function () {
  var API = 'http://127.0.0.1:3072';
  var data = null, loading = false;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function load() {
    if (loading) return;
    loading = true;
    fetch(API + '/items')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) { data = d; mount(true); } })
      .catch(function () { /* :3072 down → no panel, inPACT unchanged */ })
      .finally(function () { loading = false; });
  }

  var META = {
    droplist:   ['#0F6E56', 'intake · packets & entities', 'http://localhost:3074/line.html'],
    cycleboard: ['#185FA5', 'conversation cards', 'http://localhost:8889/'],
    inpact:     ['#993C1D', 'projects', ''],
  };

  // Which sections are expanded. Everything starts collapsed: the panel's job is to
  // say "your stuff is here and here's how much", not to spend 1500px saying it.
  // Native <details> does the collapsing, so there's no toggle state machine here —
  // only the remembering, which the browser doesn't do for us.
  var OPEN_KEY = 'inpact-backbone-open';

  function openMap() {
    try { return JSON.parse(localStorage.getItem(OPEN_KEY)) || {}; } catch (e) { return {}; }
  }

  function setOpen(key, isOpen) {
    var m = openMap();
    m[key] = isOpen;
    try { localStorage.setItem(OPEN_KEY, JSON.stringify(m)); } catch (e) { /* quota: forget it */ }
  }

  function html() {
    var open = openMap();
    var groups = {};
    (data.items || []).forEach(function (it) { (groups[it.source] = groups[it.source] || []).push(it); });
    var body = Object.keys(groups).map(function (src) {
      var color = (META[src] || ['#5F5E5A', ''])[0];
      var label = (META[src] || ['', ''])[1];
      var url = (META[src] || ['', '', ''])[2];
      var list = groups[src];
      // stopPropagation: this link lives inside <summary>, so a bare click would
      // follow the link AND toggle the group underneath it.
      var openLink = url
        ? '<a href="' + url + '" target="_blank" rel="noopener" onclick="event.stopPropagation()"'
          + ' style="margin-left:auto;font-size:12px;color:' + color + ';text-decoration:none;">open ↗</a>'
        : '';
      var rows = list.slice(0, 6).map(function (it) {
        return '<div style="display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid #f0efe9;">'
          + '<span style="color:#1d1d1b;font-size:13px;">' + esc(it.title).slice(0, 72) + '</span>'
          + '<span style="color:#888780;font-size:11px;white-space:nowrap;">' + esc(it.status) + '</span></div>';
      }).join('');
      var more = list.length > 6 ? '<div style="font-size:11px;color:#888780;padding-top:8px;">+ ' + (list.length - 6) + ' more</div>' : '';
      return '<details class="ab-group" data-ab-key="' + esc(src) + '"' + (open[src] ? ' open' : '') + '>'
        + '<summary style="display:flex;align-items:center;gap:8px;padding:9px 0;cursor:pointer;list-style:none;">'
        + '<span style="width:10px;height:10px;border-radius:50%;background:' + color + ';display:inline-block;flex-shrink:0;"></span>'
        + '<strong style="font-size:14px;color:#1d1d1b;">' + esc(src) + '</strong>'
        + '<span style="font-size:12px;color:#888780;">' + list.length + ' · ' + esc(label) + '</span>'
        + openLink + '</summary>'
        + '<div style="padding:2px 0 14px 18px;">' + rows + more + '</div>'
        + '</details>';
    }).join('');
    return '<section id="atlas-backbone" style="background:#fff;border:1px solid #e5e4dd;border-radius:14px;padding:14px 18px;margin-bottom:16px;font-family:var(--ip-font,system-ui);">'
      + '<details class="ab-panel" data-ab-key="__panel"' + (open.__panel ? ' open' : '') + '>'
      + '<summary style="display:flex;align-items:baseline;gap:10px;cursor:pointer;list-style:none;padding:2px 0;">'
      + '<h2 style="font-size:15px;font-weight:600;color:#1d1d1b;margin:0;">Atlas backbone</h2>'
      + '<span style="font-size:12px;color:#888780;">' + (data.count || 0) + ' items across '
      + Object.keys(data.by_source || {}).length + ' surfaces · live</span>'
      + '<span class="ab-caret" style="margin-left:auto;font-size:11px;color:#888780;">'
      + (open.__panel ? 'hide' : 'show') + '</span>'
      + '</summary>'
      + '<div style="padding-top:10px;">' + body + '</div>'
      + '</details></section>';
  }

  // Daily's Minimal Mode is a one-viewport execution lens. The backbone is a
  // planning surface: mounting it afterbegin pushes the NOW block off screen,
  // which defeats the whole point of the lens. Stay out of the way there.
  function suppressed() {
    return typeof state !== 'undefined' && !!state && state.screen === 'Daily'
      && !!state.UI && state.UI.dailyView === 'minimal';
  }

  function mount(force) {
    if (!data) return;
    if (suppressed()) {
      var stale = document.getElementById('atlas-backbone');
      if (stale) stale.remove();
      return;
    }
    var host = document.querySelector('#main-content .max-w-6xl') || document.getElementById('main-content');
    if (!host) return;
    var existing = document.getElementById('atlas-backbone');
    if (existing && !force) return;
    if (existing) existing.outerHTML = html();
    else host.insertAdjacentHTML('afterbegin', html());
  }

  // Remember open/closed across the re-mount the screen router forces on us.
  // 'toggle' doesn't bubble, so capture it.
  function watchToggles() {
    document.addEventListener('toggle', function (e) {
      var d = e.target;
      if (!d || !d.matches || !d.matches('#atlas-backbone details[data-ab-key]')) return;
      setOpen(d.getAttribute('data-ab-key'), d.open);
      if (d.matches('.ab-panel')) {
        var caret = d.querySelector('.ab-caret');
        if (caret) caret.textContent = d.open ? 'hide' : 'show';
      }
    }, true);
  }

  function start() {
    load();
    watchToggles();
    // Re-mount when the navigate() router swaps the screen (replaces #main-content
    // content), instead of polling forever. Observe once the host exists.
    var main = document.getElementById('main-content');
    if (main && 'MutationObserver' in window) {
      new MutationObserver(function () { if (data && !document.getElementById('atlas-backbone')) mount(false); })
        .observe(main, { childList: true, subtree: true });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();

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

  function html() {
    var groups = {};
    (data.items || []).forEach(function (it) { (groups[it.source] = groups[it.source] || []).push(it); });
    var body = Object.keys(groups).map(function (src) {
      var color = (META[src] || ['#5F5E5A', ''])[0];
      var label = (META[src] || ['', ''])[1];
      var url = (META[src] || ['', '', ''])[2];
      var list = groups[src];
      var openLink = url
        ? '<a href="' + url + '" target="_blank" rel="noopener" style="margin-left:auto;font-size:12px;color:' + color + ';text-decoration:none;">open ↗</a>'
        : '';
      var rows = list.slice(0, 6).map(function (it) {
        return '<div style="display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid #f0efe9;">'
          + '<span style="color:#1d1d1b;font-size:13px;">' + esc(it.title).slice(0, 72) + '</span>'
          + '<span style="color:#888780;font-size:11px;white-space:nowrap;">' + esc(it.status) + '</span></div>';
      }).join('');
      var more = list.length > 6 ? '<div style="font-size:11px;color:#888780;padding-top:8px;">+ ' + (list.length - 6) + ' more</div>' : '';
      return '<div style="margin-bottom:20px;">'
        + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        + '<span style="width:10px;height:10px;border-radius:50%;background:' + color + ';display:inline-block;"></span>'
        + '<strong style="font-size:14px;color:#1d1d1b;">' + esc(src) + '</strong>'
        + '<span style="font-size:12px;color:#888780;">' + list.length + ' · ' + esc(label) + '</span>'
        + openLink + '</div>'
        + rows + more + '</div>';
    }).join('');
    return '<section id="atlas-backbone" style="background:#fff;border:1px solid #e5e4dd;border-radius:14px;padding:22px;margin-bottom:22px;font-family:var(--ip-font,system-ui);">'
      + '<div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:16px;">'
      + '<h2 style="font-size:18px;font-weight:600;color:#1d1d1b;margin:0;">Atlas backbone — all your items</h2>'
      + '<span style="font-size:13px;color:#888780;">' + (data.count || 0) + ' across ' + Object.keys(data.by_source || {}).length + ' surfaces · live</span>'
      + '</div>' + body + '</section>';
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

  function start() {
    load();
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

// Runs in the page's MAIN world (per manifest).
// Patches fetch + XMLHttpRequest so we can see requests the host page fires.
// Content script (isolated world) triggers watching via CustomEvents on window.
(() => {
  'use strict';
  if (window.__anatomyPageWorldLoaded) return;
  window.__anatomyPageWorldLoaded = true;

  const origFetch = window.fetch;
  const origOpen  = XMLHttpRequest.prototype.open;
  const origSend  = XMLHttpRequest.prototype.send;

  // id -> expireAt (ms epoch)
  const active = new Map();

  function anyActive(now) {
    let any = false;
    active.forEach((exp, id) => {
      if (now > exp) active.delete(id);
      else any = true;
    });
    return any;
  }

  function emit(method, url) {
    const now = Date.now();
    const ids = [];
    active.forEach((exp, id) => { if (now <= exp) ids.push(id); });
    if (!ids.length) return;
    window.dispatchEvent(new CustomEvent('anatomy:request', {
      detail: {
        ids,
        method: String(method || 'GET').toUpperCase(),
        url: String(url || ''),
        ts: now
      }
    }));
  }

  window.fetch = function (input, init) {
    try {
      if (anyActive(Date.now())) {
        const url = typeof input === 'string'
          ? input
          : (input && input.url) || '';
        const method = (init && init.method) || (input && input.method) || 'GET';
        emit(method, url);
      }
    } catch (_) { /* best-effort */ }
    return origFetch.apply(this, arguments);
  };

  XMLHttpRequest.prototype.open = function (method, url) {
    try {
      this.__anatomyMethod = method;
      this.__anatomyUrl = url;
    } catch (_) {}
    return origOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function () {
    try {
      if (anyActive(Date.now())) emit(this.__anatomyMethod, this.__anatomyUrl);
    } catch (_) {}
    return origSend.apply(this, arguments);
  };

  window.addEventListener('anatomy:watch', (e) => {
    const d = e.detail || {};
    if (!d.id) return;
    active.set(d.id, Date.now() + (d.duration || 3000));
  });
})();

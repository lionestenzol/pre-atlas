// Canvas pre-capture — SPEC 03 (Plan D · extension-side patch)
//
// `<canvas>` elements paint into pixel buffers via JS. `outerHTML` preserves
// the tag but loses every drawn pixel. This module walks the document and any
// reachable open shadow root, snapshots each canvas via `toDataURL`, and
// stores the data URL on the live element as `data-precapture-src` so the
// vendored copy can paint it back on replay.
//
// Mutates the live DOM IN PLACE. MUST run before any serialization step —
// before `outerHTML`, before `serializeWithShadow`, before stylesheet
// collection — so the data attributes land in the captured HTML.
//
// Exported via `window.__anatomyCanvas.precaptureCanvases(root)`.

(() => {
  'use strict';

  // 10 MB cap. Beyond this, the canvas blob bloats the envelope without much
  // visual gain; replay can re-render via the page's own renderer if loaded.
  const MAX_DATAURL_BYTES = 10 * 1024 * 1024;
  // Soft budget for the whole pre-capture phase.
  const BUDGET_MS = 100;

  function setStatus(canvas, value) {
    try { canvas.setAttribute('data-precapture-status', value); } catch (_) {}
  }

  function setAttr(canvas, name, value) {
    try { canvas.setAttribute(name, value); } catch (_) {}
  }

  function approxByteLength(dataURL) {
    if (typeof dataURL !== 'string') return 0;
    const i = dataURL.indexOf(',');
    if (i < 0) return dataURL.length;
    const b64 = dataURL.length - (i + 1);
    return Math.floor(b64 * 3 / 4);
  }

  // Best-effort context type detection without binding a fresh context.
  //
  // The HTML spec says `getContext(type)` returns null when an incompatible
  // type is already bound, so this read is safe AFTER toDataURL has succeeded
  // (which proves some context is bound). On a canvas with no context bound,
  // `getContext("2d")` would create and bind a 2d context — we avoid that by
  // preferring the page-supplied `data-context-hint` and only probing after a
  // successful capture.
  function detectContext(canvas, captureSucceeded) {
    try {
      const hint = canvas.getAttribute('data-context-hint');
      if (hint === '2d' || hint === 'webgl' || hint === 'webgl2') return hint;
    } catch (_) {}
    if (!captureSucceeded) return 'unknown';
    try {
      if (typeof canvas.getContext !== 'function') return 'unknown';
      let ctx = null;
      try { ctx = canvas.getContext('2d'); } catch (_) { ctx = null; }
      if (ctx) return '2d';
      try { ctx = canvas.getContext('webgl2'); } catch (_) { ctx = null; }
      if (ctx) return 'webgl2';
      try { ctx = canvas.getContext('webgl') || canvas.getContext('experimental-webgl'); } catch (_) { ctx = null; }
      if (ctx) return 'webgl';
    } catch (_) {}
    return 'unknown';
  }

  // Try toDataURL with PNG, then JPEG fallback (sometimes bypasses a stale
  // taint check in older engines). Returns either a data URL string or null.
  function captureDataURL(canvas) {
    try {
      const png = canvas.toDataURL('image/png');
      if (png && typeof png === 'string') return { url: png, ok: true };
    } catch (_) {
      // SecurityError on tainted canvas — fall through.
    }
    try {
      const jpg = canvas.toDataURL('image/jpeg', 0.85);
      if (jpg && typeof jpg === 'string') return { url: jpg, ok: true };
    } catch (_) {
      // Still tainted.
    }
    return { url: null, ok: false };
  }

  function processCanvas(canvas) {
    const w = canvas.width | 0;
    const h = canvas.height | 0;

    // 0x0 canvas: skip silently. Nothing to capture and emitting empty
    // attributes would just bloat the envelope.
    if (w <= 0 || h <= 0) return { skipped: true };

    const result = captureDataURL(canvas);
    if (!result.ok) {
      setStatus(canvas, 'tainted');
      setAttr(canvas, 'data-precapture-width', String(w));
      setAttr(canvas, 'data-precapture-height', String(h));
      setAttr(canvas, 'data-precapture-context', detectContext(canvas, false));
      return { tainted: true };
    }

    const bytes = approxByteLength(result.url);
    if (bytes > MAX_DATAURL_BYTES) {
      setStatus(canvas, 'oversize');
      setAttr(canvas, 'data-precapture-width', String(w));
      setAttr(canvas, 'data-precapture-height', String(h));
      setAttr(canvas, 'data-precapture-context', detectContext(canvas, true));
      return { oversize: true };
    }

    setAttr(canvas, 'data-precapture-src', result.url);
    setAttr(canvas, 'data-precapture-width', String(w));
    setAttr(canvas, 'data-precapture-height', String(h));
    setAttr(canvas, 'data-precapture-context', detectContext(canvas, true));
    return { captured: true };
  }

  // Walk document tree + every reachable open shadow root; collect <canvas>.
  function collectCanvases(root) {
    const out = [];
    const seenShadows = new WeakSet();

    function pushQueryAll(scope) {
      if (!scope || typeof scope.querySelectorAll !== 'function') return;
      let nodes;
      try { nodes = scope.querySelectorAll('canvas'); } catch (_) { return; }
      for (let i = 0; i < nodes.length; i++) out.push(nodes[i]);
    }

    function walkShadows(scope) {
      if (!scope || typeof scope.querySelectorAll !== 'function') return;
      let all;
      try { all = scope.querySelectorAll('*'); } catch (_) { return; }
      for (let i = 0; i < all.length; i++) {
        let sr = null;
        try { sr = all[i].shadowRoot; } catch (_) { sr = null; }
        if (sr && sr.mode === 'open' && !seenShadows.has(sr)) {
          seenShadows.add(sr);
          pushQueryAll(sr);
          walkShadows(sr);
        }
      }
    }

    // Root itself.
    if (root && root.nodeType === 9 /* Document */ && root.documentElement) {
      pushQueryAll(root);
      walkShadows(root);
    } else if (root && root.nodeType === 1 /* Element */) {
      if (root.localName === 'canvas') out.push(root);
      pushQueryAll(root);
      walkShadows(root);
    } else if (root && typeof root.querySelectorAll === 'function') {
      pushQueryAll(root);
      walkShadows(root);
    }

    return out;
  }

  /**
   * Snapshot every <canvas> in `root` (and reachable open shadow roots) to a
   * `data-precapture-src` attribute on the element. Mutates the live DOM.
   *
   * @param {Document | Element} root
   * @returns {{count: number, tainted: number, oversize: number, skipped: number, elapsedMs: number}}
   */
  function precaptureCanvases(root) {
    const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const target = root || (typeof document !== 'undefined' ? document : null);
    if (!target) return { count: 0, tainted: 0, oversize: 0, skipped: 0, elapsedMs: 0 };

    const canvases = collectCanvases(target);
    let captured = 0, tainted = 0, oversize = 0, skipped = 0;

    for (let i = 0; i < canvases.length; i++) {
      const c = canvases[i];
      let r;
      try { r = processCanvas(c); } catch (_) { r = { skipped: true }; }
      if (r.captured) captured++;
      else if (r.tainted) tainted++;
      else if (r.oversize) oversize++;
      else if (r.skipped) skipped++;
    }

    const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const elapsedMs = Math.max(0, t1 - t0);
    if (elapsedMs > BUDGET_MS && typeof console !== 'undefined' && console.warn) {
      try {
        console.warn('[anatomy] canvas pre-capture exceeded budget', {
          elapsedMs: Math.round(elapsedMs), canvases: canvases.length, budgetMs: BUDGET_MS,
        });
      } catch (_) {}
    }

    return { count: captured, tainted, oversize, skipped, elapsedMs };
  }

  if (typeof window !== 'undefined') {
    window.__anatomyCanvas = { precaptureCanvases };
  }
})();

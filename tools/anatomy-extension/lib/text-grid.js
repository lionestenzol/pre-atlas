// Visual-prominence grid for the live page · auto-label heatmap signal
//
// Walks every visible TextNode in the document and bins it into a NxM cell
// grid covering the FULL page. Each cell accumulates the VISUAL PROMINENCE
// of text touching it · prominence = fontSize² × contrast(text, background).
// Char count is intentionally NOT a factor: a 28px headline reading "BIG"
// must outrank a 200-char block of 11px gray legalese. That's how a real
// reader ranks the page.
//
// Why fontSize²: visual area scales quadratically with type size, and bigger
// type pulls more attention per pixel of layout. Why contrast: low-contrast
// text reads as decoration; high-contrast text reads as content (WCAG
// luminance-ratio formula).
//
// Two consumers:
//   - buildTextGrid(opts) → { cells, cols, rows, cellPx, pageW, pageH, max,
//                             textNodes, textChars }
//   - scoreRegion(grid, rect) → average cell prominence inside the region.
//     doAutoLabel uses this as a ranking signal so high-prominence zones
//     win the MAX_LABELS cap on dense pages (notion, gmail, twitter).
//   - renderGridOverlay(grid, opts) → translucent canvas overlay, scaled
//     up via CSS so grid pixels render as crisp blocks at full page size.
//
// Exported via `window.__anatomyTextGrid.{ buildTextGrid, scoreRegion,
// renderGridOverlay, removeGridOverlay }`.

(() => {
  'use strict';

  const DEFAULT_CELL_PX = 24;
  const OVERLAY_ID = 'anatomy-text-grid-overlay';
  const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE']);

  function isElementVisible(el) {
    if (!el || el.nodeType !== 1) return false;
    const cs = window.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
    return true;
  }

  // Parse "rgb(r,g,b)" or "rgba(r,g,b,a)" or "transparent" into {r,g,b,a}.
  // Returns null on failure or fully transparent.
  function parseColor(s) {
    if (!s) return null;
    const t = String(s).trim().toLowerCase();
    if (t === 'transparent' || t === 'rgba(0, 0, 0, 0)') return null;
    const m = t.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/);
    if (!m) return null;
    const a = m[4] === undefined ? 1 : parseFloat(m[4]);
    if (a === 0) return null;
    return { r: +m[1], g: +m[2], b: +m[3], a };
  }

  // WCAG relative luminance · sRGB → linear → weighted sum.
  function relLum({ r, g, b }) {
    const lin = (c) => {
      const s = c / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }

  // WCAG contrast ratio · 1 (none) to 21 (max).
  function contrastRatio(fg, bg) {
    const L1 = relLum(fg);
    const L2 = relLum(bg);
    const hi = Math.max(L1, L2);
    const lo = Math.min(L1, L2);
    return (hi + 0.05) / (lo + 0.05);
  }

  // Walk up the parent chain to find the first non-transparent
  // background-color. Defaults to white (most pages render on white).
  // Memoized per element for the duration of one buildTextGrid pass.
  function effectiveBackground(el, cache) {
    if (!el || el.nodeType !== 1) return { r: 255, g: 255, b: 255, a: 1 };
    if (cache.has(el)) return cache.get(el);
    let cur = el;
    while (cur && cur.nodeType === 1) {
      const cs = window.getComputedStyle(cur);
      const c = parseColor(cs.backgroundColor);
      if (c) { cache.set(el, c); return c; }
      cur = cur.parentElement;
    }
    const fallback = { r: 255, g: 255, b: 255, a: 1 };
    cache.set(el, fallback);
    return fallback;
  }

  // Compute prominence for a text node's parent element. Cached per element.
  // prominence = fontSize² × contrast · in arbitrary units (scoreRegion only
  // cares about relative magnitudes). Floor at fontSize=8, contrast=1.
  function computeProminence(el, promCache, bgCache) {
    if (promCache.has(el)) return promCache.get(el);
    const cs = window.getComputedStyle(el);
    const fontSize = Math.max(8, parseFloat(cs.fontSize) || 16);
    const fg = parseColor(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    const bg = effectiveBackground(el, bgCache);
    const cr = Math.max(1, contrastRatio(fg, bg));
    const prom = fontSize * fontSize * cr;
    promCache.set(el, prom);
    return prom;
  }

  function pageDimensions() {
    const de = document.documentElement;
    const body = document.body;
    const pageW = Math.max(
      de ? de.scrollWidth : 0,
      de ? de.clientWidth : 0,
      body ? body.scrollWidth : 0,
    );
    const pageH = Math.max(
      de ? de.scrollHeight : 0,
      de ? de.clientHeight : 0,
      body ? body.scrollHeight : 0,
    );
    return { pageW: Math.max(1, pageW), pageH: Math.max(1, pageH) };
  }

  function buildTextGrid(opts = {}) {
    const cellPx = Math.max(4, opts.cellPx | 0 || DEFAULT_CELL_PX);
    const root = opts.root || document.body || document.documentElement;
    const { pageW, pageH } = pageDimensions();
    const cols = Math.max(1, Math.ceil(pageW / cellPx));
    const rows = Math.max(1, Math.ceil(pageH / cellPx));
    // Uint32 so prominence accumulation can't overflow on dense pages
    // (worst case: ~28² × 21 ≈ 16000/cell × 1000 nodes ≈ 16M, well under 2³²).
    const cells = new Uint32Array(cols * rows);
    let max = 0;
    let textNodes = 0;
    let textChars = 0;
    // Per-pass caches · prominence + background lookups are O(parent-walk),
    // and the same parent serves many text nodes (every chunk of an article).
    const promCache = new WeakMap();
    const bgCache = new WeakMap();

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const v = node.nodeValue;
        if (!v || v.trim().length < 2) return NodeFilter.FILTER_REJECT;
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (SKIP_TAGS.has(parent.tagName)) return NodeFilter.FILTER_REJECT;
        if (!isElementVisible(parent)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const scrollX = window.scrollX || 0;
    const scrollY = window.scrollY || 0;
    let node;
    while ((node = walker.nextNode())) {
      const text = node.nodeValue.trim();
      if (!text) continue;
      const parent = node.parentElement;
      const prominence = computeProminence(parent, promCache, bgCache);
      const range = document.createRange();
      try {
        range.selectNodeContents(node);
      } catch (_) {
        continue;
      }
      // getClientRects returns one rect per line of wrapped text. Each cell
      // touched by ANY text rect accumulates the full prominence. Stamp model:
      // prominence is the visual weight WHERE text is present, not a fixed
      // budget split across cells. A wide line (more cells touched) deserves
      // more total grid weight than a narrow line of the same text style —
      // mass and visual area scale together.
      const rects = range.getClientRects();
      if (!rects.length) continue;
      const promCell = Math.max(1, Math.round(prominence));
      for (const rect of rects) {
        if (rect.width <= 0 || rect.height <= 0) continue;
        const x0 = rect.left + scrollX;
        const y0 = rect.top + scrollY;
        const x1 = rect.right + scrollX;
        const y1 = rect.bottom + scrollY;
        const c0 = Math.max(0, Math.floor(x0 / cellPx));
        const c1 = Math.min(cols - 1, Math.floor((x1 - 0.001) / cellPx));
        const r0 = Math.max(0, Math.floor(y0 / cellPx));
        const r1 = Math.min(rows - 1, Math.floor((y1 - 0.001) / cellPx));
        for (let r = r0; r <= r1; r++) {
          for (let c = c0; c <= c1; c++) {
            const i = r * cols + c;
            const next = cells[i] + promCell;
            cells[i] = next;
            if (next > max) max = next;
          }
        }
      }
      textNodes++;
      textChars += text.length;
    }

    return { cells, cols, rows, cellPx, pageW, pageH, max, textNodes, textChars };
  }

  // Average text density inside a page-coordinate rect. rect is the same
  // shape doAutoLabel builds for entries: { x, y, w, h } in PAGE coords
  // (already includes scrollY). Returns 0..max.
  function scoreRegion(grid, rect) {
    if (!grid || !rect || rect.w <= 0 || rect.h <= 0) return 0;
    const { cells, cols, rows, cellPx } = grid;
    const c0 = Math.max(0, Math.floor(rect.x / cellPx));
    const c1 = Math.min(cols - 1, Math.floor((rect.x + rect.w - 0.001) / cellPx));
    const r0 = Math.max(0, Math.floor(rect.y / cellPx));
    const r1 = Math.min(rows - 1, Math.floor((rect.y + rect.h - 0.001) / cellPx));
    if (c1 < c0 || r1 < r0) return 0;
    let total = 0;
    let count = 0;
    for (let r = r0; r <= r1; r++) {
      for (let c = c0; c <= c1; c++) {
        total += cells[r * cols + c];
        count++;
      }
    }
    return count > 0 ? total / count : 0;
  }

  // Render the grid as a translucent canvas, sized to cols×rows pixels but
  // CSS-scaled to the full page (image-rendering: pixelated keeps cells
  // crisp). One canvas pixel = one grid cell. Avoids allocating a giant
  // page-sized canvas (a 1500×50000 page would otherwise need ~300 MB).
  function renderGridOverlay(grid, opts = {}) {
    if (!grid) return null;
    removeGridOverlay();
    const { cells, cols, rows, cellPx, pageW, pageH, max } = grid;
    const opacity = opts.opacity != null ? opts.opacity : 0.42;
    const host = document.createElement('div');
    host.id = OVERLAY_ID;
    host.style.cssText = [
      'position:absolute',
      'top:0', 'left:0',
      `width:${pageW}px`, `height:${pageH}px`,
      'pointer-events:none',
      'z-index:2147483640',
      `opacity:${opacity}`,
      'mix-blend-mode:multiply',
    ].join(';');

    const canvas = document.createElement('canvas');
    canvas.width = cols;
    canvas.height = rows;
    canvas.style.cssText = [
      `width:${cols * cellPx}px`,
      `height:${rows * cellPx}px`,
      'image-rendering:pixelated',
      'image-rendering:-moz-crisp-edges',
      'display:block',
    ].join(';');
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    const img = ctx.createImageData(cols, rows);
    const data = img.data;
    const denom = max > 0 ? max : 1;
    for (let i = 0; i < cells.length; i++) {
      const v = cells[i];
      const o = i * 4;
      if (v === 0) {
        data[o] = 0; data[o + 1] = 0; data[o + 2] = 0; data[o + 3] = 0;
        continue;
      }
      // Sub-linear curve so mid-density still reads visually.
      const t = Math.pow(v / denom, 0.55);
      // Heatmap: cool (low) → warm (high). Hue 220 (blue) → 0 (red).
      const hue = (1 - t) * 220;
      const { r, g, b } = hslToRgb(hue, 0.85, 0.5);
      data[o] = r; data[o + 1] = g; data[o + 2] = b;
      data[o + 3] = Math.round(80 + t * 175);
    }
    ctx.putImageData(img, 0, 0);
    host.appendChild(canvas);

    const target = document.body || document.documentElement;
    target.appendChild(host);
    return host;
  }

  function removeGridOverlay() {
    const existing = document.getElementById(OVERLAY_ID);
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
  }

  function hslToRgb(h, s, l) {
    h = (h % 360 + 360) % 360 / 360;
    let r, g, b;
    if (s === 0) { r = g = b = l; }
    else {
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      r = hueToRgb(p, q, h + 1 / 3);
      g = hueToRgb(p, q, h);
      b = hueToRgb(p, q, h - 1 / 3);
    }
    return { r: Math.round(r * 255), g: Math.round(g * 255), b: Math.round(b * 255) };
  }
  function hueToRgb(p, q, t) {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  }

  window.__anatomyTextGrid = {
    buildTextGrid,
    scoreRegion,
    renderGridOverlay,
    removeGridOverlay,
  };
})();

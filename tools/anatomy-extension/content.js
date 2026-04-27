(() => {
  'use strict';
  if (window.__anatomyLoaded) return;
  window.__anatomyLoaded = true;

  const STORAGE_KEY = 'anatomy.labels.v1';
  const scopeKey = () => location.hostname + location.pathname;

  // Layer palette — canonical from ANATOMY_V1_SCHEMA.md §5
  const DEFAULT_LAYERS = {
    ui:    { color: '#c084fc' },
    api:   { color: '#f59e0b' },
    ext:   { color: '#818cf8' },
    lib:   { color: '#22c55e' },
    state: { color: '#a855f7' },
  };
  const LAYER_ORDER = ['ui', 'api', 'ext', 'lib', 'state'];

  function slugify(s) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'region';
  }

  // Ensure a stored entry has all v1 fields. Additive; never drops data.
  function normalize(entry, idx) {
    if (!entry) return entry;
    if (!entry.id) entry.id = `${slugify(entry.label)}-${entry.ts || Date.now()}-${idx || 0}`;
    if (!entry.layer) entry.layer = 'ui';
    if (!('note' in entry)) entry.note = '';
    if (!Array.isArray(entry.fetches)) entry.fetches = [];
    return entry;
  }

  let state = {
    on: false,
    labels: {},          // keyed by scopeKey()
    hoverEl: null,
    tags: [],            // rendered floating tags
    rulesVersion: 'v2',  // 'v2' (cascade) | 'legacy' (pre-v0.2 heuristic)
    patternsOn: true,    // cluster repeat containers into one "list · Nx" label
  };

  // -------------------------------------------------------------
  // Selector building (tag + :nth-of-type chain, short & stable enough)
  // -------------------------------------------------------------
  function buildSelector(el) {
    if (!(el instanceof Element)) return null;
    // Include tag prefix on the id fast-path so downstream consumers can read
    // the leaf tag (a#docs, input#search, button#save). Bare `#id` would lose
    // the tag info that canvas-engine's pattern-library uses as ground truth.
    if (el.id && /^[a-zA-Z_][\w-]*$/.test(el.id)) return el.tagName.toLowerCase() + '#' + el.id;
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body) {
      let part = cur.tagName.toLowerCase();
      const parent = cur.parentElement;
      if (parent) {
        const sibs = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
        if (sibs.length > 1) part += ':nth-of-type(' + (sibs.indexOf(cur) + 1) + ')';
      }
      parts.unshift(part);
      cur = cur.parentElement;
      if (parts.length > 8) break;
    }
    return parts.join(' > ');
  }

  function resolve(sel) {
    try { return document.querySelector(sel); } catch (e) { return null; }
  }

  // -------------------------------------------------------------
  // Persistence
  // -------------------------------------------------------------
  function load() {
    return new Promise(res => {
      chrome.storage.local.get([STORAGE_KEY], (r) => {
        state.labels = (r && r[STORAGE_KEY]) || {};
        // Migrate: mint v1 fields on any legacy entries.
        let migrated = false;
        Object.keys(state.labels).forEach(k => {
          const arr = state.labels[k] || [];
          arr.forEach((e, i) => {
            const before = JSON.stringify(e);
            normalize(e, i);
            if (JSON.stringify(e) !== before) migrated = true;
          });
        });
        if (migrated) save();
        res();
      });
    });
  }
  function save() {
    chrome.storage.local.set({ [STORAGE_KEY]: state.labels });
  }
  function scopeLabels() {
    const k = scopeKey();
    if (!state.labels[k]) state.labels[k] = [];
    return state.labels[k];
  }

  // -------------------------------------------------------------
  // Network attribution bridge (page-world.js emits anatomy:request)
  // -------------------------------------------------------------
  function startWatch(id, duration) {
    if (!id) return;
    window.dispatchEvent(new CustomEvent('anatomy:watch', { detail: { id, duration: duration || 3000 } }));
  }

  function onRequest(ev) {
    const d = ev && ev.detail;
    if (!d || !Array.isArray(d.ids) || !d.ids.length) return;
    const labels = scopeLabels();
    let changed = false;
    d.ids.forEach(id => {
      const entry = labels.find(l => l.id === id);
      if (!entry) return;
      if (!Array.isArray(entry.fetches)) entry.fetches = [];
      // Cap to 50 fetches per label to keep storage bounded.
      if (entry.fetches.length < 50) {
        entry.fetches.push({ method: d.method, url: d.url, ts: d.ts });
        changed = true;
      }
    });
    if (changed) save();
  }

  // -------------------------------------------------------------
  // Floating tags
  // -------------------------------------------------------------
  function clearTags() {
    state.tags.forEach(t => t.remove());
    state.tags = [];
    document.querySelectorAll('.anatomy-pinned-outline').forEach(el => el.classList.remove('anatomy-pinned-outline'));
  }

  function renderTags() {
    clearTags();
    if (!state.on) return;
    scopeLabels().forEach((entry, i) => {
      const el = resolve(entry.selector);
      if (!el) return;
      el.classList.add('anatomy-pinned-outline');
      const r = el.getBoundingClientRect();
      const dot = document.createElement('div');
      dot.className = 'anatomy-dot anatomy-root';
      dot.textContent = String(i + 1);
      dot.title = entry.label;
      dot.style.left = (r.left + window.scrollX - 10) + 'px';
      dot.style.top = (r.top + window.scrollY - 10) + 'px';
      dot.dataset.idx = i;
      dot.addEventListener('mouseenter', () => showTooltip(dot, entry.label));
      dot.addEventListener('mouseleave', hideTooltip);
      document.body.appendChild(dot);
      state.tags.push(dot);
    });
  }

  let tooltipEl = null;
  function showTooltip(anchor, text) {
    if (!tooltipEl) {
      tooltipEl = document.createElement('div');
      tooltipEl.className = 'anatomy-tooltip anatomy-root';
      document.body.appendChild(tooltipEl);
    }
    tooltipEl.textContent = text;
    const r = anchor.getBoundingClientRect();
    tooltipEl.style.left = (r.right + window.scrollX + 6) + 'px';
    tooltipEl.style.top  = (r.top + window.scrollY - 2) + 'px';
    tooltipEl.style.opacity = '1';
  }
  function hideTooltip() {
    if (tooltipEl) tooltipEl.style.opacity = '0';
  }

  // -------------------------------------------------------------
  // Alt+click → label prompt
  // -------------------------------------------------------------
  function onClick(e) {
    if (!state.on) return;
    if (!e.altKey) return;
    // ignore clicks inside our own UI
    if (e.target.closest('.anatomy-root')) return;
    e.preventDefault();
    e.stopPropagation();
    promptLabel(e.target, e.clientX, e.clientY);
  }

  function promptLabel(el, x, y) {
    document.querySelectorAll('.anatomy-prompt').forEach(n => n.remove());
    const box = document.createElement('div');
    box.className = 'anatomy-prompt anatomy-root';
    box.style.left = Math.min(window.innerWidth - 340, x) + 'px';
    box.style.top = Math.min(window.innerHeight - 60, y) + 'px';
    box.innerHTML = '<input type="text" placeholder="label…" /><button class="ok">save</button><button class="cancel">✕</button>';
    document.body.appendChild(box);
    const input = box.querySelector('input');
    const ok = box.querySelector('.ok');
    const cancel = box.querySelector('.cancel');
    input.focus();
    const commit = () => {
      const label = input.value.trim();
      if (label) {
        const ts = Date.now();
        const sel = buildSelector(el);
        const r = el.getBoundingClientRect();
        const entry = normalize({
          label,
          selector: sel,
          ts,
          layer: 'ui',
          kind: 'custom',
          bounds: { x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height },
        }, scopeLabels().length);
        scopeLabels().push(entry);
        save();
        renderTags();
        refreshHud();
        startWatch(entry.id, 3000);
      }
      box.remove();
    };
    ok.addEventListener('click', commit);
    cancel.addEventListener('click', () => box.remove());
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') commit();
      if (ev.key === 'Escape') box.remove();
    });
  }

  // -------------------------------------------------------------
  // Hover outline (visual hint when Alt is held)
  // -------------------------------------------------------------
  function onMove(e) {
    if (!state.on || !e.altKey) {
      if (state.hoverEl) { state.hoverEl.classList.remove('anatomy-hover-outline'); state.hoverEl = null; }
      return;
    }
    if (e.target.closest('.anatomy-root')) return;
    if (state.hoverEl === e.target) return;
    if (state.hoverEl) state.hoverEl.classList.remove('anatomy-hover-outline');
    state.hoverEl = e.target;
    state.hoverEl.classList.add('anatomy-hover-outline');
  }

  // -------------------------------------------------------------
  // HUD (list of labels + actions)
  // -------------------------------------------------------------
  let hudEl = null;
  function buildHud() {
    if (hudEl) return;
    hudEl = document.createElement('div');
    hudEl.className = 'anatomy-hud anatomy-root';
    hudEl.innerHTML = `
      <h4>Anatomy <button class="hud-help-btn" data-act="help" title="show help">?</button></h4>
      <div class="hint">Alt+click any element to label it. Hover a label to light the region.</div>
      <div class="help-panel" hidden>
        <dl>
          <dt>how to label</dt>
          <dd><b>Alt+click</b> any element · prompt pops up for a name</dd>
          <dd><b>auto-label</b> · heuristic scans the whole page, adds up to 1000 labels (buttons, links, headings, cards)</dd>
          <dt>per-label row</dt>
          <dd><b>click text</b> · scroll page to that element + pulse it</dd>
          <dd><b>[ui]/[api]/[ext]/[lib]/[state] chip</b> · click to cycle layer color</dd>
          <dd><b>✎</b> · add/edit a free-text note</dd>
          <dd><b>✕</b> · delete just this label</dd>
          <dt>row 2 · map & data</dt>
          <dd><b>make map</b> · downloads a self-contained anatomy.html with callouts + page backdrop (or live iframe if you pulled)</dd>
          <dd><b>export</b> · save labels as JSON</dd>
          <dd><b>import</b> · load labels from JSON</dd>
          <dd><b>clear page</b> · wipe all labels on this page (scope = hostname + path)</dd>
          <dt>row 3 · pull to local canvas</dt>
          <dd><b>pull this page</b> · send DOM + CSS + images to sitepull daemon at localhost:8088, serves a local copy at /c/&lt;slug&gt;/</dd>
          <dd><b>→ singlefile</b> · fallback · daemon spawns the SingleFile subprocess (slower but handles complex SPAs)</dd>
          <dt>dev</dt>
          <dd><b>rules: v2</b> · swap the auto-label cascade (v2 = browser-use port · default) ↔ legacy</dd>
        </dl>
      </div>
      <ul></ul>
      <div class="row">
        <button data-act="auto" class="anatomy-primary">auto-label</button>
        <button data-act="watch" title="record where your cursor lingers · auto-create labels at those spots (lifted from openscreen zoomSuggestionUtils)">watch me</button>
        <button data-act="grid" title="toggle a UI text-density heatmap · ranks auto-label candidates by visible-text content">grid</button>
      </div>
      <div class="row">
        <button data-act="map" class="anatomy-primary">make map</button>
        <button data-act="export">export</button>
        <button data-act="import">import</button>
        <button data-act="clear">clear page</button>
      </div>
      <div class="row">
        <button data-act="pull" class="anatomy-primary" title="POST DOM + assets to local sitepull daemon (default localhost:8088, mode=raw)">pull this page</button>
        <button data-act="pull-singlefile" title="Use SingleFile subprocess fallback for sites where raw mode breaks">→ singlefile</button>
      </div>
      <div class="row">
        <button data-act="pull-hybrid" title="Raw DOM (your auth state) + SingleFile inlined styles/fonts. Best for logged-in dashboards with CDN CSS.">→ hybrid (raw + styles)</button>
      </div>
      <div class="row anatomy-debug">
        <button data-act="rules" title="Toggle auto-label rules cascade (v2 default, legacy fallback)">rules: v2</button>
        <button data-act="patterns" title="Collapse repeating UI patterns (lists, feeds) into one 'Nx' label">patterns: on</button>
      </div>
    `;
    document.body.appendChild(hudEl);
    hudEl.addEventListener('click', onHudClick);
    hudEl.addEventListener('mouseover', onHudMouseover);
    hudEl.addEventListener('mouseout', onHudMouseout);
  }
  function refreshHud() {
    if (!hudEl) return;
    const ul = hudEl.querySelector('ul');
    const items = scopeLabels();
    ul.innerHTML = items.length
      ? items.map((e, i) => {
          const layer = e.layer || 'ui';
          const color = (DEFAULT_LAYERS[layer] || DEFAULT_LAYERS.ui).color;
          const note = e.note ? escapeHtml(e.note) : '';
          return `<li data-idx="${i}">
            <span class="lbl">${i+1}. ${escapeHtml(e.label)}${note ? ` <em class="note-peek" title="${note}">·note</em>` : ''}</span>
            <span class="layer-chip" data-act-li="cycle-layer" title="layer — click to cycle" style="background:${color}22;border-color:${color};color:${color}">${layer}</span>
            <span class="edit" data-act-li="edit-note" title="edit note">✎</span>
            <span class="rm" title="remove">✕</span>
          </li>`;
        }).join('')
      : '<li style="cursor:default;opacity:0.5;"><span class="lbl">no labels yet</span></li>';
  }
  function escapeHtml(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function onHudClick(e) {
    const act = e.target.closest('[data-act]');
    if (act) {
      const a = act.dataset.act;
      if (a === 'help') {
        const panel = hudEl.querySelector('.help-panel');
        if (panel) {
          const wasHidden = panel.hasAttribute('hidden');
          if (wasHidden) panel.removeAttribute('hidden'); else panel.setAttribute('hidden', '');
          act.textContent = wasHidden ? '×' : '?';
          act.title = wasHidden ? 'hide help' : 'show help';
        }
        return;
      }
      if (a === 'auto')   doAutoLabel().catch(err => { console.error('[anatomy] auto-label failed:', err); flash('auto-label failed · check console'); });
      if (a === 'watch')  toggleWatchMe(act).catch(err => { console.error('[anatomy] watch-me failed:', err); flash('watch failed · check console'); });
      if (a === 'grid')   toggleTextGrid(act);
      if (a === 'map')    doExportMap().catch(err => { console.error('[anatomy] export map failed:', err); flash('export failed · check console'); });
      if (a === 'export') doExport();
      if (a === 'import') doImport();
      if (a === 'pull')   doPull('raw').catch(err => { console.error('[anatomy] pull failed:', err); flash('pull failed · check console'); });
      if (a === 'pull-singlefile') doPull('singlefile').catch(err => { console.error('[anatomy] pull failed:', err); flash('singlefile pull failed · check console'); });
      if (a === 'pull-hybrid') doPull('hybrid').catch(err => { console.error('[anatomy] pull failed:', err); flash('hybrid pull failed · check console'); });
      if (a === 'rules') {
        state.rulesVersion = state.rulesVersion === 'v2' ? 'legacy' : 'v2';
        act.textContent = 'rules: ' + state.rulesVersion;
        flash('rules → ' + state.rulesVersion);
      }
      if (a === 'patterns') {
        state.patternsOn = !state.patternsOn;
        act.textContent = 'patterns: ' + (state.patternsOn ? 'on' : 'off');
        flash('patterns → ' + (state.patternsOn ? 'on' : 'off'));
      }
      if (a === 'clear') {
        // Strip our visual classes from anywhere on the page so the next
        // auto-label run sees a clean DOM.
        document.querySelectorAll('.anatomy-pinned-outline, .anatomy-hover-outline, .anatomy-lit')
          .forEach(el => el.classList.remove('anatomy-pinned-outline', 'anatomy-hover-outline', 'anatomy-lit'));
        state.hoverEl = null;
        state.labels[scopeKey()] = [];
        save(); renderTags(); refreshHud();
        flash('cleared');
      }
      return;
    }
    const rm = e.target.closest('.rm');
    if (rm) {
      const li = rm.closest('li');
      scopeLabels().splice(+li.dataset.idx, 1);
      save(); renderTags(); refreshHud();
      return;
    }
    // Click the label text → scroll to its element and pulse it. Hovering
    // already does this, but on long lists hover-scroll gets cancelled the
    // moment the cursor leaves the HUD for the mouse wheel. Click is durable.
    const lbl = e.target.closest('.lbl');
    if (lbl) {
      const li = lbl.closest('li');
      if (!li || li.dataset.idx == null) return;
      const entry = scopeLabels()[+li.dataset.idx];
      if (!entry) return;
      const el = resolve(entry.selector);
      if (!el) { flash('element gone · selector stale'); return; }
      el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
      // Pulse for ~1.2s so it's easy to spot after the scroll settles.
      el.classList.add('anatomy-lit');
      setTimeout(() => el.classList.remove('anatomy-lit'), 1200);
      return;
    }
    const liAct = e.target.closest('[data-act-li]');
    if (liAct) {
      e.stopPropagation();
      const li = liAct.closest('li');
      const idx = +li.dataset.idx;
      const entry = scopeLabels()[idx];
      if (!entry) return;
      const a = liAct.dataset.actLi;
      if (a === 'cycle-layer') {
        const cur = LAYER_ORDER.indexOf(entry.layer || 'ui');
        entry.layer = LAYER_ORDER[(cur + 1) % LAYER_ORDER.length];
        save(); refreshHud();
      } else if (a === 'edit-note') {
        openNoteEditor(li, idx);
      }
    }
  }

  function openNoteEditor(li, idx) {
    const existing = li.querySelector('.note-editor');
    if (existing) { existing.querySelector('textarea').focus(); return; }
    const box = document.createElement('div');
    box.className = 'note-editor';
    box.innerHTML = `<textarea placeholder="free-text note…" rows="2"></textarea>`;
    li.appendChild(box);
    const ta = box.querySelector('textarea');
    const entry = scopeLabels()[idx];
    ta.value = (entry && entry.note) || '';
    ta.focus();
    const commit = () => {
      const v = ta.value.trim();
      if (entry) { entry.note = v; save(); }
      box.remove();
      refreshHud();
    };
    ta.addEventListener('blur', commit, { once: true });
    ta.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') { ta.value = (entry && entry.note) || ''; ta.blur(); }
      if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) ta.blur();
    });
  }
  function onHudMouseover(e) {
    const li = e.target.closest('li[data-idx]');
    if (!li) return;
    const entry = scopeLabels()[+li.dataset.idx];
    const el = entry && resolve(entry.selector);
    if (el) { el.classList.add('anatomy-lit'); el.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
  }
  function onHudMouseout(e) {
    document.querySelectorAll('.anatomy-lit').forEach(el => el.classList.remove('anatomy-lit'));
  }

  // -------------------------------------------------------------
  // Export / Import
  // -------------------------------------------------------------
  // Group a region set's fetches by URL host into schema-§4 chains.
  // Each chain: api endpoint summary (method + sample path) → ext host node.
  // Node numbering continues the regions namespace (see schema §6).
  function buildChains(regions) {
    const byHost = new Map();
    regions.forEach(r => {
      const fetches = Array.isArray(r.fetches) ? r.fetches : [];
      fetches.forEach(f => {
        if (!f || !f.url) return;
        let u;
        try { u = new URL(f.url, location.href); } catch (_) { return; }
        // Skip data:/blob:/about: — they parse but collapse host to '' and leak full payloads into paths.
        if (u.protocol !== 'http:' && u.protocol !== 'https:') return;
        const host = u.host;
        if (!host) return;
        const path = (u.pathname || '/') + (u.search || '');
        if (!byHost.has(host)) byHost.set(host, { host, entries: [], regionIds: new Set() });
        const bucket = byHost.get(host);
        bucket.entries.push({ method: f.method || 'GET', path, ts: f.ts });
        if (r.id) bucket.regionIds.add(r.id);
      });
    });

    let n = regions.length;
    const out = [];
    for (const { host, entries, regionIds } of byHost.values()) {
      const methods = Array.from(new Set(entries.map(e => e.method))).sort();
      const paths = Array.from(new Set(entries.map(e => e.path)));
      const samplePath = paths[0] || '/';
      const methodsLabel = methods.join('/');
      const apiLabel = `${methodsLabel} ${samplePath}`.slice(0, 48);
      const apiDetail = paths.length > 1 ? `${entries.length} calls · ${paths.length} paths` : `${entries.length} call${entries.length === 1 ? '' : 's'}`;
      const extDetail = `${regionIds.size} region${regionIds.size === 1 ? '' : 's'}`;

      n++;
      const apiNode = { n, layer: 'api', label: apiLabel, detail: apiDetail };
      n++;
      const extNode = { n, layer: 'ext', label: host, detail: extDetail };

      out.push({
        // Host is unique within one envelope (byHost keyed on host), so no timestamp needed.
        id: `chain-${slugify(host)}`,
        nodes: [apiNode, extNode],
      });
    }
    return out;
  }

  function buildAnatomyV1() {
    const vocab = (typeof window !== 'undefined' && window.AnatomyDetectionVocab) || null;
    const labels = scopeLabels();
    const regions = [];
    const dropped = [];
    labels.forEach((e, i) => {
      const rawDetection = e.reason || (e.auto ? 'auto-label' : 'alt-click');
      const migrated = vocab ? vocab.migrateDetection(rawDetection) : rawDetection;
      const candidate = {
        id: e.id,
        n: regions.length + 1,
        name: e.label,
        layer: e.layer || 'ui',
        selector: e.selector,
        detection: migrated,
        desc: e.kind || 'custom',
        note: e.note || '',
        kind: e.kind,
        bounds: e.bounds,
        fetches: Array.isArray(e.fetches) ? e.fetches : [],
      };
      if (vocab) {
        const v = vocab.validateRegion(candidate);
        if (!v.ok) {
          dropped.push({ id: candidate.id, reason: v.reason });
          return;
        }
        regions.push(v.fixed);
      } else {
        if (!candidate.kind) candidate.kind = 'custom';
        regions.push(candidate);
      }
    });
    if (dropped.length) {
      console.warn('[anatomy] dropped ' + dropped.length + ' region(s) with unknown detection:', dropped);
    }
    return {
      version: 'anatomy-v1',
      metadata: {
        target: location.href,
        mode: 'extension',
        source: scopeKey(),
        timestamp: new Date().toISOString(),
        tools: ['anatomy-extension@0.4.1'],
      },
      regions,
      chains: buildChains(regions),
      layers: DEFAULT_LAYERS,
    };
  }

  // ---------- Anatomy map HTML renderer (v0.2.1) ----------
  // Takes the anatomy-v1 envelope + a snapshot of the page viewport
  // and returns a self-contained HTML document with callouts + mockup
  // + leader lines. No CDN deps, inline CSS. One file, one download.
  function generateMapHtml(envelope, opts = {}) {
    const { regions, layers, metadata, chains } = envelope;
    const { screenshot, viewport } = opts;
    const vw = Math.max(document.documentElement.clientWidth, 1);
    const vh = Math.max(document.documentElement.clientHeight, 1);
    const scrollH = Math.max(document.documentElement.scrollHeight, 1);
    const scrollW = Math.max(document.documentElement.scrollWidth, 1);
    const layerColor = (l) => (layers[l] || layers.ui || { color: '#c084fc' }).color;

    const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    // Center mockup: bigger width + enforced minimum box height so labels stay readable
    // even on long pages (HN, reddit). Slightly distorts positions for tall pages, but
    // the payoff is "I can tell what each box is from 3 feet away".
    const mockupW = 1100;
    const targetAspect = scrollH / scrollW;
    const mockupH = Math.round(mockupW * Math.min(targetAspect, 1.6)); // cap tall pages
    const scaleX = mockupW / scrollW, scaleY = mockupH / scrollH;
    const MIN_BOX_H = 22;
    const MIN_BOX_W = 60;
    const mockupBoxes = regions.map(r => {
      if (!r.bounds) return '';
      const x = Math.round(r.bounds.x * scaleX);
      const y = Math.round(r.bounds.y * scaleY);
      const rawW = Math.round(r.bounds.w * scaleX);
      const rawH = Math.round(r.bounds.h * scaleY);
      const w = Math.max(MIN_BOX_W, rawW);
      const h = Math.max(MIN_BOX_H, rawH);
      const c = layerColor(r.layer);
      const showLabel = w >= 90 && h >= 22;
      return `<div class="mk-box" data-n="${r.n}" data-layer="${r.layer}" title="${escapeHtml(r.name)}" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-color:${c};background:${c}22;color:${c}">
        <span class="mk-n">${r.n}</span>
        ${showLabel ? `<span class="mk-lbl">${escapeHtml(r.name)}</span>` : ''}
      </div>`;
    }).join('');

    // Backdrop modes (mutually exclusive):
    // 1. iframeSrc — live vendored copy from sitepull daemon. Entire page
    //    dimensions (scrollW × scrollH), transform-scaled to fit the mockup.
    //    Regions overlay in mockup coords and stay aligned.
    // 2. screenshot — PNG dataURL captured via chrome.tabs.captureVisibleTab,
    //    mapped into mockup coords at viewport position. Historical fallback.
    let backdropHtml = '';
    if (opts.iframeSrc) {
      // Full page inside iframe, then scale. Use min scale to ensure both axes fit.
      const scale = Math.min(scaleX, scaleY);
      backdropHtml = `<iframe class="mk-backdrop mk-backdrop-iframe" src="${opts.iframeSrc}" loading="eager" sandbox="allow-same-origin allow-scripts" style="left:0;top:0;width:${scrollW}px;height:${scrollH}px;transform:scale(${scaleX}, ${scaleY});transform-origin:0 0;border:0;"></iframe>`;
    } else if (screenshot && viewport) {
      const bx = Math.round((viewport.scrollX || 0) * scaleX);
      const by = Math.round((viewport.scrollY || 0) * scaleY);
      const bw = Math.round((viewport.vw || vw) * scaleX);
      const bh = Math.round((viewport.vh || vh) * scaleY);
      backdropHtml = `<img class="mk-backdrop" src="${screenshot}" alt="viewport snapshot" style="left:${bx}px;top:${by}px;width:${bw}px;height:${bh}px">`;
    }

    // Split callouts left/right by position
    const left = [], right = [];
    regions.forEach(r => ((r.bounds && r.bounds.x < scrollW / 2) ? left : right).push(r));

    // Edit mode is only available when the map has a live vendored backdrop
    // (iframe → daemon slug). For static-screenshot maps, there's no file on
    // disk to rewrite, so edit buttons would be dead-end.
    const editMode = !!(opts.iframeSrc && opts.slug);

    const renderCallout = (r) => {
      const c = layerColor(r.layer);
      const editBtn = editMode
        ? `<button class="co-edit" data-act="edit" data-n="${r.n}" data-selector="${escapeHtml(r.selector || '')}" data-name="${escapeHtml(r.name)}" title="edit with Claude">✎</button>`
        : '';
      return `<div class="callout" data-n="${r.n}" data-layer="${r.layer}" style="border-color:${c}66;background:${c}14;color:${c}">
        <span class="no" style="border-color:${c}">${r.n}</span>
        ${editBtn}
        <div class="hd">${escapeHtml(r.name)}</div>
        <div class="pth">${escapeHtml(r.selector || '')}</div>
        ${r.note ? `<div class="dsc">${escapeHtml(r.note)}</div>` : ''}
        ${r.detection ? `<div class="dsc">detection: ${escapeHtml(r.detection)}</div>` : ''}
        ${(r.fetches && r.fetches.length) ? `<div class="dsc">${r.fetches.length} fetch${r.fetches.length===1?'':'es'}</div>` : ''}
      </div>`;
    };

    const layerButtons = Object.keys(layers).map(l =>
      `<button data-layer-filter="${l}" class="lf on" style="border-color:${layers[l].color};color:${layers[l].color}">${l}</button>`
    ).join('');

    const viewButtons = `
      <button data-toggle="tour" class="tb">tour</button>
      <button data-toggle="numbers" class="tb on">numbers</button>
      <button data-toggle="labels" class="tb on">labels</button>
      <button data-toggle="lines" class="tb">lines</button>
    `;

    // Chains strip — one chip per host, colored by the `ext` layer.
    const safeChains = Array.isArray(chains) ? chains : [];
    const chainsStripHtml = safeChains.length ? `
    <div class="chains">
      <div class="chains-hd">chains · ${safeChains.length} host${safeChains.length === 1 ? '' : 's'}</div>
      <div class="chains-row">
        ${safeChains.map(c => {
          const apiNode = c.nodes && c.nodes[0];
          const extNode = c.nodes && c.nodes[c.nodes.length - 1];
          if (!extNode) return '';
          const color = layerColor(extNode.layer);
          const apiColor = apiNode ? layerColor(apiNode.layer) : color;
          return `<div class="chain" data-chain-id="${escapeHtml(c.id || '')}" style="border-color:${color}66">
            <span class="chain-n" style="background:${color}33;color:${color}">${extNode.n}</span>
            <span class="chain-host" style="color:${color}">${escapeHtml(extNode.label)}</span>
            ${apiNode ? `<span class="chain-api" style="color:${apiColor}">${escapeHtml(apiNode.label)}</span>` : ''}
            ${apiNode && apiNode.detail ? `<span class="chain-detail">${escapeHtml(apiNode.detail)}</span>` : ''}
            ${extNode.detail ? `<span class="chain-detail">${escapeHtml(extNode.detail)}</span>` : ''}
          </div>`;
        }).join('')}
      </div>
    </div>` : '';

    return `<!doctype html>
<html><head><meta charset="utf-8"><title>Anatomy · ${escapeHtml(metadata.source || metadata.target)}</title>
<style>
  :root { --bg:#080808; --border:rgba(255,255,255,0.06); --text:#c8c8c8; --dim:#666; }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px 32px 40px; background:var(--bg); color:var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size:12px; }
  .mono { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; }
  h1 { margin:0 0 4px 0; font-size:16px; color:#fff; letter-spacing:2px; }
  .sub { font-size:10px; color:var(--dim); letter-spacing:1.5px; text-transform:uppercase; }
  .head { display:flex; justify-content:space-between; align-items:flex-end; padding-bottom:16px; margin-bottom:24px; border-bottom:1px solid var(--border); }
  .toolbar { display:flex; gap:6px; align-items:center; }
  .toolbar .lf { padding:4px 10px; background:transparent; border:1px solid; border-radius:4px; font-size:10px; text-transform:uppercase; letter-spacing:1px; cursor:pointer; opacity:0.35; }
  .toolbar .lf.on { opacity:1; }
  .toolbar .tb { padding:4px 10px; background:transparent; border:1px solid rgba(255,255,255,0.18); color:#888; border-radius:4px; font-size:10px; text-transform:uppercase; letter-spacing:1px; cursor:pointer; }
  .toolbar .tb.on { border-color:#c084fc; color:#c084fc; }
  .tb-sep { width:1px; height:18px; background:rgba(255,255,255,0.12); margin:0 4px; }
  .stage { position:relative; display:grid; grid-template-columns: 240px minmax(${mockupW}px, 1fr) 240px; gap:32px; align-items:start; }
  .leader-lines { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; opacity:0; transition:opacity 0.2s ease-out; z-index:20; overflow:visible; }
  .leader-lines.on { opacity:0.5; }
  .leader-lines path { fill:none; stroke-width:1; stroke-dasharray:3 3; }
  body.no-numbers .mk-n { display:none; }
  body.no-numbers .callout .no { display:none; }
  .mk-lbl { opacity:0.78; transition:opacity 0.12s ease; }
  .mk-box:hover .mk-lbl, .mk-box.lit .mk-lbl { opacity:1; }
  body.no-labels .mk-lbl { display:none; }
  .col { display:flex; flex-direction:column; gap:10px; padding-top:24px; }
  .callout { position:relative; padding:10px 12px 8px; border:1px solid; border-radius:6px; font-size:11px; transition:all 0.15s ease; cursor:pointer; }
  .callout .no { position:absolute; top:-8px; left:-8px; width:18px; height:18px; border-radius:50%; background:var(--bg); border:1px solid; display:flex; align-items:center; justify-content:center; font-size:9px; font-weight:700; }
  .callout .hd { font-weight:700; letter-spacing:0.5px; text-transform:uppercase; font-size:10px; margin-bottom:3px; }
  .callout .pth { font-family:'JetBrains Mono', monospace; font-size:9px; color:#888; word-break:break-all; }
  .callout .dsc { font-size:10px; color:#888; margin-top:3px; }
  .callout.lit { transform:translateY(-1px); box-shadow:0 0 0 1px currentColor, 0 6px 20px rgba(0,0,0,0.4); }
  .callout.dim { opacity:0.15; }
  .mockup-wrap { position:relative; }
  .mockup { position:relative; width:${mockupW}px; height:${mockupH}px; background:#0c0c0c;
    border:1px solid rgba(255,255,255,0.08); border-radius:6px; overflow:hidden;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(192,132,252,0.08); }
  .mk-backdrop { position:absolute; opacity:0; transition:opacity 0.45s ease-out; pointer-events:none; object-fit:fill; z-index:0; filter:saturate(0.9) brightness(0.95); }
  .mk-backdrop.loaded { opacity:0.55; }
  /* iframe variant: live vendored copy. Higher opacity (it's the real thing,
     not a screenshot) and pointer-events back on so users can scroll inside
     the page within the iframe when zooming in. */
  .mk-backdrop-iframe { filter:none; pointer-events:auto; background:#0c0c0c; }
  .mk-backdrop-iframe.loaded { opacity:0.92; }
  .mk-box { position:absolute; border:1px dashed; border-radius:2px; opacity:0.75; transition:all 0.15s ease; cursor:pointer; z-index:1; }
  .mk-box:hover, .mk-box.lit { opacity:1; transform:scale(1.02); box-shadow:0 0 18px currentColor; z-index:10; }
  .mk-box.dim { opacity:0.1; }
  .mk-n { position:absolute; top:2px; left:2px; font-size:8px; font-weight:700; padding:1px 4px; background:rgba(0,0,0,0.7); border-radius:2px; color:#fff; font-family:'JetBrains Mono', monospace; }
  .mk-lbl { position:absolute; left:22px; top:2px; right:4px; font-size:10px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; letter-spacing:0.3px; text-shadow:0 1px 2px rgba(0,0,0,0.6); }
  .chains { margin-top:28px; padding:14px 18px 16px; background:rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:8px; }
  .chains-hd { font-size:10px; letter-spacing:1.5px; text-transform:uppercase; color:var(--dim); margin-bottom:10px; }
  .chains-row { display:flex; flex-wrap:wrap; gap:8px; }
  .chain { display:flex; align-items:center; gap:10px; padding:6px 10px 5px; border:1px solid; border-radius:4px; font-size:11px; background:rgba(255,255,255,0.015); }
  .chain-n { font-family:'JetBrains Mono', monospace; font-size:9px; font-weight:700; padding:2px 6px; border-radius:2px; }
  .chain-host { font-weight:600; letter-spacing:0.3px; }
  .chain-api { font-family:'JetBrains Mono', monospace; font-size:10px; opacity:0.85; }
  .chain-detail { font-family:'JetBrains Mono', monospace; font-size:9px; color:#666; }
  .foot { margin-top:40px; padding-top:16px; border-top:1px solid var(--border); font-size:10px; color:var(--dim); letter-spacing:1px; text-transform:uppercase; text-align:center; }
  /* Edit button on each callout (iframe mode only). Floats top-right so it
     doesn't push the header line. Appears on hover of the callout. */
  .callout { position:relative; }
  .co-edit { position:absolute; top:6px; right:6px; opacity:0; transition:opacity 0.12s ease;
    width:22px; height:22px; padding:0; line-height:1;
    background:rgba(192,132,252,0.15); border:1px solid rgba(192,132,252,0.4); border-radius:4px;
    color:#c084fc; font-size:12px; cursor:pointer; z-index:2; }
  .callout:hover .co-edit, .callout.lit .co-edit { opacity:1; }
  .co-edit:hover { background:rgba(192,132,252,0.3); color:#fff; }
  /* Modal for Claude-edit flow */
  .edit-modal { position:fixed; inset:0; background:rgba(0,0,0,0.75); z-index:1000;
    display:none; align-items:center; justify-content:center; backdrop-filter:blur(2px); }
  .edit-modal.on { display:flex; }
  .edit-modal-inner { background:#0c0c0c; border:1px solid rgba(192,132,252,0.4); border-radius:8px;
    width:min(560px, 90vw); padding:20px 22px; box-shadow:0 20px 60px rgba(0,0,0,0.6); }
  .em-head { font-size:10px; text-transform:uppercase; letter-spacing:1.5px; color:#c084fc; margin-bottom:6px; }
  .em-region { font-size:14px; color:#fff; font-weight:700; margin-bottom:4px; }
  .em-selector { font-family:'JetBrains Mono',monospace; font-size:10px; color:#666; margin-bottom:14px; word-break:break-all; }
  .em-prompt { width:100%; min-height:80px; background:rgba(255,255,255,0.05); color:#fff;
    border:1px solid rgba(255,255,255,0.1); border-radius:4px; padding:10px 12px;
    font-size:13px; font-family:inherit; resize:vertical; }
  .em-prompt:focus { outline:none; border-color:#c084fc; }
  .em-prompt::placeholder { color:#555; }
  .em-status { font-size:11px; color:#888; margin-top:10px; min-height:16px; font-family:'JetBrains Mono',monospace; }
  .em-status.error { color:#f87171; }
  .em-status.ok { color:#86efac; }
  .em-buttons { display:flex; justify-content:flex-end; gap:8px; margin-top:14px; }
  .em-buttons button { padding:6px 14px; border-radius:4px; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; cursor:pointer; }
  .em-cancel { background:transparent; color:#888; border:1px solid rgba(255,255,255,0.15); }
  .em-cancel:hover { color:#fff; border-color:rgba(255,255,255,0.4); }
  .em-submit { background:#c084fc; color:#0a0a0a; border:0; font-weight:700; }
  .em-submit:hover { background:#d4a3ff; }
  .em-submit:disabled { opacity:0.5; cursor:wait; }
  /* Tour player ── lifted from openscreen mathUtils.ts (Screen-Studio easing) */
  body.touring { cursor:progress; }
  body.touring .toolbar > *:not([data-toggle="tour"]) { opacity:0.4; pointer-events:none; }
  .toolbar .tb[data-toggle="tour"].on { border-color:#f59e0b; color:#fde68a; background:rgba(245,158,11,0.18); }
  .callout.touring-active { transform:translateY(-2px) scale(1.04);
    box-shadow:0 0 0 2px currentColor, 0 0 28px currentColor; z-index:30; }
  .mk-box.touring-active { opacity:1 !important; outline:3px solid #c084fc; outline-offset:3px;
    box-shadow:0 0 50px rgba(192,132,252,0.6); z-index:25 !important; }
  body.touring .leader-lines { opacity:0; transition:opacity 0.18s ease; }
</style></head>
<body>
  <div class="head">
    <div>
      <h1>${escapeHtml(metadata.source || new URL(metadata.target).hostname)}</h1>
      <div class="sub">anatomy · ${regions.length} regions · ${escapeHtml(metadata.mode || 'extension')} · ${escapeHtml((metadata.tools || []).join(', '))}</div>
    </div>
    <div class="toolbar">${viewButtons}<span class="tb-sep"></span>${layerButtons}</div>
  </div>
  <div class="stage">
    <svg class="leader-lines" aria-hidden="true"></svg>
    <div class="col">${left.map(renderCallout).join('')}</div>
    <div class="mockup-wrap"><div class="mockup"><div class="mockup-inner" style="position:absolute;inset:0;transform-origin:0 0;will-change:transform">${backdropHtml}${mockupBoxes}</div></div></div>
    <div class="col">${right.map(renderCallout).join('')}</div>
  </div>
  ${chainsStripHtml}
  ${editMode ? `
  <div class="edit-modal" id="editModal">
    <div class="edit-modal-inner">
      <div class="em-head">edit region · claude rewrites the vendored copy</div>
      <div class="em-region" id="emRegion"></div>
      <div class="em-selector" id="emSelector"></div>
      <textarea class="em-prompt" id="emPrompt" placeholder="what do you want to change? e.g. 'make this button purple and say sign up'"></textarea>
      <div class="em-status" id="emStatus"></div>
      <div class="em-buttons">
        <button class="em-cancel" id="emCancel">cancel</button>
        <button class="em-submit" id="emSubmit">edit with claude</button>
      </div>
    </div>
  </div>` : ''}
  <div class="foot">generated by anatomy-extension · ${escapeHtml(metadata.timestamp)}${editMode ? ` · edit mode via ${escapeHtml(opts.daemonBase)}` : ''}</div>
<script>
  const callouts = Array.from(document.querySelectorAll('.callout'));
  const boxes = Array.from(document.querySelectorAll('.mk-box'));
  function lightN(n) {
    callouts.concat(boxes).forEach(e => e.classList.toggle('lit', e.dataset.n === n));
  }
  function clearLit() { callouts.concat(boxes).forEach(e => e.classList.remove('lit')); }
  callouts.forEach(c => {
    c.addEventListener('mouseenter', () => lightN(c.dataset.n));
    c.addEventListener('mouseleave', clearLit);
  });
  boxes.forEach(b => {
    b.addEventListener('mouseenter', () => lightN(b.dataset.n));
    b.addEventListener('mouseleave', clearLit);
  });
  // layer filter
  const activeLayers = new Set(Object.keys(${JSON.stringify(layers).replace(/<\/script>/gi, '<\\/script>')}));
  document.querySelectorAll('[data-layer-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      const l = btn.dataset.layerFilter;
      if (activeLayers.has(l)) { activeLayers.delete(l); btn.classList.remove('on'); }
      else { activeLayers.add(l); btn.classList.add('on'); }
      callouts.concat(boxes).forEach(e => e.classList.toggle('dim', !activeLayers.has(e.dataset.layer)));
    });
  });
  // Progressive reveal: rectangles paint first (stage 1), backdrop fades in next frame (stage 2).
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const b = document.querySelector('.mk-backdrop');
    if (b) b.classList.add('loaded');
  }));

  // View toggles: numbers + leader lines
  const numbersBtn = document.querySelector('[data-toggle="numbers"]');
  const linesBtn = document.querySelector('[data-toggle="lines"]');
  const linesSvg = document.querySelector('.leader-lines');
  const stage = document.querySelector('.stage');

  function drawLeaderLines() {
    if (!linesSvg || !stage) return;
    linesSvg.innerHTML = '';
    const stageRect = stage.getBoundingClientRect();
    callouts.forEach(c => {
      const n = c.dataset.n;
      const box = document.querySelector('.mk-box[data-n="' + n + '"]');
      if (!box) return;
      const cr = c.getBoundingClientRect();
      const br = box.getBoundingClientRect();
      const calloutIsLeft = cr.right < br.left;
      const cx = (calloutIsLeft ? cr.right : cr.left) - stageRect.left;
      const cy = cr.top + cr.height / 2 - stageRect.top;
      const bx = (calloutIsLeft ? br.left : br.right) - stageRect.left;
      const by = br.top + br.height / 2 - stageRect.top;
      const mx = (cx + bx) / 2;
      const d = 'M ' + cx + ' ' + cy + ' C ' + mx + ' ' + cy + ', ' + mx + ' ' + by + ', ' + bx + ' ' + by;
      const color = getComputedStyle(c).color || '#c084fc';
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('stroke', color);
      path.dataset.n = n;
      linesSvg.appendChild(path);
    });
  }

  if (numbersBtn) {
    numbersBtn.addEventListener('click', () => {
      numbersBtn.classList.toggle('on');
      document.body.classList.toggle('no-numbers', !numbersBtn.classList.contains('on'));
    });
  }
  const labelsBtn = document.querySelector('[data-toggle="labels"]');
  if (labelsBtn) {
    labelsBtn.addEventListener('click', () => {
      labelsBtn.classList.toggle('on');
      document.body.classList.toggle('no-labels', !labelsBtn.classList.contains('on'));
    });
  }
  if (linesBtn && linesSvg) {
    linesBtn.addEventListener('click', () => {
      linesBtn.classList.toggle('on');
      const on = linesBtn.classList.contains('on');
      linesSvg.classList.toggle('on', on);
      if (on) drawLeaderLines();
    });
    window.addEventListener('resize', () => {
      if (linesBtn.classList.contains('on')) drawLeaderLines();
    });
  }

  // ── Tour player ────────────────────────────────────────────────────
  // Easing ported from openscreen/src/components/video-editor/videoPlayback/
  // mathUtils.ts — cubicBezier(0.16, 1, 0.3, 1) is the Screen-Studio feel.
  function _clamp01(v) { return Math.max(0, Math.min(1, v)); }
  function _bz(a1, a2, t) { const m = 1 - t; return 3*a1*m*m*t + 3*a2*m*t*t + t*t*t; }
  function _bzD(a1, a2, t) { const m = 1 - t; return 3*a1*m*m + 6*(a2-a1)*m*t + 3*(1-a2)*t*t; }
  function _cubicBezier(x1, y1, x2, y2, t) {
    const tx = _clamp01(t); let s = tx;
    for (let i = 0; i < 8; i++) {
      const cx = _bz(x1, x2, s) - tx; const cd = _bzD(x1, x2, s);
      if (Math.abs(cx) < 1e-6 || Math.abs(cd) < 1e-6) break;
      s -= cx / cd;
    }
    let lo = 0, hi = 1; s = _clamp01(s);
    for (let i = 0; i < 10; i++) {
      const cx = _bz(x1, x2, s);
      if (Math.abs(cx - tx) < 1e-6) break;
      if (cx < tx) lo = s; else hi = s;
      s = (lo + hi) / 2;
    }
    return _bz(y1, y2, s);
  }
  const _easeSS = (t) => _cubicBezier(0.16, 1, 0.3, 1, t);
  function _animate(duration, onTick) {
    return new Promise(resolve => {
      const start = performance.now();
      function step(now) {
        const t = Math.min(1, (now - start) / duration);
        onTick(_easeSS(t));
        if (t < 1) requestAnimationFrame(step); else resolve();
      }
      requestAnimationFrame(step);
    });
  }
  function _smoothScrollTo(targetY, duration) {
    const startY = window.scrollY;
    const dy = Math.max(0, targetY) - startY;
    if (Math.abs(dy) < 2) return Promise.resolve();
    return _animate(duration, e => window.scrollTo(0, startY + dy * e));
  }

  // ── Pan & zoom on .mockup-inner ────────────────────────────────────
  const _mockup = document.querySelector('.mockup');
  const _mockupInner = document.querySelector('.mockup-inner');
  const _mw = _mockup ? _mockup.clientWidth : 1100;
  const _mh = _mockup ? _mockup.clientHeight : 1700;
  let _zoom = { tx: 0, ty: 0, scale: 1 };
  function _applyZoom(z) {
    if (!_mockupInner) return;
    _mockupInner.style.transform = 'translate(' + z.tx + 'px,' + z.ty + 'px) scale(' + z.scale + ')';
  }
  function _zoomForBox(box) {
    if (!box) return { tx: 0, ty: 0, scale: 1 };
    const L = box.offsetLeft, T = box.offsetTop, W = box.offsetWidth, H = box.offsetHeight;
    const scale = Math.min(_mw / W, _mh / H) * 0.85;
    const cx = L + W / 2, cy = T + H / 2;
    return { tx: _mw / 2 - cx * scale, ty: _mh / 2 - cy * scale, scale };
  }
  function _animateZoomTo(target, duration) {
    const from = { ..._zoom };
    return _animate(duration, e => {
      _zoom = {
        tx: from.tx + (target.tx - from.tx) * e,
        ty: from.ty + (target.ty - from.ty) * e,
        scale: from.scale + (target.scale - from.scale) * e,
      };
      _applyZoom(_zoom);
    });
  }

  const tourBtn = document.querySelector('[data-toggle="tour"]');
  let _stopTour = null;
  function _clearTouringMarks() {
    document.querySelectorAll('.touring-active').forEach(el => el.classList.remove('touring-active'));
  }
  async function runTour() {
    const seq = callouts.slice().sort((a, b) => +a.dataset.n - +b.dataset.n);
    if (!seq.length) return;
    document.body.classList.add('touring');
    tourBtn.textContent = 'stop';
    tourBtn.classList.add('on');
    let stopped = false;
    _stopTour = () => { stopped = true; };
    for (const co of seq) {
      if (stopped) break;
      clearLit();
      _clearTouringMarks();
      const box = document.querySelector('.mk-box[data-n="' + co.dataset.n + '"]');
      co.classList.add('touring-active');
      if (box) box.classList.add('touring-active');
      lightN(co.dataset.n);
      const focusEl = box || co;
      const r = focusEl.getBoundingClientRect();
      const targetY = window.scrollY + r.top - window.innerHeight / 2 + r.height / 2;
      const zoomTarget = _zoomForBox(box);
      await Promise.all([
        _smoothScrollTo(targetY, 700),
        _animateZoomTo(zoomTarget, 700),
      ]);
      if (stopped) break;
      await new Promise(res => setTimeout(res, 1800));
    }
    await _animateZoomTo({ tx: 0, ty: 0, scale: 1 }, 400);
    _clearTouringMarks();
    clearLit();
    document.body.classList.remove('touring');
    tourBtn.textContent = 'tour';
    tourBtn.classList.remove('on');
    _stopTour = null;
  }
  if (tourBtn) {
    tourBtn.addEventListener('click', () => {
      if (_stopTour) _stopTour();
      else runTour();
    });
  }

  ${editMode ? `
  // ── Claude-edit flow ────────────────────────────────────────────────
  // The legacy claude -p path that backed this modal lived in web-audit's
  // lib/edit.js and was deleted in canvas-engine Phase 6 (2026-04-26). The
  // sitepull daemon's POST /edit now returns 410 Gone. Until the modal is
  // rewired against canvas-engine's SSE /edit (port 3050, sessionId+targetId
  // protocol — not slug+selector+prompt), the submit shows a deprecation
  // notice with a pointer to the new flow rather than firing into the void.
  const SLUG = ${JSON.stringify(opts.slug)};
  const DAEMON = ${JSON.stringify(opts.daemonBase)};
  const CANVAS_ENGINE_URL = 'http://localhost:3050';
  const editModal = document.getElementById('editModal');
  const emRegion = document.getElementById('emRegion');
  const emSelector = document.getElementById('emSelector');
  const emPrompt = document.getElementById('emPrompt');
  const emStatus = document.getElementById('emStatus');
  const emSubmit = document.getElementById('emSubmit');
  const emCancel = document.getElementById('emCancel');
  let currentSelector = null;

  function openEdit(selector, name) {
    currentSelector = selector;
    emRegion.textContent = name;
    emSelector.textContent = selector;
    emPrompt.value = '';
    emStatus.innerHTML = '';
    emStatus.className = 'em-status';
    emSubmit.disabled = false;
    editModal.classList.add('on');
    setTimeout(() => emPrompt.focus(), 30);
  }
  function closeEdit() {
    editModal.classList.remove('on');
    currentSelector = null;
  }
  async function submitEdit() {
    const prompt = emPrompt.value.trim();
    if (!prompt || !currentSelector) return;
    emSubmit.disabled = true;
    // Hard-coded short-circuit: do NOT POST to the deleted /edit endpoint.
    // Surface the migration path so the user understands WHY it does nothing
    // and where to go instead. Removing the button entirely was the other
    // option; we kept it as a visual affordance for the future rewire.
    const link = document.createElement('a');
    link.href = CANVAS_ENGINE_URL + '/sessions';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = 'open canvas-engine sessions';
    emStatus.textContent = 'edit endpoint deprecated · canvas-engine on :3050 took over · ';
    emStatus.appendChild(link);
    emStatus.className = 'em-status error';
    emSubmit.disabled = false;
  }

  document.querySelectorAll('.co-edit').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation(); // don't trigger the callout's hover-light
      openEdit(btn.dataset.selector, btn.dataset.name);
    });
  });
  if (emCancel) emCancel.addEventListener('click', closeEdit);
  if (emSubmit) emSubmit.addEventListener('click', submitEdit);
  if (emPrompt) {
    emPrompt.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeEdit();
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') submitEdit();
    });
  }
  if (editModal) {
    editModal.addEventListener('click', e => {
      if (e.target === editModal) closeEdit(); // click backdrop to dismiss
    });
  }
  ` : ''}
</script>
</body></html>`;
  }

  // Ask the background service worker for a viewport screenshot.
  // Resolves to a PNG dataURL, or null if the capture fails.
  function requestScreenshot() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: 'anatomy:capture' }, (res) => {
          if (chrome.runtime.lastError || !res || !res.ok) {
            resolve(null);
          } else {
            resolve(res.dataUrl);
          }
        });
      } catch (e) {
        resolve(null);
      }
    });
  }

  async function doExportMap() {
    const payload = buildAnatomyV1();
    if (!payload.regions.length) { flash('no labels yet'); return; }

    // If a pull exists for this page, prefer iframe mode (live vendored copy)
    // over screenshot mode. Skips the captureVisibleTab dance entirely in that
    // case — no HUD-hiding, no double-rAF wait.
    const storedPull = await getStoredPull(scopeKey());
    const iframeSrc = storedPull && storedPull.url;

    const viewport = {
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      vw: Math.max(window.innerWidth, 1),
      vh: Math.max(window.innerHeight, 1),
      dpr: window.devicePixelRatio || 1,
    };

    let screenshot = null;
    if (!iframeSrc) {
      // Screenshot path — hide our own UI so HUD / flash / dots don't land inside it.
      const uiEls = Array.from(document.querySelectorAll('.anatomy-root'));
      const prevVis = uiEls.map(el => el.style.visibility);
      uiEls.forEach(el => { el.style.visibility = 'hidden'; });
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      try { screenshot = await requestScreenshot(); }
      finally { uiEls.forEach((el, i) => { el.style.visibility = prevVis[i] || ''; }); }
    }

    const html = generateMapHtml(payload, {
      screenshot, viewport, iframeSrc,
      slug: storedPull && storedPull.slug,
      daemonBase: DAEMON_BASE,
    });
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'anatomy-map-' + scopeKey().replace(/[^a-z0-9]+/gi, '-') + '.html';
    a.click();
    URL.revokeObjectURL(url);
    const mode = iframeSrc ? 'iframe · live' : (screenshot ? 'screenshot' : 'no backdrop');
    flash('map exported · ' + mode);
  }

  function doExport() {
    const payload = buildAnatomyV1();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'anatomy-' + scopeKey().replace(/[^a-z0-9]+/gi, '-') + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  // Accept BOTH shapes: new anatomy-v1 envelope OR legacy {labels:[...]}.
  function doImport() {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'application/json';
    inp.addEventListener('change', () => {
      const f = inp.files[0]; if (!f) return;
      f.text().then(txt => {
        try {
          const data = JSON.parse(txt);
          let arr;
          if (data && data.version === 'anatomy-v1' && Array.isArray(data.regions)) {
            const vocab = (typeof window !== 'undefined' && window.AnatomyDetectionVocab) || null;
            arr = data.regions.map(r => {
              // Migrate stale detection strings to canonical equivalents on import.
              // If the value can't be migrated and isn't recognized, fall back to
              // 'manual' so the region still validates downstream.
              const migrated = vocab ? (vocab.migrateDetection(r.detection) || 'manual') : r.detection;
              return {
                id: r.id,
                label: r.name,
                selector: r.selector,
                ts: Date.now(),
                auto: false,
                kind: r.kind || (vocab ? vocab.inferKindFromGroup(vocab.normalizeDetection({ detection: migrated, kind: r.kind }), migrated) : 'custom'),
                layer: r.layer || 'ui',
                note: r.note || '',
                bounds: r.bounds,
                fetches: Array.isArray(r.fetches) ? r.fetches : [],
                reason: migrated,
              };
            });
          } else {
            arr = (data && data.labels) || [];
          }
          const base = scopeLabels().length;
          arr.forEach((e, i) => scopeLabels().push(normalize(e, base + i)));
          save(); renderTags(); refreshHud();
        } catch (e) { alert('Bad JSON: ' + e.message); }
      });
    });
    inp.click();
  }

  // -------------------------------------------------------------
  // Raw-mode page pull → sitepull daemon (Plan C, v0.3)
  // -------------------------------------------------------------
  // Produces an `anatomy-pull-v1` envelope: {metadata, html, stylesheets[],
  // assets[], anatomy?}. Daemon at `localhost:8088` writes it to a slug under
  // `.canvas/<hostname>/<slug>/` and serves the result at `/c/<slug>/`.
  //
  // Why raw mode is naive on purpose: Plan D will own the heavy serializer.
  // Plan C is the host runtime + the "is the loop even worth building" probe.
  const DAEMON_BASE = 'http://localhost:8088';
  const PULL_VERSION = 'anatomy-pull-v1';
  const MAX_ASSETS_PER_PULL = 200;
  const MAX_TOTAL_PULL_BYTES = 32 * 1024 * 1024; // 32 MB envelope cap

  function pullSlug() {
    // hostname + short hash of pathname + ts. Daemon trusts this only as a hint;
    // it normalizes again server-side.
    const base = location.hostname.replace(/[^a-z0-9.-]+/gi, '-').toLowerCase();
    const path = location.pathname || '/';
    let h = 0;
    for (let i = 0; i < path.length; i++) h = ((h << 5) - h + path.charCodeAt(i)) | 0;
    const hash = (h >>> 0).toString(36).slice(0, 6);
    return `${base}-${hash}-${Date.now().toString(36)}`;
  }

  // Walk document.styleSheets, prefer in-memory cssRules. CORS-blocked
  // sheets throw on .cssRules access — fall back to background-proxy fetch
  // of sheet.href. Inline <style> already lives in the HTML so we skip those.
  async function collectStylesheets() {
    const out = [];
    const sheets = Array.from(document.styleSheets || []);
    for (const sheet of sheets) {
      try {
        if (!sheet.href) continue; // inline <style> already serialized in HTML
        let css = '';
        try {
          const rules = sheet.cssRules;
          if (rules) {
            for (const r of rules) css += r.cssText + '\n';
          }
        } catch (corsErr) {
          // Cross-origin sheet — re-fetch via background SW (extension origin).
          const fetched = await proxyFetch(sheet.href);
          if (fetched && fetched.ok) {
            css = base64ToText(fetched.dataB64);
          }
        }
        if (css) out.push({ href: sheet.href, css });
      } catch (e) {
        // Skip unhealthy sheets; daemon will still get the HTML.
      }
    }
    return out;
  }

  // Decode a base64 payload as UTF-8 text. Background SW returns binary as
  // base64; CSS comes back this way too when it's CORS-fetched.
  function base64ToText(b64) {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return new TextDecoder('utf-8', { fatal: false }).decode(bytes);
    } catch (_) { return ''; }
  }

  // Harvest asset URLs referenced by the live DOM + collected stylesheets.
  // We skip data:/blob:/javascript: schemes, dedupe, cap at MAX_ASSETS_PER_PULL,
  // and resolve everything against location.href so relative URLs survive.
  function harvestAssetUrls(stylesheets) {
    const urls = new Set();
    const push = (u) => {
      if (!u) return;
      try {
        const abs = new URL(u, location.href);
        if (abs.protocol !== 'http:' && abs.protocol !== 'https:') return;
        urls.add(abs.href);
      } catch (_) {}
    };

    document.querySelectorAll('img[src]').forEach(el => push(el.getAttribute('src')));
    document.querySelectorAll('img[srcset]').forEach(el => {
      const set = el.getAttribute('srcset') || '';
      set.split(',').forEach(part => push(part.trim().split(/\s+/)[0]));
    });
    document.querySelectorAll('source[src], source[srcset], video[src], audio[src]').forEach(el => {
      if (el.getAttribute('src')) push(el.getAttribute('src'));
      const set = el.getAttribute('srcset');
      if (set) set.split(',').forEach(part => push(part.trim().split(/\s+/)[0]));
    });
    document.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="manifest"], link[rel="stylesheet"]').forEach(el => push(el.getAttribute('href')));
    document.querySelectorAll('script[src]').forEach(el => push(el.getAttribute('src')));

    // Pull url(...) refs out of inlined / cross-origin stylesheets we already
    // captured. Conservative regex — strips quotes + #fragment.
    const URL_RX = /url\(\s*(['"]?)([^'"\)]+)\1\s*\)/g;
    stylesheets.forEach(sh => {
      let m;
      const cssBase = sh.href || location.href;
      while ((m = URL_RX.exec(sh.css)) !== null) {
        const raw = m[2].split('#')[0].trim();
        if (!raw) continue;
        try { urls.add(new URL(raw, cssBase).href); } catch (_) {}
      }
    });

    // Cap to keep payload manageable. Hot fix list, not a final answer.
    return Array.from(urls).slice(0, MAX_ASSETS_PER_PULL);
  }

  // Asset fetcher · runs in the background SW so we bypass page CORS.
  // Pass credentials='include' for SAME-ORIGIN requests so logged-in pages
  // (Gmail, Linear, Stripe dashboards) capture authenticated assets. Cross-
  // origin requests stay credentials='omit' to avoid leaking the user's
  // session cookies to third-party CDNs the page loads from.
  // FOLLOW-UP · WAF passthrough: extension cannot currently route through
  // sitepull's --via brightdata or --stealth · DataDome-class pulls fail.
  // See triage #8 in tools/codex-partner/runs/TRIAGE-2026-04-26.md.
  function proxyFetch(url) {
    let credentials = 'omit';
    try {
      const target = new URL(url, location.href);
      if (target.origin === location.origin) credentials = 'include';
    } catch (_) {}
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: 'anatomy:fetch', url, credentials }, (res) => {
          if (chrome.runtime.lastError) { resolve(null); return; }
          resolve(res || null);
        });
      } catch (_) { resolve(null); }
    });
  }

  // Issue all asset fetches via the background SW (extension origin = no CORS),
  // bounded by a small concurrency cap so we don't slam the network. Optional
  // progressCb(done, total) lets the caller drive a UI bar while the batch runs.
  async function fetchAssetsBatch(urls, progressCb) {
    const out = [];
    let total = 0;
    let done = 0;
    const CONCURRENCY = 6;
    let cursor = 0;
    async function worker() {
      while (cursor < urls.length) {
        const i = cursor++;
        const u = urls[i];
        const res = await proxyFetch(u);
        done++;
        if (progressCb) try { progressCb(done, urls.length); } catch (_) {}
        if (!res || !res.ok || !res.dataB64) continue;
        if (total + res.byteLength > MAX_TOTAL_PULL_BYTES) return; // bail rest of worker
        total += res.byteLength;
        out.push({
          url: u,
          finalUrl: res.finalUrl || u,
          contentType: res.contentType || '',
          dataB64: res.dataB64,
          byteLength: res.byteLength,
        });
      }
    }
    const workers = Array.from({ length: Math.min(CONCURRENCY, urls.length) }, worker);
    await Promise.all(workers);
    return out;
  }

  // Pre-flight the daemon. Returns {ok, mode, base} or null if down.
  function pingDaemon() {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ type: 'anatomy:daemon-ping', base: DAEMON_BASE }, (res) => {
          if (chrome.runtime.lastError) { resolve(null); return; }
          resolve(res || null);
        });
      } catch (_) { resolve(null); }
    });
  }

  function postIngest(body) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({
          type: 'anatomy:daemon-post',
          base: DAEMON_BASE,
          path: '/ingest',
          body,
        }, (res) => {
          if (chrome.runtime.lastError) { resolve({ ok: false, error: chrome.runtime.lastError.message }); return; }
          resolve(res || { ok: false, error: 'no response' });
        });
      } catch (e) { resolve({ ok: false, error: (e && e.message) || String(e) }); }
    });
  }

  async function doPull(mode) {
    const VALID = ['raw', 'singlefile', 'hybrid'];
    mode = VALID.includes(mode) ? mode : 'raw';
    showProgress('pinging daemon', { detail: 'localhost:8088' });

    const ping = await pingDaemon();
    if (!ping || !ping.ok) {
      showProgress('daemon down · run: sitepull serve', { state: 'error' });
      return;
    }

    const slugHint = pullSlug();
    const metadata = {
      target: location.href,
      hostname: location.hostname,
      pathname: location.pathname,
      title: document.title || '',
      slugHint,
      viewport: {
        scrollX: window.scrollX,
        scrollY: window.scrollY,
        vw: Math.max(window.innerWidth, 1),
        vh: Math.max(window.innerHeight, 1),
        dpr: window.devicePixelRatio || 1,
      },
      timestamp: new Date().toISOString(),
      mode,
      tools: ['anatomy-extension@0.3.15'],
    };

    // SingleFile mode: daemon does all the work via subprocess. We send only
    // {target, mode} and let the daemon spawn `single-file <url> <out>`.
    if (mode === 'singlefile') {
      showProgress('singlefile subprocess', { detail: 'daemon spawning…' });
      const body = { version: PULL_VERSION, metadata, anatomy: maybeAnatomy() };
      const res = await postIngest(body);
      await reportPullResult(res);
      return;
    }

    // Raw mode + Hybrid mode: extension captures DOM/assets, daemon persists.
    // Hybrid additionally spawns singlefile on the daemon side and splices its
    // <style> blocks into the raw DOM.
    showProgress(mode === 'hybrid' ? 'serializing DOM (hybrid leg 1/2)' : 'serializing DOM');

    // SPEC 03: pre-capture canvas pixel buffers. Mutates the live DOM (adds
    // data-precapture-src) so the subsequent serialization picks them up.
    // MUST run before any outerHTML / shadow-DOM serialization step.
    let canvasReport = null;
    try {
      const canvas = window.__anatomyCanvas;
      if (canvas && typeof canvas.precaptureCanvases === 'function') {
        canvasReport = canvas.precaptureCanvases(document);
      }
    } catch (_) { canvasReport = null; }
    if (canvasReport && canvasReport.count > 0) {
      const detail = canvasReport.tainted || canvasReport.oversize
        ? `${canvasReport.count} captured · ${canvasReport.tainted} tainted · ${canvasReport.oversize} oversize`
        : `${canvasReport.count} canvas${canvasReport.count === 1 ? '' : 'es'} snapshotted`;
      showProgress('canvas pre-capture', { detail });
    }

    // SPEC 01 + runtime-inline rehydrator: constructed stylesheets
    // (document.adoptedStyleSheets) and inline <style> tags populated via
    // CSSOM insertRule() (styled-components, emotion) are invisible to
    // outerHTML. Serialize both into <style> tags and splice before </head>.
    let runtimeTags = '';
    let rehydratedCount = 0;
    try {
      const adopted = window.__anatomyAdoptedStyles;
      if (adopted && typeof adopted.serializeAdoptedStyles === 'function') {
        runtimeTags += adopted.serializeAdoptedStyles(document).styleTags || '';
      }
    } catch (_) {}
    try {
      const inline = window.__anatomyInlineStyles;
      if (inline && typeof inline.serializeRuntimeInlineStyles === 'function') {
        const r = inline.serializeRuntimeInlineStyles();
        if (r.styleTags) runtimeTags += (runtimeTags ? '\n' : '') + r.styleTags;
        rehydratedCount = r.rehydratedCount || 0;
      }
    } catch (_) {}

    // SPEC 02: serialize shadow DOM via declarative <template shadowrootmode>
    // tags. Falls back to outerHTML when no open shadow roots exist (fast path
    // is internal to serializeWithShadow). On any error fall through to plain
    // outerHTML so a serializer bug never blocks a pull.
    let serialized = '';
    let shadowCount = 0;
    try {
      const shadow = window.__anatomyShadowDOM;
      if (shadow && typeof shadow.serializeWithShadow === 'function') {
        serialized = shadow.serializeWithShadow(document.documentElement);
        try {
          const all = document.documentElement.querySelectorAll('*');
          for (let i = 0; i < all.length; i++) {
            const sr = all[i].shadowRoot;
            if (sr && sr.mode === 'open') shadowCount++;
          }
        } catch (_) {}
      }
    } catch (_) { serialized = ''; }
    if (!serialized) serialized = document.documentElement.outerHTML;

    let html = '<!doctype html>\n' + serialized;
    if (shadowCount > 0) {
      showProgress('serializing DOM', { detail: `${shadowCount} shadow root${shadowCount === 1 ? '' : 's'} inlined` });
    }
    if (runtimeTags) {
      const m = html.match(/<\/head>/i);
      if (m && typeof m.index === 'number') {
        html = html.slice(0, m.index) + runtimeTags + '\n' + html.slice(m.index);
      } else {
        const b = html.match(/<body[^>]*>/i);
        if (b && typeof b.index === 'number') {
          html = html.slice(0, b.index) + runtimeTags + '\n' + html.slice(b.index);
        } else {
          html = runtimeTags + '\n' + html;
        }
      }
      const hint = rehydratedCount
        ? `adopted + ${rehydratedCount} runtime sheet${rehydratedCount === 1 ? '' : 's'} spliced`
        : 'adopted sheets spliced';
      showProgress('serializing DOM', { detail: hint });
    }

    showProgress('collecting stylesheets');
    const stylesheets = await collectStylesheets();
    showProgress('collecting stylesheets', { detail: `${stylesheets.length} sheet${stylesheets.length === 1 ? '' : 's'}` });

    showProgress('harvesting asset urls');
    const assetUrls = harvestAssetUrls(stylesheets);

    showProgress('fetching assets', { done: 0, total: assetUrls.length });
    const assets = await fetchAssetsBatch(assetUrls, (done, total) => {
      showProgress('fetching assets', { done, total });
    });

    const body = {
      version: PULL_VERSION,
      metadata,
      html,
      stylesheets,
      assets,
      anatomy: maybeAnatomy(),
    };

    showProgress(
      mode === 'hybrid' ? 'uploading + headless chrome (hybrid leg 2/2)' : 'uploading to daemon',
      { detail: mode === 'hybrid' ? 'POST /ingest · ~10s' : 'POST /ingest' }
    );
    const res = await postIngest(body);
    await reportPullResult(res);
  }

  // Attach the current anatomy-v1 envelope only if the user has labels on the
  // page. Empty envelope clutters the daemon directory for no payoff.
  function maybeAnatomy() {
    const labels = scopeLabels();
    if (!labels.length) return null;
    return buildAnatomyV1();
  }

  // Storage key for "what slug is the latest pull for THIS page (scopeKey)?".
  // Lets `make map` switch from screenshot backdrop to live iframe automatically
  // after a pull has happened, without requiring a separate user gesture.
  const PULLS_STORAGE_KEY = 'anatomy.pulls.v1';

  function getStoredPull(scope) {
    return new Promise((resolve) => {
      try {
        chrome.storage.local.get([PULLS_STORAGE_KEY], (r) => {
          const map = (r && r[PULLS_STORAGE_KEY]) || {};
          resolve(map[scope] || null);
        });
      } catch (_) { resolve(null); }
    });
  }

  function setStoredPull(scope, pull) {
    return new Promise((resolve) => {
      try {
        chrome.storage.local.get([PULLS_STORAGE_KEY], (r) => {
          const map = (r && r[PULLS_STORAGE_KEY]) || {};
          map[scope] = pull;
          chrome.storage.local.set({ [PULLS_STORAGE_KEY]: map }, () => resolve());
        });
      } catch (_) { resolve(); }
    });
  }

  async function reportPullResult(res) {
    if (!res || !res.ok) {
      const b = (res && res.body) || {};
      const why = b.detail || b.error || (res && res.error) || 'unknown error';
      const status = res && typeof res.status === 'number' ? `HTTP ${res.status} · ` : '';
      showProgress('pull failed', { state: 'error', detail: status + String(why).slice(0, 140) });
      console.error('[anatomy] pull failed:', res);
      return;
    }
    const r = res.body || {};
    const url = r.url || (r.slug ? `${DAEMON_BASE}/c/${r.slug}/` : null);
    const detail = `${r.slug || 'ok'} · ${r.stats && r.stats.bytes ? r.stats.bytes.toLocaleString() + ' bytes' : ''}`;
    showProgress('pulled', { state: 'done', detail });
    console.log('[anatomy] pull ok:', r);

    if (r.slug) {
      await setStoredPull(scopeKey(), {
        slug: r.slug,
        url,
        target: location.href,
        mode: r.mode || '',
        bytes: (r.stats && r.stats.bytes) || 0,
        pulledAt: new Date().toISOString(),
      });
    }
    if (url) {
      try { window.open(url, '_blank', 'noopener'); } catch (_) {}
    }
  }

  // -------------------------------------------------------------
  // Auto-label (heuristic DOM scanner) — heavy edition
  // -------------------------------------------------------------
  const LANDMARK_TAGS = ['header', 'nav', 'main', 'aside', 'footer', 'section', 'form'];
  const DIALOG_TAGS = ['dialog'];
  const INTERACTIVE_TAGS = ['button', 'a', 'input', 'select', 'textarea'];
  const HEADING_TAGS = ['h1', 'h2', 'h3'];
  const MAX_LABELS = 1000;
  const MIN_AREA = 220; // px²
  // REPEAT_KEEP: cap on how many "same-label, same-parent-pattern" candidates
  // survive dedupe. 3 was too aggressive for content-heavy sites (HN had 100+
  // story rows collapsing to 3). 20 keeps real repetition visible while still
  // trimming pure noise (e.g. 50 identical "login" buttons from a broken scan).
  const REPEAT_KEEP = 20;

  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    const r = el.getBoundingClientRect();
    if (r.width * r.height < MIN_AREA) return false;
    if (r.bottom < 0 || r.top > (document.documentElement.scrollHeight + 1000)) return false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
    return true;
  }

  function shortText(s, n = 36) {
    s = (s || '').replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }

  function classHint(el) {
    // Pull semantic words from class names, ignoring utility/hash classes.
    const c = el.getAttribute('class') || '';
    const words = c.split(/[\s_-]+/)
      .map(w => w.toLowerCase())
      .filter(w => /^[a-z][a-z]{2,}$/.test(w))                // alpha only, 3+ chars
      .filter(w => !/^(is|has|css|sc|tw|sm|md|lg|xl|btn|wrapper|container|inner|outer|root|item|el|ui|app|main|content|block|inline|flex|grid|row|col|gap|p[xy]?|m[xy]?|w|h|bg|fg|text|font|border|rounded|shadow)$/.test(w))
      .filter(w => !/^[a-f0-9]{4,}$/.test(w));                // skip hex hashes
    return words[0] || null;
  }

  function svgHint(el) {
    // Icon-only buttons: try the SVG title, aria-label on the svg, data-icon.
    const svg = el.querySelector('svg');
    if (!svg) return null;
    const title = svg.querySelector('title');
    if (title && title.textContent.trim()) return shortText(title.textContent);
    const aria = svg.getAttribute('aria-label');
    if (aria) return shortText(aria);
    const dataIcon = svg.getAttribute('data-icon') || svg.getAttribute('data-name');
    if (dataIcon) return shortText(dataIcon);
    const iconClass = (svg.getAttribute('class') || '').match(/icon[-_]?([a-z]+)/i);
    if (iconClass) return shortText(iconClass[1]);
    return null;
  }

  function imgHint(el) {
    const img = el.querySelector('img');
    if (img && img.getAttribute('alt')) return shortText(img.getAttribute('alt'));
    return null;
  }

  function isClickyDiv(el) {
    if (INTERACTIVE_TAGS.includes(el.tagName.toLowerCase())) return false;
    if (el.hasAttribute('role')) return true;
    if (el.hasAttribute('onclick')) return true;
    if (el.hasAttribute('tabindex') && el.getAttribute('tabindex') !== '-1') return true;
    const cs = getComputedStyle(el);
    if (cs.cursor === 'pointer') return true;
    return false;
  }

  function isCard(el) {
    // Visually boxed container that's not a landmark.
    const tag = el.tagName.toLowerCase();
    if (LANDMARK_TAGS.includes(tag) || INTERACTIVE_TAGS.includes(tag)) return false;
    const cs = getComputedStyle(el);
    const hasBorder = parseFloat(cs.borderTopWidth) >= 1 || parseFloat(cs.borderLeftWidth) >= 1;
    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
    const hasBg = cs.backgroundColor && cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent';
    const hasRadius = parseFloat(cs.borderRadius) > 2;
    const score = (hasBorder ? 1 : 0) + (hasShadow ? 1 : 0) + (hasBg ? 1 : 0) + (hasRadius ? 1 : 0);
    if (score < 2) return false;
    // Must hold actual content, not be a wrapper around 1 child
    if (el.children.length < 2 && (el.textContent || '').trim().length < 20) return false;
    const r = el.getBoundingClientRect();
    if (r.width * r.height < 4000) return false;
    return true;
  }

  function isCustomElement(el) {
    return el.tagName.includes('-') || el.tagName.startsWith('X-') ;
  }

  function deriveLabel(el) {
    const aria = el.getAttribute('aria-label');
    if (aria) return shortText(aria);
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const ref = document.getElementById(labelledBy);
      if (ref) return shortText(ref.textContent);
    }
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-cy');
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role');

    if (tag === 'input') {
      const ph = el.getAttribute('placeholder');
      if (ph) return shortText(ph);
      const type = el.getAttribute('type') || 'text';
      const name = el.getAttribute('name') || testId;
      return shortText(`${type} input${name ? ' · ' + name : ''}`);
    }
    if (tag === 'select')   return shortText('select · ' + (el.getAttribute('name') || el.id || testId || 'options'));
    if (tag === 'textarea') return shortText('textarea · ' + (el.getAttribute('placeholder') || el.getAttribute('name') || testId || ''));

    if (tag === 'a' || tag === 'button' || isClickyDiv(el)) {
      const txt = (el.innerText || el.textContent || '').trim();
      if (txt) return shortText(txt);
      const svg = svgHint(el);
      if (svg) return shortText((tag === 'a' ? 'link' : 'btn') + ' · ' + svg);
      const img = imgHint(el);
      if (img) return shortText((tag === 'a' ? 'link' : 'btn') + ' · ' + img);
      const title = el.getAttribute('title');
      if (title) return shortText(title);
      if (testId) return shortText(testId);
      const cls = classHint(el);
      if (cls) return shortText((role || (tag === 'a' ? 'link' : 'btn')) + ' · ' + cls);
      return role || (tag === 'a' ? 'link' : 'button');
    }

    if (HEADING_TAGS.includes(tag)) {
      return shortText(el.textContent) || tag.toUpperCase();
    }
    if (LANDMARK_TAGS.includes(tag)) {
      const name = aria || el.id;
      return shortText(`${tag}${role ? ' · ' + role : ''}${name ? ' · ' + name : ''}`);
    }
    if (DIALOG_TAGS.includes(tag) || role === 'dialog') {
      const name = aria || (el.querySelector('h1,h2,h3') || {}).textContent;
      return shortText('dialog' + (name ? ' · ' + name.trim() : ''));
    }
    if (isCustomElement(el)) {
      return shortText('custom · ' + tag);
    }
    if (isCard(el)) {
      const heading = el.querySelector('h1, h2, h3, h4, [role="heading"]');
      if (heading && heading.textContent.trim()) return shortText('card · ' + heading.textContent.trim());
      const cls = classHint(el);
      if (cls) return shortText('card · ' + cls);
      if (testId) return shortText('card · ' + testId);
      return 'card';
    }
    if (role) return shortText(role + (testId ? ' · ' + testId : ''));
    return null;
  }

  function classString(el) {
    if (!el) return '';
    const c = el.className;
    if (typeof c === 'string') return c;
    if (c && typeof c.baseVal === 'string') return c.baseVal; // SVGAnimatedString
    return '';
  }

  function parentKeyOf(el) {
    const parent = el.parentElement;
    if (!parent) return '';
    return parent.tagName + '.' + classString(parent).slice(0, 40);
  }

  // Reject only labels that carry NO information beyond the element's tag.
  // Bare "button" / "link" / "tab" / "presentation" + hash-class fallbacks.
  function isJunkLabel(label) {
    if (!label) return true;
    const t = label.trim().toLowerCase();
    if (/^(button|link|btn|nav|menu|tab|presentation|item|el|div|span|none)$/.test(t)) return true;
    // "btn · gbii", "link · xkdj" — suffix is a hashy class fragment (no vowels, short)
    const parts = t.split('·').map(s => s.trim());
    if (parts.length === 2 && /^(btn|link|btn|role)$/.test(parts[0])) {
      const suffix = parts[1].replace(/\s+\d+$/, ''); // strip trailing repeat counter
      if (/^[a-z0-9]{2,8}$/.test(suffix) && !/[aeiou]/.test(suffix)) return true;
    }
    return false;
  }

  function gatherCandidatesLegacy() {
    const existing = new Set(scopeLabels().map(e => e.selector));
    const out = [];
    const all = document.querySelectorAll('*');
    all.forEach(el => {
      try {
        if (el.closest('.anatomy-root')) return;
        const tag = el.tagName.toLowerCase();
        const isSem = LANDMARK_TAGS.includes(tag) || HEADING_TAGS.includes(tag) || DIALOG_TAGS.includes(tag) || INTERACTIVE_TAGS.includes(tag);
        const isClicky = !isSem && isClickyDiv(el);
        const isCustom = !isSem && !isClicky && isCustomElement(el);
        const isCardy = !isSem && !isClicky && !isCustom && isCard(el);
        if (!isSem && !isClicky && !isCustom && !isCardy) return;
        if (!isVisible(el)) return;
        const sel = buildSelector(el);
        if (!sel || existing.has(sel)) return;
        const label = deriveLabel(el);
        if (isJunkLabel(label)) return;
        out.push({ el, sel, label, kind: isSem ? 'sem' : isClicky ? 'click' : isCustom ? 'custom' : 'card', reason: 'legacy' });
      } catch (err) {
        // skip unhealthy elements (shadow DOM hosts, broken nodes)
      }
    });
    return out;
  }

  // -------------------------------------------------------------
  // v0.2 cascade — ported from browser-use clickable_elements.py
  // See _research/AUDIT_FINDINGS.md §Repo 2 for rule→verdict table.
  // -------------------------------------------------------------
  const ARIA_INTERACTIVE_ROLES = new Set([
    'button','link','menuitem','menuitemcheckbox','menuitemradio','option',
    'radio','checkbox','tab','textbox','combobox','slider','spinbutton',
    'searchbox','gridcell','switch','treeitem',
  ]);
  const FORM_CONTROL_TAGS = new Set(['input', 'select', 'textarea', 'button']);
  const SEARCH_INDICATOR_RX = /(^|[-_])(search|filter|query|lookup|autocomplete|combobox|typeahead)($|[-_])/i;
  const INLINE_EVENT_ATTRS = [
    'onclick','onmousedown','onmouseup','onkeydown','onkeyup','onkeypress',
    'onchange','oninput','onsubmit','onfocus','onblur','ontouchstart','onpointerdown',
  ];

  // WeakMap cache for is_clickable per element (browser-use enhanced_snapshot.py:91 pattern)
  let clickableCache = new WeakMap();

  function hasFormControlDescendant(el, depth) {
    if (depth <= 0 || !el) return false;
    for (const child of el.children) {
      if (FORM_CONTROL_TAGS.has(child.tagName.toLowerCase())) return true;
      if (hasFormControlDescendant(child, depth - 1)) return true;
    }
    return false;
  }

  function hasInlineEventAttr(el) {
    for (const a of INLINE_EVENT_ATTRS) if (el.hasAttribute(a)) return true;
    return false;
  }

  function isAncestor(maybeAnc, el) {
    let p = el && el.parentElement;
    while (p) { if (p === maybeAnc) return true; p = p.parentElement; }
    return false;
  }

  function isDescendant(maybeDesc, el) {
    return el && maybeDesc && el !== maybeDesc && el.contains(maybeDesc);
  }

  // Occlusion check (v0.3.5) — hybrid box-overlap + pixel-sample.
  //
  // Why hybrid: pixel sampling via elementsFromPoint only works for coordinates
  // inside the current viewport — below-fold candidates can't be pixel-checked
  // without scrolling. Box-overlap math works anywhere on the page, is 10×
  // faster, and catches the 90% case (fixed/sticky/absolute overlays). For
  // in-viewport candidates we still run pixel sampling as a second opinion —
  // it catches CSS edge cases (clip-path, mix-blend, transforms) that pure
  // geometry misses.
  //
  // Strategy:
  //   1. Cache a list of "occluder" elements per scan — those likely to hide
  //      other elements (position:fixed/sticky/absolute/relative with z-index
  //      and opaque bg). ~50 per page; built once per gatherCandidates run.
  //   2. For each candidate, test box-intersection against the occluder set.
  //      If >50% of the candidate's area is covered by a single occluder that's
  //      neither ancestor nor descendant → mark covered.
  //   3. If box-overlap is ambiguous (covered, but maybe by a transparent
  //      layer) AND candidate is in viewport → run pixel-sample to confirm.

  let occluderCache = null; // reset per gatherCandidates call
  function getOccluders() {
    if (occluderCache) return occluderCache;
    const out = [];
    const all = document.querySelectorAll('*');
    all.forEach(el => {
      try {
        if (el.closest('.anatomy-root')) return;
        const cs = getComputedStyle(el);
        const pos = cs.position;
        // Normal-flow elements rarely occlude other candidates directly —
        // when they do, it's usually via positive z-index + transform/opacity.
        if (pos !== 'fixed' && pos !== 'sticky' && pos !== 'absolute') return;
        const op = parseFloat(cs.opacity || '1');
        if (op < 0.8) return;
        const bg = cs.backgroundColor || '';
        const opaqueBg = bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
        const hasImgBg = cs.backgroundImage && cs.backgroundImage !== 'none';
        if (!opaqueBg && !hasImgBg) return;
        const r = el.getBoundingClientRect();
        // Ignore tiny occluders (dots, accents, icons) — they don't hide labels.
        if (r.width < 24 || r.height < 24) return;
        out.push({ el, r });
      } catch (_) { /* skip unhealthy nodes */ }
    });
    occluderCache = out;
    return out;
  }

  function isInViewport(r) {
    return r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth;
  }

  // Box-overlap primary check. Returns:
  //   'clear'      → no significant overlap
  //   'covered'    → ≥50% covered by a larger opaque occluder
  //   'maybe'      → significant overlap but worth double-checking with pixels
  function isCoveredByBoxOverlap(el, r) {
    const elArea = r.width * r.height;
    if (elArea <= 0) return 'clear';
    for (const { el: occ, r: or } of getOccluders()) {
      if (occ === el || isAncestor(occ, el) || isDescendant(occ, el)) continue;
      if (or.right <= r.left || or.left >= r.right || or.bottom <= r.top || or.top >= r.bottom) continue;
      const ox = Math.max(0, Math.min(or.right, r.right) - Math.max(or.left, r.left));
      const oy = Math.max(0, Math.min(or.bottom, r.bottom) - Math.max(or.top, r.top));
      const overlapArea = ox * oy;
      const frac = overlapArea / elArea;
      if (frac >= 0.5) return 'covered';
      if (frac >= 0.25) return 'maybe';
    }
    return 'clear';
  }

  // Pixel-sampling confirmation (runs only for in-viewport candidates).
  // Same 5-point probe logic as pre-0.3.5 — kept for CSS edge cases that
  // box math doesn't catch (clip-path, transform, mix-blend).
  function isCoveredByPixelSample(el, r) {
    if (r.width < 6 || r.height < 6) return false;
    const points = [
      [r.left + r.width * 0.5,  r.top + r.height * 0.5],
      [r.left + r.width * 0.25, r.top + r.height * 0.25],
      [r.left + r.width * 0.75, r.top + r.height * 0.25],
      [r.left + r.width * 0.25, r.top + r.height * 0.75],
      [r.left + r.width * 0.75, r.top + r.height * 0.75],
    ];
    let coveredCount = 0;
    let sampledCount = 0;
    for (const [x, y] of points) {
      if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) continue;
      sampledCount++;
      let stack;
      try { stack = document.elementsFromPoint(x, y); } catch (_) { continue; }
      if (!stack || !stack.length) continue;
      const top = stack[0];
      if (top === el || isAncestor(top, el) || isDescendant(top, el)) continue;
      const cs = getComputedStyle(top);
      const op = parseFloat(cs.opacity || '1');
      const bg = cs.backgroundColor || '';
      const opaqueBg = bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent';
      if (op >= 0.8 && opaqueBg) coveredCount++;
    }
    // Need at least 3 of the sampled points covered. If fewer than 3 sampled
    // (tiny in-viewport slice), don't reject on that evidence alone.
    return sampledCount >= 3 && coveredCount >= 3;
  }

  function isCovered(el) {
    const r = el.getBoundingClientRect();
    if (r.width < 6 || r.height < 6) return false;
    const verdict = isCoveredByBoxOverlap(el, r);
    if (verdict === 'covered') return true;
    if (verdict === 'clear')   return false;
    // 'maybe' — overlap exists but <50%. If in viewport, confirm with pixels.
    if (!isInViewport(r)) return false;
    return isCoveredByPixelSample(el, r);
  }

  // Run the rule cascade, short-circuiting on first match. Returns a rule id or null.
  function classifyClickable(el) {
    if (clickableCache.has(el)) return clickableCache.get(el);
    const tag = el.tagName.toLowerCase();
    let reason = null;

    // r2 — large iframe
    if (tag === 'iframe') {
      const r = el.getBoundingClientRect();
      if (r.width > 100 && r.height > 100) reason = 'r2-large-iframe';
    }
    // r3 — <label> with form-control descendant (depth ≤ 2), skip `for=` proxies
    if (!reason && tag === 'label' && !el.hasAttribute('for') && hasFormControlDescendant(el, 2)) {
      reason = 'r3-label-with-control';
    }
    // r4 — <span> with form-control descendant
    if (!reason && tag === 'span' && hasFormControlDescendant(el, 2)) {
      reason = 'r4-span-with-control';
    }
    // r5 — search indicator in class / id / data-*
    if (!reason) {
      const attrs = `${el.id || ''} ${classString(el) || ''} ${el.getAttribute('data-testid') || ''} ${el.getAttribute('data-role') || ''}`;
      if (SEARCH_INDICATOR_RX.test(attrs)) reason = 'r5-search-indicator';
    }
    // r7 — native interactive tag
    if (!reason && INTERACTIVE_TAGS.includes(tag)) reason = 'r7-native-interactive';
    // r8 — inline event attrs or tabindex ≥ 0
    if (!reason) {
      const ti = el.getAttribute('tabindex');
      if (hasInlineEventAttr(el) || (ti != null && +ti >= 0)) reason = 'r8-event-handler-attrs';
    }
    // r9 — interactive ARIA role
    if (!reason) {
      const role = (el.getAttribute('role') || '').toLowerCase();
      if (role && ARIA_INTERACTIVE_ROLES.has(role)) reason = 'r9-aria-role';
    }
    // r11 — icon-sized (10–50px) + interactive attrs
    if (!reason) {
      const r = el.getBoundingClientRect();
      const minSide = Math.min(r.width, r.height);
      if (minSide >= 10 && minSide <= 50 && (hasInlineEventAttr(el) || el.hasAttribute('role') || el.hasAttribute('tabindex'))) {
        reason = 'r11-icon-sized-interactive';
      }
    }
    // r12 — cursor:pointer AND pointer-events !== 'none' (Codex correction)
    if (!reason) {
      const cs = getComputedStyle(el);
      if (cs.cursor === 'pointer' && cs.pointerEvents !== 'none') reason = 'r12-cursor-pointer';
    }

    clickableCache.set(el, reason);
    return reason;
  }

  // ── Pattern detection (v0.3.11) ────────────────────────────────────
  // On content-heavy pages (apify store, HN, reddit, twitter, github search),
  // exhaustive labeling drowns the user in 200 dots. Instead: find containers
  // whose children repeat a structural pattern (≥5 siblings with same tag +
  // class signature), emit ONE label for the container ("N items"), keep 2
  // exemplar children for the user to alt+click into, skip the rest.
  //
  // Structural signature: tag + sorted meaningful classes (drop hash fragments,
  // utility classes). Rough but works for most component-based UIs.
  function structSig(el) {
    if (!el || !el.tagName) return '';
    const raw = classString(el).split(/\s+/).filter(Boolean);
    const keep = raw.filter(c =>
      // skip utility / hash-looking classes that vary per instance
      !/^([a-f0-9]{4,}|[a-z0-9]{1,3}|[wm]-\d|p[xy]?-\d|m[xy]?-\d)$/i.test(c)
    );
    return el.tagName + '.' + keep.sort().join(' ').slice(0, 80);
  }

  function findRepeatContainers() {
    const result = new WeakMap(); // parent element → { count, sig, exemplarSet }
    const all = document.querySelectorAll('*');
    all.forEach(parent => {
      try {
        if (parent.closest && parent.closest('.anatomy-root')) return;
        const kids = Array.from(parent.children);
        if (kids.length < 5) return;
        // Group siblings by structural signature.
        const byS = new Map();
        for (const k of kids) {
          const s = structSig(k);
          if (!byS.has(s)) byS.set(s, []);
          byS.get(s).push(k);
        }
        let dominant = null;
        for (const list of byS.values()) {
          if (!dominant || list.length > dominant.length) dominant = list;
        }
        if (!dominant) return;
        // Require ≥5 matches AND dominant fraction ≥60% of visible kids.
        if (dominant.length < 5) return;
        if (dominant.length < kids.length * 0.6) return;
        // Adaptive exemplar cap (v0.4.3 · fix C). Small groups label everything;
        // medium groups keep 5; large groups keep 2 (original behavior).
        // <10  → label all individually, no summary container (return early)
        // 10-30 → keep 5 exemplars + summary
        // >30  → keep 2 exemplars + summary
        let keepCount;
        if (dominant.length < 10) {
          return; // small enough · let every sibling get its own label, no collapse
        } else if (dominant.length <= 30) {
          keepCount = 5;
        } else {
          keepCount = 2;
        }
        const exemplarSet = new Set(dominant.slice(0, keepCount));
        const skipSet = new Set(dominant.slice(keepCount));
        result.set(parent, { count: dominant.length, exemplarSet, skipSet, sig: structSig(dominant[0]) });
      } catch (_) { /* skip unhealthy nodes */ }
    });
    return result;
  }

  function gatherCandidatesV2() {
    clickableCache = new WeakMap(); // fresh cache per run
    occluderCache = null;           // rebuild occluder list per run (layout can have changed)
    const repeats = state.patternsOn ? findRepeatContainers() : new WeakMap();
    // Union of all descendant elements inside a repeat container (beyond the 2
    // exemplars). Those candidates get dropped from the main pass.
    const skipBecauseOfPattern = new WeakSet();
    const repeatContainerList = []; // [el, desc] pairs for emitting list candidates
    const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_ELEMENT);
    while (walker.nextNode()) {
      const el = walker.currentNode;
      const desc = repeats.get(el);
      if (!desc) continue;
      repeatContainerList.push([el, desc]);
      // Walk subtree of each skipped sibling, mark all their descendants.
      for (const skipKid of desc.skipSet) {
        skipBecauseOfPattern.add(skipKid);
        const sub = skipKid.querySelectorAll('*');
        for (const s of sub) skipBecauseOfPattern.add(s);
      }
    }

    // Per-stage dropout counters · diagnoses where labelable elements vanish.
    // Logged once at end of scrolled-scan via state._dropCounters.
    const drop = state._dropCounters = state._dropCounters || {
      total: 0, anatomyRoot: 0, patternRepeat: 0, noReason: 0,
      notVisible: 0, isCovered: 0, noSelector: 0, dupSelector: 0,
      junkLabel: 0, kept: 0,
    };

    const existing = new Set(scopeLabels().map(e => e.selector));
    const out = [];
    const all = document.querySelectorAll('*');
    all.forEach(el => {
      try {
        drop.total++;
        if (el.closest('.anatomy-root')) { drop.anatomyRoot++; return; }
        // Pattern skip — element is inside a repeat container, beyond the first 2 exemplars.
        if (skipBecauseOfPattern.has(el)) { drop.patternRepeat++; return; }
        const tag = el.tagName.toLowerCase();

        // Semantic tags still get labeled regardless of cascade (landmarks, headings, dialogs).
        const isSem = LANDMARK_TAGS.includes(tag) || HEADING_TAGS.includes(tag) || DIALOG_TAGS.includes(tag) || INTERACTIVE_TAGS.includes(tag);
        const isCustom = !isSem && isCustomElement(el);
        const isCardy = !isSem && !isCustom && isCard(el);

        let reason = null;
        let kind = null;
        if (isSem) {
          reason = INTERACTIVE_TAGS.includes(tag) ? 'r7-native-interactive' : `sem-${tag}`;
          kind = 'sem';
        } else {
          reason = classifyClickable(el);
          if (reason) kind = 'click';
          else if (isCustom) { reason = 'custom-element'; kind = 'custom'; }
          else if (isCardy) { reason = 'card-heuristic'; kind = 'card'; }
        }
        if (!reason) { drop.noReason++; return; }
        if (!isVisible(el)) { drop.notVisible++; return; }
        if (isCovered(el)) { drop.isCovered++; return; }

        const sel = buildSelector(el);
        if (!sel) { drop.noSelector++; return; }
        if (existing.has(sel)) { drop.dupSelector++; return; }
        const label = deriveLabel(el);
        if (isJunkLabel(label)) { drop.junkLabel++; return; }
        drop.kept++;
        out.push({ el, sel, label, kind, reason });
      } catch (err) {
        // skip unhealthy nodes (shadow hosts, broken refs)
      }
    });

    // Emit one "list" candidate per repeat container. Label describes what we
    // collapsed so the user knows there's a pattern here and can alt+click an
    // exemplar if they want to target one specifically.
    for (const [container, desc] of repeatContainerList) {
      try {
        if (container.closest('.anatomy-root')) continue;
        if (!isVisible(container)) continue;
        const sel = buildSelector(container);
        if (!sel || existing.has(sel)) continue;
        const childTag = desc.sig.split('.')[0].toLowerCase();
        const label = shortText(`list · ${desc.count}× ${childTag}`, 40);
        out.push({ el: container, sel, label, kind: 'list', reason: 'pattern-repeat' });
      } catch (_) {}
    }

    return out;
  }

  function gatherCandidates() {
    return state.rulesVersion === 'legacy' ? gatherCandidatesLegacy() : gatherCandidatesV2();
  }

  // Scroll through the page in viewport increments, gathering candidates at each
  // stop. Required because the v2 cascade calls isCovered() which relies on
  // document.elementsFromPoint() — that only returns elements at coordinates
  // inside the current viewport. Below-the-fold candidates pass the "covered"
  // check trivially (sample points fall outside innerHeight, loop continues, so
  // coveredCount stays 0). That sounds harmless but means tall pages never get
  // a TRUE occlusion check on the bottom 80%, which sometimes lets covered
  // elements through AND sometimes filters real ones via downstream interactions.
  // Scrolling guarantees every candidate is sampled in-viewport at least once.
  //
  // v0.3.7 progressive commit: onStep(newCandidates, stepIdx, totalSteps) is
  // called after each scroll stop with the candidates newly seen in that batch.
  // Lets callers (doAutoLabel) commit labels incrementally so the HUD list and
  // page dots populate live instead of jumping from 0 → N at the end.
  async function gatherCandidatesScrolled(onStep) {
    const original = { x: window.scrollX, y: window.scrollY };
    const docH = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight, window.innerHeight);
    const step = Math.max(Math.floor(window.innerHeight * 0.85), 200);
    const totalSteps = Math.max(1, Math.ceil(docH / step));
    const seen = new Map(); // selector -> candidate (first wins, preserves order)

    // Reset per-stage drop counters at run start so each scrolled-scan reports
    // fresh numbers. Counters accumulate across all gatherCandidatesV2 calls
    // (one per scroll stop) and get logged at end of the scan.
    state._dropCounters = {
      total: 0, anatomyRoot: 0, patternRepeat: 0, noReason: 0,
      notVisible: 0, isCovered: 0, noSelector: 0, dupSelector: 0,
      junkLabel: 0, kept: 0,
    };

    let stops = 0;
    try {
      for (let y = 0; y < docH; y += step) {
        window.scrollTo({ top: y, left: 0, behavior: 'instant' });
        // Give layout + lazy-loaded content a beat to settle. Double-rAF +
        // a small timeout handles sites that swap content on scroll (lazy
        // mount triggered by IntersectionObserver). Hidden tabs throttle rAF
        // to ~1Hz, so skip the rAF wait when not visible — setTimeout still
        // works (clamped to ~1s in background but doesn't deadlock).
        if (document.visibilityState === 'visible') {
          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        }
        await new Promise(r => setTimeout(r, 40));
        // Occluder positions (esp. sticky headers) change per scroll — rebuild.
        occluderCache = null;
        const batch = gatherCandidates();
        const freshThisStep = [];
        for (const c of batch) {
          if (!c.sel || seen.has(c.sel)) continue;
          seen.set(c.sel, c);
          freshThisStep.push(c);
        }
        stops++;
        if (onStep && freshThisStep.length) {
          try { await onStep(freshThisStep, stops, totalSteps); } catch (e) { console.warn('[anatomy] onStep error (non-fatal):', e); }
        }
      }
    } finally {
      window.scrollTo({ top: original.y, left: original.x, behavior: 'instant' });
    }
    console.log(`[anatomy] scrolled-scan · docH=${docH} innerH=${window.innerHeight} step=${step} stops=${stops} seen=${seen.size}`);
    if (state._dropCounters) {
      console.log('[anatomy] dropout-by-stage:', JSON.stringify(state._dropCounters));
    }

    return Array.from(seen.values());
  }

  function dedupe(candidates) {
    // Pre-compute parent keys ONCE so we can total-count without O(n²) errors.
    const keys = new Map(); // candidate -> key
    const totals = new Map(); // key -> count
    candidates.forEach(c => {
      const k = c.label + '|' + parentKeyOf(c.el);
      keys.set(c, k);
      totals.set(k, (totals.get(k) || 0) + 1);
    });
    const counts = new Map();
    const out = [];
    candidates.forEach(c => {
      const k = keys.get(c);
      const n = counts.get(k) || 0;
      if (n >= REPEAT_KEEP) return;
      counts.set(k, n + 1);
      const total = totals.get(k) || 1;
      const labeled = total > REPEAT_KEEP
        ? `${c.label} · ${n + 1}/${total}`
        : (total > 1 ? `${c.label} · ${n + 1}` : c.label);
      out.push({ ...c, label: labeled });
    });
    return out;
  }

  function avoidDescendantDoubles(items) {
    // If we labeled a parent, skip a descendant with the same label.
    const taken = new Set();
    const out = [];
    items.forEach(it => {
      let p = it.el.parentElement;
      let nestedSkip = false;
      while (p) {
        if (taken.has(p)) { nestedSkip = true; break; }
        p = p.parentElement;
      }
      if (nestedSkip && it.kind !== 'click') return;
      taken.add(it.el);
      out.push(it);
    });
    return out;
  }

  // ── Watch-me labeling ──────────────────────────────────────────────
  // Records cursor positions while user browses naturally. On stop, runs
  // the dwell-detection algo (lifted from openscreen/zoomSuggestionUtils.ts:
  // a "dwell" = 450-2600ms of cursor staying within 0.02 normalized distance).
  // Each dwell point becomes a label at the DOM element under that cursor.
  const WATCH_MIN_DWELL_MS = 450;
  const WATCH_MAX_DWELL_MS = 2600;
  const WATCH_MOVE_THRESHOLD = 0.02; // normalized to viewport diagonal
  let _watchActive = false;
  let _watchSamples = [];
  let _watchSampleHandler = null;
  let _watchLastSampleTs = 0;

  function _detectDwellRuns(samples, vw, vh) {
    if (samples.length < 2) return [];
    const diag = Math.hypot(vw, vh) || 1;
    const dwells = [];
    let runStart = 0;
    function flushIfDwell(startIdx, endIdxExcl) {
      if (endIdxExcl - startIdx < 2) return;
      const a = samples[startIdx], b = samples[endIdxExcl - 1];
      const dur = b.t - a.t;
      if (dur < WATCH_MIN_DWELL_MS || dur > WATCH_MAX_DWELL_MS) return;
      const slice = samples.slice(startIdx, endIdxExcl);
      const ax = slice.reduce((s, p) => s + p.x, 0) / slice.length;
      const ay = slice.reduce((s, p) => s + p.y, 0) / slice.length;
      dwells.push({ x: Math.round(ax), y: Math.round(ay), durationMs: dur });
    }
    for (let i = 1; i < samples.length; i++) {
      const prev = samples[i - 1], cur = samples[i];
      const dist = Math.hypot(cur.x - prev.x, cur.y - prev.y) / diag;
      if (dist > WATCH_MOVE_THRESHOLD) {
        flushIfDwell(runStart, i);
        runStart = i;
      }
    }
    flushIfDwell(runStart, samples.length);
    return dwells;
  }

  async function toggleWatchMe(btn) {
    if (_watchActive) {
      // Stop and process.
      _watchActive = false;
      if (_watchSampleHandler) {
        document.removeEventListener('mousemove', _watchSampleHandler, true);
        _watchSampleHandler = null;
      }
      btn.textContent = 'watch me';
      btn.classList.remove('on');
      const samples = _watchSamples.slice();
      _watchSamples = [];
      if (samples.length < 4) {
        flash('watch · too few samples · move the cursor next time');
        return;
      }
      const dwells = _detectDwellRuns(samples, window.innerWidth, window.innerHeight);
      if (!dwells.length) {
        flash('watch · no dwell points found');
        return;
      }
      // Convert each dwell point into a label.
      const before = scopeLabels().length;
      const existingSelectors = new Set(scopeLabels().map(e => e.selector));
      let added = 0;
      for (const d of dwells) {
        const el = document.elementFromPoint(d.x, d.y);
        if (!el) continue;
        const target = (typeof isJunkLabel === 'function' && el.tagName.match(/^(SPAN|EM|STRONG|I|B|U)$/i))
          ? (el.closest('a, button, [role], section, article, nav, header, footer, main, .card, [class]') || el)
          : el;
        const sel = buildSelector(target);
        if (!sel || existingSelectors.has(sel)) continue;
        existingSelectors.add(sel);
        const r = target.getBoundingClientRect();
        const label = (typeof deriveLabel === 'function' ? deriveLabel(target) : '') || target.tagName.toLowerCase();
        const entry = normalize({
          label,
          selector: sel,
          ts: Date.now(),
          auto: true,
          kind: 'watch',
          layer: 'ui',
          reason: 'cursor-dwell',
          note: 'dwell ' + d.durationMs + 'ms',
          bounds: { x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height },
        }, before + added);
        scopeLabels().push(entry);
        added++;
      }
      save();
      renderTags();
      refreshHud();
      flash('watch · ' + added + ' label' + (added === 1 ? '' : 's') + ' from ' + dwells.length + ' dwell point' + (dwells.length === 1 ? '' : 's'));
      return;
    }
    // Start.
    _watchActive = true;
    _watchSamples = [];
    _watchLastSampleTs = 0;
    btn.textContent = 'stop watching';
    btn.classList.add('on');
    flash('watch · move the cursor naturally · click "stop watching" when done');
    _watchSampleHandler = (ev) => {
      const now = performance.now();
      if (now - _watchLastSampleTs < 50) return; // throttle to 20Hz
      _watchLastSampleTs = now;
      _watchSamples.push({ t: now, x: ev.clientX, y: ev.clientY });
    };
    document.addEventListener('mousemove', _watchSampleHandler, true);
  }

  // ── UI text-density grid · NEW (auto-label heatmap signal) ──────────
  // Toggles the grid overlay AND ensures a fresh grid is built so the next
  // doAutoLabel uses up-to-date density. Stored on `state` so it survives
  // toggle/scan ordering. The grid itself is rebuilt at the start of every
  // doAutoLabel anyway — the toggle just controls visibility.
  state.textGrid = state.textGrid || null;
  state.gridShown = state.gridShown || false;

  function toggleTextGrid(btn) {
    const tg = (typeof window !== 'undefined') ? window.__anatomyTextGrid : null;
    if (!tg) {
      flash('text-grid module not loaded · reload extension');
      return;
    }
    if (state.gridShown) {
      tg.removeGridOverlay();
      state.gridShown = false;
      if (btn) btn.classList.remove('on');
      flash('grid · off');
      return;
    }
    showProgress('grid · scanning text', { detail: 'walking text nodes' });
    try {
      state.textGrid = tg.buildTextGrid({ cellPx: 24 });
      tg.renderGridOverlay(state.textGrid);
      state.gridShown = true;
      if (btn) btn.classList.add('on');
      const g = state.textGrid;
      showProgress('grid · on', { state: 'done', detail: `${g.textNodes} text nodes · ${g.cols}×${g.rows} cells · max ${g.max}` });
    } catch (e) {
      console.error('[anatomy] grid build failed:', e);
      showProgress('grid failed', { state: 'error', detail: 'see console' });
    }
  }

  async function doAutoLabel() {
    showProgress('auto-labeling', { detail: 'scanning page…' });

    // Build the text-density grid first so onStep can rank candidates by
    // visible-text content. Falls back to bucket-only sort if the module
    // didn't load (extension partial reload, etc).
    const tg = (typeof window !== 'undefined') ? window.__anatomyTextGrid : null;
    let textGrid = null;
    if (tg) {
      try {
        textGrid = tg.buildTextGrid({ cellPx: 24 });
        state.textGrid = textGrid;
        // If the overlay is already on, refresh it against the new grid.
        if (state.gridShown) tg.renderGridOverlay(textGrid);
      } catch (e) {
        console.warn('[anatomy] text-grid build failed, falling back to bucket-only sort:', e);
        textGrid = null;
      }
    }
    const scoreCandidate = textGrid
      ? (c) => {
          if (!c.el || !c.el.isConnected) return 0;
          const r = c.el.getBoundingClientRect();
          return tg.scoreRegion(textGrid, {
            x: r.left + window.scrollX,
            y: r.top + window.scrollY,
            w: r.width,
            h: r.height,
          });
        }
      : () => 0;

    const bucket = (c) => {
      const t = c.el.tagName.toLowerCase();
      if (LANDMARK_TAGS.includes(t)) return 0;
      if (HEADING_TAGS.includes(t)) return 1;
      if (DIALOG_TAGS.includes(t) || c.el.getAttribute('role') === 'dialog') return 2;
      if (c.kind === 'click' || INTERACTIVE_TAGS.includes(t)) return 3;
      if (c.kind === 'card') return 4;
      return 5;
    };

    const startCount = scopeLabels().length;
    let totalCommitted = 0;

    // onStep: for each scroll batch, commit fresh candidates into scopeLabels
    // immediately so the HUD list and page dots populate live. End-of-scan
    // pass handles dedupe suffix renaming across the full accumulated set.
    const onStep = async (freshCandidates, stepIdx, totalSteps) => {
      // Sort this batch by bucket priority first (semantic importance:
      // landmark > heading > dialog > click > card > other), then by
      // text-density score (text-rich regions win the MAX_LABELS cap on
      // dense pages), then by document position for stable ordering.
      freshCandidates.sort((a, b) => {
        const ba = bucket(a), bb = bucket(b);
        if (ba !== bb) return ba - bb;
        const sa = scoreCandidate(a), sb = scoreCandidate(b);
        if (sa !== sb) return sb - sa;
        const pos = a.el.compareDocumentPosition(b.el);
        return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });
      const existing = new Set(scopeLabels().map(e => e.selector));
      const now = Date.now();
      let baseIdx = scopeLabels().length;
      for (const c of freshCandidates) {
        if (scopeLabels().length >= MAX_LABELS) break;
        if (existing.has(c.sel)) continue;
        if (!c.el || !c.el.isConnected) continue; // element gone since the batch
        const r = c.el.getBoundingClientRect();
        const entry = normalize({
          label: c.label,
          selector: c.sel,
          ts: now,
          auto: true,
          kind: c.kind,
          layer: 'ui',
          reason: c.reason,
          bounds: { x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height },
        }, baseIdx + totalCommitted);
        scopeLabels().push(entry);
        startWatch(entry.id, 5000);
        totalCommitted++;
      }
      save();
      renderTags();
      refreshHud();
      showProgress('auto-labeling', { done: stepIdx, total: totalSteps, detail: `${scopeLabels().length} labels · ${stepIdx}/${totalSteps} passes` });
    };

    let candidates;
    try { candidates = await gatherCandidatesScrolled(onStep); }
    catch (err) { console.error('[anatomy] gatherCandidates failed:', err); showProgress('auto-label failed', { state: 'error', detail: 'see console' }); return; }

    // Diagnostic: bucket distribution across the full accumulated candidate set.
    const buckets = { landmark: 0, heading: 0, dialog: 0, click: 0, card: 0, custom: 0, other: 0 };
    for (const c of candidates) {
      const t = c.el.tagName.toLowerCase();
      if (LANDMARK_TAGS.includes(t)) buckets.landmark++;
      else if (HEADING_TAGS.includes(t)) buckets.heading++;
      else if (DIALOG_TAGS.includes(t) || c.el.getAttribute('role') === 'dialog') buckets.dialog++;
      else if (c.kind === 'click' || INTERACTIVE_TAGS.includes(t)) buckets.click++;
      else if (c.kind === 'card') buckets.card++;
      else if (c.kind === 'custom') buckets.custom++;
      else buckets.other++;
    }
    console.log('[anatomy] candidates:', candidates.length, 'committed this run:', totalCommitted, 'buckets:', buckets);

    // End-of-scan cleanup: apply dedupe suffix renaming (" · 1/20") to the
    // freshly added labels so repeating patterns are still visually numbered.
    // We only touch labels added in THIS run.
    const runEnd = scopeLabels().length;
    if (totalCommitted > 0) {
      const windowSlice = scopeLabels().slice(startCount, runEnd);
      const labelCounts = new Map(); // label -> count
      for (const e of windowSlice) {
        labelCounts.set(e.label, (labelCounts.get(e.label) || 0) + 1);
      }
      const seen = new Map();
      for (const e of windowSlice) {
        const total = labelCounts.get(e.label) || 1;
        if (total <= 1) continue;
        const n = (seen.get(e.label) || 0) + 1;
        seen.set(e.label, n);
        e.label = total > REPEAT_KEEP ? `${e.label} · ${n}/${total}` : `${e.label} · ${n}`;
      }
      save();
      refreshHud();
    }

    if (totalCommitted === 0) {
      showProgress('nothing new to label', { state: 'done', detail: `${scopeLabels().length} total` });
      return;
    }
    showProgress('done', { state: 'done', detail: `+${totalCommitted} labels · ${scopeLabels().length} total` });
  }

  let flashEl = null;
  function flash(msg) {
    if (!flashEl) {
      flashEl = document.createElement('div');
      flashEl.className = 'anatomy-flash anatomy-root';
      document.body.appendChild(flashEl);
    }
    flashEl.textContent = msg;
    flashEl.style.opacity = '1';
    clearTimeout(flash._t);
    flash._t = setTimeout(() => { if (flashEl) flashEl.style.opacity = '0'; }, 1600);
  }

  // ── progress panel (sticks during long ops, vs flash which fades) ──────
  let progressEl = null;
  function ensureProgress() {
    if (progressEl) return progressEl;
    progressEl = document.createElement('div');
    progressEl.className = 'anatomy-progress anatomy-root';
    progressEl.innerHTML = `
      <div class="ap-phase"></div>
      <div class="ap-bar"><div class="ap-fill"></div></div>
      <div class="ap-detail"></div>
    `;
    document.body.appendChild(progressEl);
    return progressEl;
  }
  // showProgress(phase, {done, total, detail, state}) — state ∈ '' | 'done' | 'error'
  function showProgress(phase, opts) {
    const el = ensureProgress();
    const o = opts || {};
    el.classList.add('on');
    el.classList.remove('done', 'error', 'indeterminate');
    if (o.state === 'done')  el.classList.add('done');
    if (o.state === 'error') el.classList.add('error');
    el.querySelector('.ap-phase').textContent = phase || '';
    const fill = el.querySelector('.ap-fill');
    const detail = el.querySelector('.ap-detail');
    if (typeof o.done === 'number' && typeof o.total === 'number' && o.total > 0) {
      const pct = Math.max(0, Math.min(100, (o.done / o.total) * 100));
      fill.style.width = pct.toFixed(0) + '%';
      detail.textContent = o.detail || `${o.done} / ${o.total}`;
    } else {
      el.classList.add('indeterminate');
      fill.style.width = ''; // CSS animation drives it
      detail.textContent = o.detail || '';
    }
    // Auto-hide after a beat for terminal states.
    clearTimeout(showProgress._t);
    if (o.state === 'done' || o.state === 'error') {
      showProgress._t = setTimeout(() => { if (progressEl) progressEl.classList.remove('on'); }, 2200);
    }
  }
  function hideProgress() {
    clearTimeout(showProgress._t);
    if (progressEl) progressEl.classList.remove('on');
  }

  // -------------------------------------------------------------
  // Toggle
  // -------------------------------------------------------------
  let toggleBtn = null;
  function buildToggle() {
    toggleBtn = document.createElement('button');
    toggleBtn.className = 'anatomy-toggle anatomy-root';
    toggleBtn.textContent = 'ⓘ';
    toggleBtn.title = 'Anatomy — click to toggle, Alt+click elements to label';
    toggleBtn.addEventListener('click', (e) => {
      if (e.altKey) return; // don't toggle on labeling clicks
      setOn(!state.on);
    });
    document.body.appendChild(toggleBtn);
  }
  function setOn(on) {
    state.on = on;
    toggleBtn.classList.toggle('on', on);
    hudEl.classList.toggle('on', on);
    if (on) { renderTags(); refreshHud(); }
    else { clearTags(); }
  }

  // -------------------------------------------------------------
  // Messages (from popup)
  // -------------------------------------------------------------
  chrome.runtime.onMessage.addListener((msg, sender, reply) => {
    if (msg.type === 'toggle') { setOn(!state.on); reply({ on: state.on }); }
    if (msg.type === 'status') { reply({ on: state.on, count: scopeLabels().length, scope: scopeKey() }); }
    if (msg.type === 'export') { doExport(); reply({ ok: true }); }
    if (msg.type === 'clear')  { state.labels[scopeKey()] = []; save(); renderTags(); refreshHud(); reply({ ok: true }); }
    return true;
  });

  // -------------------------------------------------------------
  // Boot
  // -------------------------------------------------------------
  load().then(() => {
    buildToggle();
    buildHud();
    document.addEventListener('click', onClick, true);
    document.addEventListener('mousemove', onMove, true);
    window.addEventListener('scroll', () => { if (state.on) renderTags(); }, true);
    window.addEventListener('resize', () => { if (state.on) renderTags(); });
    window.addEventListener('anatomy:request', onRequest);
  });
})();

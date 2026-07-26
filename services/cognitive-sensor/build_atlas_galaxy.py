"""build_atlas_galaxy.py - render atlas_points.json as a WebGL galaxy.

Produces a single-file `atlas_galaxy.html` (~32 MB) that renders the
same UMAP coordinates as `cognitive_atlas.html` but with the deck.gl
WebGL pipeline: dark space, glowing points, density-heatmap toggle,
smooth pan + zoom, hover tooltip per point. Replaces the "stiff and
rigid" Plotly scatter with something organic.

Inputs:
    atlas_points.json          (run extract_atlas_data.py --full first)
    atlas_points_index.json    (per-cluster aggregates, optional)

Output:
    atlas_galaxy.html
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE = Path(__file__).parent.resolve()


# Single-file HTML template. The {{DATA_JSON}} placeholder gets replaced
# with the compact JSON blob. Everything else is inline so the file is
# double-clickable.
HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Cognitive Galaxy</title>
  <style>
    :root {
      --bg: #06060d;
      --panel: rgba(18, 20, 32, 0.86);
      --panel-edge: #2a2c44;
      --ink: #e6e8f5;
      --muted: #8a8db0;
      --accent: #7c5cff;
    }
    html, body { margin: 0; padding: 0; height: 100%; background: var(--bg); color: var(--ink);
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; overflow: hidden; }
    #map { position: fixed; inset: 0; }
    #controls {
      position: fixed; top: 16px; left: 16px; z-index: 10;
      background: var(--panel); border: 1px solid var(--panel-edge);
      border-radius: 14px; padding: 16px 18px; min-width: 260px; max-width: 320px;
      backdrop-filter: blur(10px) saturate(140%);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
    }
    #controls h1 { font-size: 14px; margin: 0 0 8px; letter-spacing: 0.04em;
      text-transform: uppercase; color: var(--muted); font-weight: 600; }
    #controls h2 { font-size: 18px; margin: 0 0 14px; letter-spacing: -0.01em; }
    .row { display: flex; align-items: center; justify-content: space-between;
      margin: 10px 0; gap: 12px; font-size: 13px; }
    .row label { color: var(--muted); flex: 0 0 auto; }
    .row select, .row input[type="range"] { flex: 1 1 auto; min-width: 0; }
    select { background: #1a1d2e; color: var(--ink); border: 1px solid var(--panel-edge);
      border-radius: 6px; padding: 4px 8px; font-size: 13px; }
    input[type="range"] { accent-color: var(--accent); }
    .check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink);
      margin: 8px 0; cursor: pointer; }
    .check input { accent-color: var(--accent); }
    #stats { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--panel-edge);
      font-size: 11px; color: var(--muted); line-height: 1.6; font-variant-numeric: tabular-nums; }
    #legend {
      position: fixed; bottom: 16px; left: 16px; z-index: 10;
      background: var(--panel); border: 1px solid var(--panel-edge);
      border-radius: 12px; padding: 10px 14px; backdrop-filter: blur(10px);
      font-size: 11px; color: var(--muted); max-width: 260px;
    }
    #legend .swatch { display: inline-block; width: 10px; height: 10px;
      border-radius: 50%; margin-right: 6px; vertical-align: middle; }
    #legend .item { display: flex; align-items: center; margin: 3px 0; }
    #tooltip {
      position: absolute; pointer-events: none; z-index: 20;
      background: rgba(10, 12, 22, 0.94); border: 1px solid var(--panel-edge);
      border-radius: 8px; padding: 8px 12px; font-size: 12px; color: var(--ink);
      max-width: 320px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
      transition: opacity 0.1s ease; opacity: 0;
    }
    #tooltip.show { opacity: 1; }
    #tooltip .title { font-weight: 600; margin-bottom: 4px; }
    #tooltip .meta { color: var(--muted); font-size: 11px; }
    #hint {
      position: fixed; top: 16px; right: 16px; z-index: 10; background: var(--panel);
      border: 1px solid var(--panel-edge); border-radius: 12px; padding: 10px 14px;
      backdrop-filter: blur(10px); font-size: 11px; color: var(--muted); max-width: 240px;
    }
    #hint kbd { background: #1a1d2e; border: 1px solid var(--panel-edge); border-radius: 4px;
      padding: 1px 6px; font-size: 10px; color: var(--ink); font-family: ui-monospace, Consolas, monospace; }
  </style>
</head>
<body>
  <div id="map"></div>

  <div id="controls">
    <h1>Cognitive Galaxy</h1>
    <h2 id="title">your mind, 22 months</h2>

    <div class="row">
      <label>Color by</label>
      <select id="colorBy">
        <option value="cluster">cluster</option>
        <option value="role">role</option>
        <option value="recency">recency</option>
      </select>
    </div>

    <div class="row">
      <label>Point size</label>
      <input id="size" type="range" min="0.5" max="6" step="0.25" value="2"/>
    </div>

    <div class="row">
      <label>Glow</label>
      <input id="opacity" type="range" min="20" max="255" step="5" value="180"/>
    </div>

    <label class="check">
      <input id="heatmap" type="checkbox" checked/> Density nebula
    </label>

    <label class="check">
      <input id="points" type="checkbox" checked/> Individual stars
    </label>

    <div id="stats"></div>
  </div>

  <div id="legend"></div>

  <div id="hint">
    drag to pan &middot; scroll to zoom &middot; hover for title
  </div>

  <div id="tooltip"></div>

  <script src="https://unpkg.com/deck.gl@9.0.30/dist.min.js"></script>
  <script>
    // ===== embedded data =====
    const D = {{DATA_JSON}};

    // ===== derived structures =====
    const N = D.x.length;
    const xs = new Float32Array(D.x);
    const ys = new Float32Array(D.y);

    // Build a per-point typed array of [x, y] for deck.gl binary path.
    const positions = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) {
      positions[2*i]     = xs[i];
      positions[2*i + 1] = ys[i];
    }

    // Cluster IDs are in D.layers.cluster — could be -1 for noise.
    const clusters = D.layers.cluster || new Array(N).fill(-1);
    const roles = D.roles || new Array(N).fill('assistant');
    const times = D.layers.time || new Array(N).fill(0);  // normalized 0..1

    // Color palette for clusters (HSL-stepped, perceptually-ish smooth).
    function paletteForCluster(cid) {
      if (cid < 0) return [60, 60, 80, 120];  // noise -> dim gray
      // Stable hash from cluster id -> hue.
      const hue = (cid * 137) % 360;
      const sat = 0.78;
      const light = 0.6;
      return hslToRgb(hue / 360, sat, light).concat([220]);
    }

    function hslToRgb(h, s, l) {
      let r, g, b;
      if (s === 0) { r = g = b = l; }
      else {
        const hue2rgb = (p, q, t) => {
          if (t < 0) t += 1;
          if (t > 1) t -= 1;
          if (t < 1/6) return p + (q - p) * 6 * t;
          if (t < 1/2) return q;
          if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
          return p;
        };
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
      }
      return [Math.round(r*255), Math.round(g*255), Math.round(b*255)];
    }

    const ROLE_COLORS = {
      user:      [124, 92, 255, 220],   // accent purple
      assistant: [80, 200, 255, 220],   // cyan
      tool:      [255, 180, 80, 220],   // amber
    };

    function colorByRecency(t) {
      // t in [0,1]. Old -> deep blue, recent -> hot pink.
      const r = Math.round(40 + t * 215);
      const g = Math.round(60 + t * 60);
      const b = Math.round(200 - t * 100);
      return [r, g, b, 200];
    }

    // Pre-compute color arrays for each mode (so toggle is instant).
    function buildColorArray(mode) {
      const colors = new Uint8Array(N * 4);
      for (let i = 0; i < N; i++) {
        let c;
        if (mode === 'cluster') c = paletteForCluster(clusters[i] | 0);
        else if (mode === 'role') c = ROLE_COLORS[roles[i]] || ROLE_COLORS.assistant;
        else c = colorByRecency(times[i] || 0);
        colors[4*i]     = c[0];
        colors[4*i + 1] = c[1];
        colors[4*i + 2] = c[2];
        colors[4*i + 3] = c[3];
      }
      return colors;
    }

    let colorMode = 'cluster';
    let colors = buildColorArray(colorMode);
    let pointSize = 2;
    let pointAlpha = 180;
    let showHeatmap = true;
    let showPoints = true;

    // ===== view & camera =====
    function bboxOf(xs, ys) {
      let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
      for (let i = 0; i < xs.length; i++) {
        if (xs[i] < xMin) xMin = xs[i];
        if (xs[i] > xMax) xMax = xs[i];
        if (ys[i] < yMin) yMin = ys[i];
        if (ys[i] > yMax) yMax = ys[i];
      }
      return { xMin, xMax, yMin, yMax };
    }
    const bb = bboxOf(xs, ys);
    const cx = (bb.xMin + bb.xMax) / 2;
    const cy = (bb.yMin + bb.yMax) / 2;
    const span = Math.max(bb.xMax - bb.xMin, bb.yMax - bb.yMin) || 1;

    const initialViewState = {
      target: [cx, cy, 0],
      zoom: Math.log2(800 / span),
      minZoom: -4,
      maxZoom: 12,
    };

    // ===== deck.gl layers =====
    const {Deck, OrthographicView} = deck;
    const {ScatterplotLayer, HeatmapLayer} = deck;

    function makeScatterLayer() {
      return new ScatterplotLayer({
        id: 'stars',
        data: {
          length: N,
          attributes: {
            getPosition: { value: positions, size: 2 },
            getFillColor: { value: colors, size: 4, normalized: false },
          },
        },
        radiusUnits: 'pixels',
        radiusMinPixels: 0.5,
        radiusMaxPixels: 12,
        getRadius: pointSize,
        opacity: pointAlpha / 255,
        pickable: true,
        billboard: false,
        stroked: false,
        antialiasing: true,
        updateTriggers: {
          getRadius: [pointSize],
          getFillColor: [colorMode],
        },
        onHover: showTooltip,
      });
    }

    function makeHeatmapLayer() {
      // Use a synthetic accessor; HeatmapLayer needs per-point lookup.
      return new HeatmapLayer({
        id: 'nebula',
        data: { length: N },
        getPosition: (_, {index}) => [positions[2*index], positions[2*index + 1]],
        getWeight: 1,
        radiusPixels: 36,
        intensity: 1.2,
        threshold: 0.04,
        aggregation: 'SUM',
        colorRange: [
          [10,   20,  60,   0],
          [40,   30, 120,  60],
          [90,   50, 200, 120],
          [160,  90, 220, 180],
          [220, 140, 200, 220],
          [255, 220, 180, 255],
        ],
      });
    }

    function rebuildLayers() {
      const layers = [];
      if (showHeatmap) layers.push(makeHeatmapLayer());
      if (showPoints)  layers.push(makeScatterLayer());
      return layers;
    }

    const deckInstance = new Deck({
      parent: document.getElementById('map'),
      views: new OrthographicView({controller: true}),
      initialViewState,
      controller: { dragRotate: false, minZoom: -4, maxZoom: 12, scrollZoom: { smooth: true, speed: 0.01 } },
      layers: rebuildLayers(),
      style: { background: 'radial-gradient(ellipse at center, #0e0e22 0%, #06060d 70%)' },
    });

    // ===== tooltip =====
    const tipEl = document.getElementById('tooltip');
    function showTooltip(info) {
      if (!info.object && info.index < 0) {
        tipEl.classList.remove('show');
        return;
      }
      const i = info.index;
      const cid = D.convo_ids[i];
      const title = (D.titleLookup && D.titleLookup[cid]) || '(untitled)';
      const date = (D.dateLookup && D.dateLookup[cid]) || '';
      const role = roles[i];
      const cluster = clusters[i];
      tipEl.innerHTML = `<div class="title">${escape(title)}</div>` +
        `<div class="meta">${escape(role)} &middot; cluster ${cluster < 0 ? 'noise' : cluster}${date ? ' &middot; ' + escape(date) : ''}</div>`;
      tipEl.style.left = info.x + 14 + 'px';
      tipEl.style.top = info.y + 14 + 'px';
      tipEl.classList.add('show');
    }
    function escape(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

    // ===== controls =====
    document.getElementById('colorBy').addEventListener('change', e => {
      colorMode = e.target.value;
      colors = buildColorArray(colorMode);
      deckInstance.setProps({ layers: rebuildLayers() });
      renderLegend();
    });
    document.getElementById('size').addEventListener('input', e => {
      pointSize = parseFloat(e.target.value);
      deckInstance.setProps({ layers: rebuildLayers() });
    });
    document.getElementById('opacity').addEventListener('input', e => {
      pointAlpha = parseInt(e.target.value, 10);
      deckInstance.setProps({ layers: rebuildLayers() });
    });
    document.getElementById('heatmap').addEventListener('change', e => {
      showHeatmap = e.target.checked;
      deckInstance.setProps({ layers: rebuildLayers() });
    });
    document.getElementById('points').addEventListener('change', e => {
      showPoints = e.target.checked;
      deckInstance.setProps({ layers: rebuildLayers() });
    });

    // ===== legend & stats =====
    function renderLegend() {
      const el = document.getElementById('legend');
      if (colorMode === 'role') {
        el.innerHTML = `
          <div class="item"><span class="swatch" style="background:rgb(124,92,255)"></span>you (user)</div>
          <div class="item"><span class="swatch" style="background:rgb(80,200,255)"></span>assistant</div>
          <div class="item"><span class="swatch" style="background:rgb(255,180,80)"></span>tool</div>
        `;
      } else if (colorMode === 'recency') {
        el.innerHTML = `
          <div>oldest <-> newest</div>
          <div style="height:10px; margin-top:6px; border-radius:5px;
            background: linear-gradient(90deg, rgb(40,60,200), rgb(100,90,180), rgb(255,120,100));"></div>
        `;
      } else {
        // cluster
        el.innerHTML = `1,801 clusters &middot; HSL-stepped by id<br/>noise points: dim gray`;
      }
    }
    renderLegend();

    function renderStats() {
      const roleCounts = { user: 0, assistant: 0, tool: 0 };
      for (let i = 0; i < N; i++) roleCounts[roles[i]] = (roleCounts[roles[i]] || 0) + 1;
      const nClusters = new Set(clusters.filter(c => c >= 0)).size;
      const nNoise = clusters.filter(c => c < 0).length;
      document.getElementById('stats').innerHTML =
        `${N.toLocaleString()} points<br/>` +
        `${nClusters.toLocaleString()} clusters &middot; ${nNoise.toLocaleString()} noise<br/>` +
        `${roleCounts.user.toLocaleString()} you &middot; ${roleCounts.assistant.toLocaleString()} ai &middot; ${roleCounts.tool.toLocaleString()} tool`;
    }
    renderStats();
  </script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--points", type=Path, default=BASE / "atlas_points.json",
                   help="Per-message point arrays (run extract_atlas_data.py --full)")
    p.add_argument("--out", type=Path, default=BASE / "atlas_galaxy.html")
    args = p.parse_args()

    if not args.points.exists():
        raise SystemExit(
            f"missing: {args.points}\n"
            f"run: python extract_atlas_data.py --full"
        )

    print(f"Reading {args.points.name} ...")
    data = json.loads(args.points.read_text(encoding="utf-8"))
    n_points = len(data.get("x", []))
    print(f"  {n_points:,} points")

    # Embed as compact JSON (no whitespace).
    blob = json.dumps(data, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("{{DATA_JSON}}", blob)

    print(f"Writing {args.out.name} ...")
    args.out.write_text(html, encoding="utf-8")
    print(f"  {args.out.stat().st_size / 1024 / 1024:.1f} MB")

    print("\nDone. Open with:")
    print(f"  start {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

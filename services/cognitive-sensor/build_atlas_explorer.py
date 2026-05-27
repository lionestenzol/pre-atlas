"""build_atlas_explorer.py - interactive single-file dashboard.

Generates `atlas_explorer.html` (~8 MB embedded). Four "shape" lenses
let you see + click your way through:

    Map     : cluster scatter (sized by mass, colored by dominant role)
    You     : domain x time stacked area (where attention went)
    Topics  : top-30 ideas by mention count (what recurs)
    Time    : conversation length x outcome (where you got stuck)

Click any cluster -> right rail shows top conversations.
Click any conversation -> modal shows metadata + top quote.

Reads:
    atlas_clusters.json
    conversation_classifications.json
    idea_registry.json
    results.db (for monthly distributions)

Output:
    atlas_explorer.html
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()


def _load_classifications(p: Path) -> list[dict]:
    return json.loads(p.read_text(encoding="utf-8"))["classifications"]


def _load_registry(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_clusters(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _build_convo_index(classifications: list[dict]) -> dict[str, dict]:
    """One small record per convo for the right-rail conversation list."""
    out = {}
    for c in classifications:
        if c.get("skipped"):
            continue
        out[c["convo_id"]] = {
            "title": c.get("title", "(untitled)"),
            "date": c.get("date") or "",
            "domain": c.get("domain") or "uncategorized",
            "outcome": c.get("outcome") or "looped",
            "trajectory": c.get("emotional_trajectory") or "neutral",
            "intensity": c.get("intensity") or "low",
            "word_count": int(c.get("word_count") or 0),
        }
    return out


def _build_cluster_summary(clusters_data: dict, convo_index: dict) -> list[dict]:
    """One record per cluster for the map + right-rail clicks.

    Enriches the existing atlas_clusters.json cluster_summary with the
    actual list of convo_ids in that cluster (so click -> drill works).
    """
    centroids = clusters_data.get("cluster_centroids", {})
    assignments = clusters_data.get("convo_cluster_assignments", {})

    # Invert: cluster_id -> [convo_ids]
    convos_per_cluster: dict[int, list[str]] = defaultdict(list)
    for convo_id, cl in assignments.items():
        convos_per_cluster[int(cl)].append(convo_id)

    out = []
    for cs in clusters_data["cluster_summary"]:
        cid = int(cs["id"])
        convo_ids = convos_per_cluster.get(cid, [])
        # Sort by date desc using the convo_index
        convo_ids.sort(
            key=lambda cid: convo_index.get(cid, {}).get("date") or "",
            reverse=True,
        )
        # Get centroid (x, y)
        cent = centroids.get(str(cid)) or [0.0, 0.0]
        # Compute domain breakdown for this cluster (from convo_index)
        dom_counts: Counter = Counter()
        out_counts: Counter = Counter()
        for cvid in convo_ids:
            v = convo_index.get(cvid)
            if v:
                dom_counts[v["domain"]] += 1
                out_counts[v["outcome"]] += 1
        # Best title for the cluster name = highest-msg top_title
        name = (cs["top_titles"][0]["title"]
                if cs.get("top_titles") else f"cluster {cid}")
        out.append({
            "id": cid,
            "name": name,
            "msg_count": int(cs["count"]),
            "convo_count": len(convo_ids),
            "convo_ids": convo_ids[:50],  # cap right-rail to 50 most recent
            "x": round(float(cent[0]), 4),
            "y": round(float(cent[1]), 4),
            "dominant_role": cs.get("dominant_role", "assistant"),
            "user_pct": float(cs.get("user_pct", 0.0)),
            "date_range": cs.get("date_range", ""),
            "top_titles": cs.get("top_titles", []),
            "domain_breakdown": dict(dom_counts.most_common()),
            "outcome_breakdown": dict(out_counts.most_common()),
        })
    # Sort by message mass desc so the right-rail default-list is largest first
    out.sort(key=lambda c: c["msg_count"], reverse=True)
    return out


def _build_monthly_by_domain(classifications: list[dict]) -> dict:
    """For the "You" lens — domain × month stacked area.

    Returns:
        {
          "months": ["2024-08", ..., "2026-05"],
          "domains": ["technical", "personal", ...],
          "series": {domain: [counts per month]}
        }
    """
    grid: dict[str, Counter] = defaultdict(Counter)
    domains_seen: set[str] = set()
    for c in classifications:
        if c.get("skipped"):
            continue
        d = c.get("date") or ""
        if len(d) < 7:
            continue
        ym = d[:7]
        dom = c.get("domain") or "uncategorized"
        grid[ym][dom] += 1
        domains_seen.add(dom)
    months = sorted(grid.keys())
    domains = sorted(domains_seen)
    series = {dom: [grid[m].get(dom, 0) for m in months] for dom in domains}
    return {"months": months, "domains": domains, "series": series}


def _build_top_ideas(registry: dict, n: int = 30) -> list[dict]:
    """For the "Topics" lens — most-mentioned ideas."""
    ideas = registry.get("full_registry", [])
    ideas = sorted(ideas, key=lambda i: -int(i.get("mention_count") or 0))[:n]
    out = []
    for i in ideas:
        out.append({
            "id": i["canonical_id"],
            "title": i["canonical_title"],
            "category": i.get("category", "uncategorized"),
            "status": i.get("status", "idea"),
            "tier": i.get("tier", "backlog"),
            "mention_count": int(i.get("mention_count") or 0),
            "priority_score": round(float(i.get("priority_score") or 0), 3),
        })
    return out


def _build_length_by_outcome(classifications: list[dict]) -> dict:
    """For the "Time" lens — conversation length histogram, faceted by outcome.

    Bins: <100, 100-500, 500-1k, 1k-2k, 2k-5k, 5k+
    """
    bin_labels = ["<100", "100-500", "500-1k", "1k-2k", "2k-5k", "5k+"]
    def bin_of(wc: int) -> int:
        if wc < 100:    return 0
        if wc < 500:    return 1
        if wc < 1000:   return 2
        if wc < 2000:   return 3
        if wc < 5000:   return 4
        return 5

    by_outcome: dict[str, list[int]] = defaultdict(lambda: [0] * len(bin_labels))
    outcomes_seen: set[str] = set()
    for c in classifications:
        if c.get("skipped"):
            continue
        wc = int(c.get("word_count") or 0)
        out = c.get("outcome") or "looped"
        by_outcome[out][bin_of(wc)] += 1
        outcomes_seen.add(out)
    return {
        "bins": bin_labels,
        "outcomes": sorted(outcomes_seen),
        "series": {o: by_outcome[o] for o in sorted(outcomes_seen)},
    }


def _build_top_quotes_per_cluster(registry: dict, clusters: list[dict]) -> dict:
    """For convo detail modal — pull up to 3 representative quotes per cluster
    from any registered ideas whose convo_id falls in the cluster."""
    # registry full_registry items have version_timeline with convo_id refs
    by_convo: dict[str, list[str]] = defaultdict(list)
    for idea in registry.get("full_registry", []):
        for v in idea.get("version_timeline", []) or []:
            cid = v.get("convo_id")
            q = v.get("key_quote")
            if cid and q and len(by_convo[cid]) < 3:
                by_convo[cid].append(q)
    return by_convo


# -----------------------------------------------------------------------------
# HTML TEMPLATE
# -----------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Atlas Explorer</title>
  <style>
    :root {
      --bg: #0a0b14;
      --bg2: #11131f;
      --panel: rgba(20, 22, 36, 0.94);
      --panel-edge: #2a2d44;
      --ink: #e8eaf6;
      --muted: #8a8db0;
      --accent: #7c5cff;
      --accent2: #4ad7ff;
      --warm: #ff6b8a;
      --warn: #ffb547;
      --good: #7ee787;
    }
    html, body { margin: 0; padding: 0; height: 100%; background: var(--bg);
      color: var(--ink); font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; overflow: hidden; }
    body { display: grid; grid-template-rows: auto 1fr; }

    header { display: flex; align-items: center; gap: 16px; padding: 14px 20px;
      border-bottom: 1px solid var(--panel-edge); background: linear-gradient(180deg, var(--bg2) 0%, transparent 100%); }
    header h1 { font-size: 14px; margin: 0; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
    header .subtitle { font-size: 12px; color: var(--muted); }
    .tabs { display: flex; gap: 4px; margin-left: auto; background: var(--bg2); border-radius: 10px; padding: 4px; border: 1px solid var(--panel-edge); }
    .tab { padding: 6px 14px; font-size: 12px; color: var(--muted); cursor: pointer; border-radius: 7px; transition: all 0.15s; letter-spacing: 0.04em; text-transform: uppercase; font-weight: 500; }
    .tab:hover { color: var(--ink); }
    .tab.active { background: var(--accent); color: white; }

    main { display: grid; grid-template-columns: 1fr 360px; height: 100%; overflow: hidden; }
    #viz { padding: 16px; overflow: hidden; position: relative; }
    #chart { width: 100%; height: 100%; }
    .filters { position: absolute; top: 16px; left: 16px; z-index: 5; display: flex; gap: 6px; flex-wrap: wrap; max-width: calc(100% - 40px); }
    .chip { padding: 4px 10px; border-radius: 14px; font-size: 11px; background: var(--bg2); border: 1px solid var(--panel-edge); color: var(--muted); cursor: pointer; transition: all 0.1s; user-select: none; }
    .chip:hover { color: var(--ink); border-color: var(--accent); }
    .chip.on { background: var(--accent); color: white; border-color: var(--accent); }

    #rail { background: var(--bg2); border-left: 1px solid var(--panel-edge); display: flex; flex-direction: column; overflow: hidden; }
    .rail-header { padding: 14px 18px 8px; border-bottom: 1px solid var(--panel-edge); }
    .rail-header h2 { font-size: 11px; margin: 0; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
    .rail-header h3 { font-size: 16px; margin: 4px 0 0; color: var(--ink); font-weight: 500; line-height: 1.3; }
    .rail-meta { font-size: 11px; color: var(--muted); margin-top: 6px; }
    .rail-meta span { margin-right: 12px; }
    .rail-body { flex: 1; overflow-y: auto; padding: 8px 0; }
    .rail-body::-webkit-scrollbar { width: 6px; }
    .rail-body::-webkit-scrollbar-thumb { background: var(--panel-edge); border-radius: 3px; }
    .convo-item { padding: 8px 18px; cursor: pointer; transition: background 0.1s; border-left: 2px solid transparent; }
    .convo-item:hover { background: rgba(124, 92, 255, 0.08); border-left-color: var(--accent); }
    .convo-item .title { font-size: 13px; color: var(--ink); line-height: 1.4; margin-bottom: 3px; word-break: break-word; }
    .convo-item .meta { font-size: 10px; color: var(--muted); display: flex; gap: 10px; flex-wrap: wrap; }
    .convo-item .meta .badge { padding: 1px 6px; border-radius: 3px; background: var(--bg); font-size: 9px; letter-spacing: 0.04em; text-transform: uppercase; }
    .badge.outcome-produced { background: rgba(126, 231, 135, 0.15); color: var(--good); }
    .badge.outcome-resolved { background: rgba(74, 215, 255, 0.15); color: var(--accent2); }
    .badge.outcome-abandoned { background: rgba(255, 107, 138, 0.15); color: var(--warm); }
    .badge.outcome-looped { background: rgba(255, 181, 71, 0.15); color: var(--warn); }
    .empty-state { padding: 40px 24px; text-align: center; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .empty-state b { color: var(--ink); }

    /* breakdown bars in the rail header */
    .breakdown { margin-top: 10px; }
    .breakdown .row { display: flex; align-items: center; gap: 8px; margin: 3px 0; font-size: 10px; color: var(--muted); }
    .breakdown .label { flex: 0 0 80px; text-transform: capitalize; }
    .breakdown .bar { flex: 1; height: 4px; background: var(--bg); border-radius: 2px; overflow: hidden; }
    .breakdown .bar > div { height: 100%; background: var(--accent); border-radius: 2px; }
    .breakdown .count { flex: 0 0 28px; text-align: right; font-variant-numeric: tabular-nums; }

    /* modal */
    #modal { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.7); z-index: 100; display: none; align-items: center; justify-content: center; padding: 40px; backdrop-filter: blur(4px); }
    #modal.show { display: flex; }
    .modal-card { background: var(--bg2); border: 1px solid var(--panel-edge); border-radius: 16px; max-width: 720px; width: 100%; max-height: 80vh; display: flex; flex-direction: column; overflow: hidden; }
    .modal-head { padding: 20px 24px 12px; border-bottom: 1px solid var(--panel-edge); }
    .modal-head h2 { font-size: 18px; margin: 0; line-height: 1.3; }
    .modal-head .meta { margin-top: 8px; font-size: 11px; color: var(--muted); display: flex; gap: 16px; flex-wrap: wrap; }
    .modal-body { padding: 20px 24px; overflow-y: auto; flex: 1; }
    .modal-body h3 { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 12px; font-weight: 600; }
    .modal-body .quote { background: var(--bg); border-left: 3px solid var(--accent); padding: 12px 16px; border-radius: 6px; margin: 10px 0; font-size: 13px; line-height: 1.55; color: var(--ink); white-space: pre-wrap; }
    .modal-body .quote.no-quote { color: var(--muted); font-style: italic; border-left-color: var(--muted); }
    .modal-foot { padding: 12px 24px; border-top: 1px solid var(--panel-edge); display: flex; gap: 12px; align-items: center; font-size: 11px; color: var(--muted); }
    .modal-foot code { background: var(--bg); padding: 3px 8px; border-radius: 4px; color: var(--accent2); font-family: ui-monospace, Consolas, monospace; user-select: all; cursor: text; }
    .close { margin-left: auto; cursor: pointer; color: var(--muted); font-size: 18px; padding: 4px 8px; border-radius: 4px; }
    .close:hover { color: var(--ink); background: rgba(255,255,255,0.06); }
  </style>
</head>
<body>

  <header>
    <h1>Atlas Explorer</h1>
    <span class="subtitle" id="subtitle">loading...</span>
    <div class="tabs">
      <div class="tab active" data-lens="map">Topics</div>
      <div class="tab" data-lens="you">You</div>
      <div class="tab" data-lens="ideas">Ideas</div>
      <div class="tab" data-lens="time">Time</div>
    </div>
  </header>

  <main>
    <div id="viz">
      <div class="filters" id="filters"></div>
      <div id="chart"></div>
    </div>

    <aside id="rail">
      <div class="rail-header" id="rail-header">
        <h2>top clusters</h2>
        <h3>your mind, ranked by mass</h3>
        <div class="rail-meta">click any cluster on the map -> drill in</div>
      </div>
      <div class="rail-body" id="rail-body"></div>
    </aside>
  </main>

  <div id="modal">
    <div class="modal-card">
      <div class="modal-head">
        <h2 id="modal-title">title</h2>
        <div class="meta" id="modal-meta"></div>
      </div>
      <div class="modal-body" id="modal-body"></div>
      <div class="modal-foot">
        <span>read the full conversation:</span>
        <code id="modal-cmd"></code>
        <span class="close" id="modal-close">x</span>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
  <script>
    // ============ embedded data ============
    const D = {{DATA_JSON}};

    // ============ state ============
    const state = {
      lens: 'map',
      domainFilter: null,    // null = all, or "technical"/"personal"/...
      selectedCluster: null, // cluster id or null
    };

    // ============ helpers ============
    function fmt(n) { return Number(n).toLocaleString(); }
    function escape(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

    function dominantColor(domain) {
      return ({
        technical: '#4ad7ff',
        personal: '#ff6b8a',
        business: '#ffb547',
        learning: '#7ee787',
        processing: '#c792ea',
        execution: '#7c5cff',
        uncategorized: '#5a5d80',
      })[domain] || '#5a5d80';
    }

    function outcomeColor(outcome) {
      return ({
        produced: '#7ee787',
        resolved: '#4ad7ff',
        abandoned: '#ff6b8a',
        looped: '#ffb547',
      })[outcome] || '#5a5d80';
    }

    function clusterDominantDomain(c) {
      const dom = c.domain_breakdown || {};
      const keys = Object.keys(dom);
      if (!keys.length) return 'uncategorized';
      return keys.reduce((a, b) => (dom[b] > dom[a] ? b : a));
    }

    function filteredClusters() {
      const f = state.domainFilter;
      if (!f) return D.clusters;
      return D.clusters.filter(c => clusterDominantDomain(c) === f);
    }

    // ============ chart instance ============
    const chart = echarts.init(document.getElementById('chart'), null, { renderer: 'canvas' });
    window.addEventListener('resize', () => chart.resize());

    chart.on('click', (params) => {
      if (state.lens === 'map' && params.componentType === 'series' && params.data && params.data.id != null) {
        selectCluster(params.data.id);
      } else if (state.lens === 'ideas' && params.componentType === 'series') {
        // ideas bar click -> show idea modal
        const idea = D.topIdeas[params.dataIndex];
        if (idea) showIdeaModal(idea);
      }
    });

    // ============ filters ============
    function renderFilters() {
      const el = document.getElementById('filters');
      if (state.lens !== 'map') { el.innerHTML = ''; return; }
      const domains = Array.from(new Set(D.clusters.map(clusterDominantDomain))).sort();
      const html = ['<span class="chip ' + (state.domainFilter == null ? 'on' : '') + '" data-domain="__all">All</span>'];
      for (const d of domains) {
        const cls = state.domainFilter === d ? 'on' : '';
        html.push(`<span class="chip ${cls}" data-domain="${escape(d)}" style="border-color:${dominantColor(d)}33">${escape(d)}</span>`);
      }
      el.innerHTML = html.join('');
      el.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
          const d = chip.dataset.domain;
          state.domainFilter = (d === '__all') ? null : (state.domainFilter === d ? null : d);
          renderFilters();
          renderChart();
        });
      });
    }

    // ============ lenses ============

    function renderMap() {
      const clusters = filteredClusters();
      const data = clusters.map(c => ({
        id: c.id,
        name: c.name,
        value: [c.x, c.y, c.msg_count],
        symbolSize: Math.max(4, Math.min(60, Math.sqrt(c.msg_count) / 4)),
        itemStyle: {
          color: dominantColor(clusterDominantDomain(c)),
          opacity: 0.78,
          borderColor: 'rgba(255,255,255,0.15)',
          borderWidth: 0.5,
        },
      }));
      chart.setOption({
        backgroundColor: 'transparent',
        animation: true,
        animationDuration: 400,
        tooltip: {
          trigger: 'item',
          backgroundColor: 'rgba(20,22,36,0.96)',
          borderColor: '#2a2d44',
          textStyle: { color: '#e8eaf6', fontSize: 12 },
          formatter: (p) => {
            const c = D.clusters.find(x => x.id === p.data.id);
            if (!c) return '';
            const dom = clusterDominantDomain(c);
            const role = c.dominant_role + ' (' + c.user_pct.toFixed(0) + '% you)';
            return `<b>${escape(c.name)}</b><br/>${fmt(c.msg_count)} msgs / ${fmt(c.convo_count)} convos<br/><span style="color:${dominantColor(dom)}">${escape(dom)}</span> &middot; ${escape(role)}<br/><span style="color:#8a8db0">${escape(c.date_range)}</span>`;
          },
        },
        grid: { left: 30, right: 30, top: 60, bottom: 30, containLabel: false },
        xAxis: { type: 'value', show: false, scale: true },
        yAxis: { type: 'value', show: false, scale: true },
        series: [{
          type: 'scatter',
          data,
          large: true,
          largeThreshold: 500,
          progressive: 800,
          emphasis: { itemStyle: { borderColor: '#fff', borderWidth: 2, opacity: 1 } },
        }],
      }, true);
    }

    function renderYou() {
      const m = D.monthly;
      const colors = m.domains.map(dominantColor);
      chart.setOption({
        backgroundColor: 'transparent',
        animation: true,
        color: colors,
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(20,22,36,0.96)',
          borderColor: '#2a2d44',
          textStyle: { color: '#e8eaf6', fontSize: 12 },
        },
        legend: { data: m.domains, textStyle: { color: '#8a8db0', fontSize: 11 }, top: 10, icon: 'circle', itemWidth: 10, itemHeight: 10 },
        grid: { left: 50, right: 30, top: 50, bottom: 50 },
        xAxis: { type: 'category', data: m.months, axisLine: { lineStyle: { color: '#2a2d44' } }, axisLabel: { color: '#8a8db0', fontSize: 10, rotate: 45 } },
        yAxis: { type: 'value', name: 'conversations', nameTextStyle: { color: '#8a8db0', fontSize: 10 }, axisLine: { show: false }, axisLabel: { color: '#8a8db0', fontSize: 10 }, splitLine: { lineStyle: { color: '#2a2d44', type: 'dashed' } } },
        series: m.domains.map(d => ({
          name: d, type: 'line', stack: 'all', areaStyle: { opacity: 0.65 },
          emphasis: { focus: 'series' }, showSymbol: false, smooth: true,
          data: m.series[d],
        })),
      }, true);
    }

    function renderIdeas() {
      const ideas = D.topIdeas;
      const titles = ideas.map(i => i.title.length > 50 ? i.title.slice(0, 47) + '...' : i.title);
      const counts = ideas.map(i => i.mention_count);
      const colors = ideas.map(i => outcomeColor(i.status === 'done' ? 'produced' : i.status === 'stalled' ? 'looped' : 'resolved'));
      chart.setOption({
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis', axisPointer: { type: 'shadow' },
          backgroundColor: 'rgba(20,22,36,0.96)',
          borderColor: '#2a2d44',
          textStyle: { color: '#e8eaf6', fontSize: 12 },
          formatter: (params) => {
            const p = params[0];
            const i = ideas[p.dataIndex];
            return `<b>${escape(i.title)}</b><br/>mentioned ${fmt(i.mention_count)}x &middot; ${escape(i.status)}<br/>category: <span style="color:#4ad7ff">${escape(i.category)}</span><br/>tier: ${escape(i.tier)}`;
          },
        },
        grid: { left: 240, right: 30, top: 20, bottom: 20 },
        xAxis: { type: 'value', axisLine: { show: false }, axisLabel: { color: '#8a8db0', fontSize: 10 }, splitLine: { lineStyle: { color: '#2a2d44', type: 'dashed' } } },
        yAxis: { type: 'category', data: titles.slice().reverse(), inverse: false, axisLine: { lineStyle: { color: '#2a2d44' } }, axisLabel: { color: '#e8eaf6', fontSize: 11, width: 220, overflow: 'truncate' } },
        series: [{
          type: 'bar', data: counts.slice().reverse().map((v, i) => ({ value: v, itemStyle: { color: colors.slice().reverse()[i] } })),
          barWidth: 16, label: { show: true, position: 'right', color: '#8a8db0', fontSize: 10, formatter: '{c}' },
        }],
      }, true);
    }

    function renderTime() {
      const t = D.lengthByOutcome;
      const colors = t.outcomes.map(outcomeColor);
      chart.setOption({
        backgroundColor: 'transparent',
        color: colors,
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(20,22,36,0.96)', borderColor: '#2a2d44', textStyle: { color: '#e8eaf6', fontSize: 12 } },
        legend: { data: t.outcomes, textStyle: { color: '#8a8db0', fontSize: 11 }, top: 10, icon: 'circle', itemWidth: 10, itemHeight: 10 },
        grid: { left: 60, right: 30, top: 50, bottom: 40 },
        xAxis: { type: 'category', data: t.bins, name: 'words per conversation', nameLocation: 'middle', nameGap: 28, nameTextStyle: { color: '#8a8db0', fontSize: 10 }, axisLine: { lineStyle: { color: '#2a2d44' } }, axisLabel: { color: '#8a8db0', fontSize: 11 } },
        yAxis: { type: 'value', name: 'conversations', nameTextStyle: { color: '#8a8db0', fontSize: 10 }, axisLabel: { color: '#8a8db0', fontSize: 10 }, splitLine: { lineStyle: { color: '#2a2d44', type: 'dashed' } } },
        series: t.outcomes.map(o => ({
          name: o, type: 'bar', stack: 'total', emphasis: { focus: 'series' }, data: t.series[o],
        })),
      }, true);
    }

    function renderChart() {
      renderFilters();
      if (state.lens === 'map') renderMap();
      else if (state.lens === 'you') renderYou();
      else if (state.lens === 'ideas') renderIdeas();
      else if (state.lens === 'time') renderTime();
    }

    // ============ right rail ============

    function selectCluster(cid) {
      state.selectedCluster = cid;
      renderRailForCluster(cid);
    }

    function renderRailDefault() {
      state.selectedCluster = null;
      const header = document.getElementById('rail-header');
      const body = document.getElementById('rail-body');
      header.innerHTML = `<h2>top clusters</h2><h3>your mind, ranked by mass</h3><div class="rail-meta">click any cluster on the map -> drill in</div>`;
      const top = D.clusters.slice(0, 50);
      body.innerHTML = top.map(c => {
        const dom = clusterDominantDomain(c);
        return `<div class="convo-item cluster-row" data-cluster="${c.id}">
          <div class="title">${escape(c.name)}</div>
          <div class="meta">
            <span class="badge" style="background:${dominantColor(dom)}22; color:${dominantColor(dom)}">${escape(dom)}</span>
            <span>${fmt(c.msg_count)} msgs</span>
            <span>${fmt(c.convo_count)} convos</span>
            <span>${c.user_pct.toFixed(0)}% you</span>
          </div>
        </div>`;
      }).join('');
      body.querySelectorAll('.cluster-row').forEach(el => {
        el.addEventListener('click', () => selectCluster(parseInt(el.dataset.cluster, 10)));
      });
    }

    function renderRailForCluster(cid) {
      const c = D.clusters.find(x => x.id === cid);
      if (!c) return;
      const header = document.getElementById('rail-header');
      const body = document.getElementById('rail-body');
      const dom = clusterDominantDomain(c);
      const totalConvos = c.convo_count || 1;
      // domain breakdown bars
      const domEntries = Object.entries(c.domain_breakdown || {}).sort((a,b) => b[1] - a[1]).slice(0, 6);
      const outEntries = Object.entries(c.outcome_breakdown || {}).sort((a,b) => b[1] - a[1]);
      const domBreakdownHtml = `
        <div class="breakdown">
          ${domEntries.map(([k,v]) => `
            <div class="row">
              <div class="label">${escape(k)}</div>
              <div class="bar"><div style="width:${(v/totalConvos*100).toFixed(0)}%; background:${dominantColor(k)}"></div></div>
              <div class="count">${v}</div>
            </div>
          `).join('')}
        </div>
        <div class="breakdown" style="margin-top:6px">
          ${outEntries.map(([k,v]) => `
            <div class="row">
              <div class="label">${escape(k)}</div>
              <div class="bar"><div style="width:${(v/totalConvos*100).toFixed(0)}%; background:${outcomeColor(k)}"></div></div>
              <div class="count">${v}</div>
            </div>
          `).join('')}
        </div>
      `;
      header.innerHTML = `
        <h2>cluster ${cid} &middot; <span style="color:${dominantColor(dom)}; cursor:pointer" id="back-to-all">< back to all</span></h2>
        <h3>${escape(c.name)}</h3>
        <div class="rail-meta">
          <span>${fmt(c.msg_count)} msgs</span>
          <span>${fmt(c.convo_count)} convos</span>
          <span>${c.user_pct.toFixed(0)}% you</span>
        </div>
        ${domBreakdownHtml}
      `;
      document.getElementById('back-to-all').addEventListener('click', renderRailDefault);
      // convos (most recent 50)
      const convos = c.convo_ids.map(cid => Object.assign({ id: cid }, D.convos[cid])).filter(x => x.title);
      body.innerHTML = convos.length === 0 ? `<div class="empty-state">no classified conversations in this cluster</div>`
        : convos.map(co => `
          <div class="convo-item convo-row" data-convo="${escape(co.id)}">
            <div class="title">${escape(co.title)}</div>
            <div class="meta">
              <span class="badge outcome-${escape(co.outcome)}">${escape(co.outcome)}</span>
              <span>${escape(co.domain)}</span>
              <span>${escape(co.date)}</span>
              <span>${fmt(co.word_count)} words</span>
            </div>
          </div>
        `).join('');
      body.querySelectorAll('.convo-row').forEach(el => {
        el.addEventListener('click', () => showConvoModal(el.dataset.convo));
      });
    }

    // ============ modal ============

    function showConvoModal(convoId) {
      const c = D.convos[convoId];
      if (!c) return;
      document.getElementById('modal-title').textContent = c.title;
      document.getElementById('modal-meta').innerHTML = `
        <span>${escape(c.date)}</span>
        <span>domain: <b style="color:${dominantColor(c.domain)}">${escape(c.domain)}</b></span>
        <span>outcome: <b style="color:${outcomeColor(c.outcome)}">${escape(c.outcome)}</b></span>
        <span>${fmt(c.word_count)} words</span>
        <span>trajectory: ${escape(c.trajectory)}</span>
      `;
      const quotes = D.topQuotes[convoId] || [];
      const body = document.getElementById('modal-body');
      if (quotes.length > 0) {
        body.innerHTML = `<h3>representative quotes (${quotes.length})</h3>` +
          quotes.map(q => `<div class="quote">${escape(q)}</div>`).join('');
      } else {
        body.innerHTML = `<h3>representative quotes</h3>
          <div class="quote no-quote">no ranked quotes extracted for this conversation. use the CLI to read the full text.</div>`;
      }
      document.getElementById('modal-cmd').textContent = `python atlas_query.py text --convo "${convoId}"`;
      document.getElementById('modal').classList.add('show');
    }

    function showIdeaModal(idea) {
      document.getElementById('modal-title').textContent = idea.title;
      document.getElementById('modal-meta').innerHTML = `
        <span>category: <b style="color:#4ad7ff">${escape(idea.category)}</b></span>
        <span>status: <b>${escape(idea.status)}</b></span>
        <span>tier: <b>${escape(idea.tier)}</b></span>
        <span>mentioned ${fmt(idea.mention_count)}x</span>
        <span>priority: ${idea.priority_score}</span>
      `;
      document.getElementById('modal-body').innerHTML = `<h3>idea card</h3>
        <div class="quote">This is a canonical idea cluster (canonical_id ${escape(idea.id)}). The full version-timeline + parent/child relationships + alignment scoring are in <code>idea_registry.json</code>.</div>`;
      document.getElementById('modal-cmd').textContent = `python atlas_query.py inspect --idea "${idea.id}"`;
      document.getElementById('modal').classList.add('show');
    }

    document.getElementById('modal-close').addEventListener('click', () => {
      document.getElementById('modal').classList.remove('show');
    });
    document.getElementById('modal').addEventListener('click', (e) => {
      if (e.target.id === 'modal') document.getElementById('modal').classList.remove('show');
    });

    // ============ tabs ============

    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        state.lens = tab.dataset.lens;
        renderChart();
      });
    });

    // ============ init ============

    document.getElementById('subtitle').textContent =
      `${fmt(Object.keys(D.convos).length)} conversations  ·  ${fmt(D.clusters.length)} clusters  ·  ${D.monthly.months[0]} -> ${D.monthly.months[D.monthly.months.length - 1]}`;

    renderRailDefault();
    renderChart();
  </script>
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--classifications", type=Path,
                   default=BASE / "conversation_classifications.json")
    p.add_argument("--registry", type=Path,
                   default=BASE / "idea_registry.json")
    p.add_argument("--clusters", type=Path,
                   default=BASE / "atlas_clusters.json")
    p.add_argument("--out", type=Path, default=BASE / "atlas_explorer.html")
    args = p.parse_args()

    print(f"Reading {args.classifications.name} ...")
    classifications = _load_classifications(args.classifications)
    print(f"  {len(classifications):,} classified conversations")

    print(f"Reading {args.registry.name} ...")
    registry = _load_registry(args.registry)
    print(f"  {registry['metadata']['total_ideas']} canonical ideas")

    print(f"Reading {args.clusters.name} ...")
    clusters_data = _load_clusters(args.clusters)
    print(f"  {clusters_data['cluster_count']} clusters / {clusters_data['total_messages']:,} msgs")

    print("\nBuilding views ...")
    convo_index = _build_convo_index(classifications)
    print(f"  convo_index: {len(convo_index):,} entries")

    cluster_summary = _build_cluster_summary(clusters_data, convo_index)
    print(f"  cluster_summary: {len(cluster_summary):,} entries")

    monthly = _build_monthly_by_domain(classifications)
    print(f"  monthly: {len(monthly['months'])} months x {len(monthly['domains'])} domains")

    top_ideas = _build_top_ideas(registry, n=30)
    print(f"  top_ideas: {len(top_ideas)}")

    length = _build_length_by_outcome(classifications)
    print(f"  length_by_outcome: {len(length['bins'])} bins x {len(length['outcomes'])} outcomes")

    top_quotes = _build_top_quotes_per_cluster(registry, cluster_summary)
    print(f"  top_quotes (per-convo): {len(top_quotes):,} convos with quotes")

    payload = {
        "clusters": cluster_summary,
        "convos": convo_index,
        "monthly": monthly,
        "topIdeas": top_ideas,
        "lengthByOutcome": length,
        "topQuotes": top_quotes,
    }
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    # CRITICAL: when embedding JSON in a <script> tag, escape any character
    # sequences that would close the script tag or break out of HTML comment
    # context. A user message containing literal "</script>" or "-->" would
    # otherwise let raw conversation text leak into the rendered DOM.
    # See ~/.claude/rules/common/code-as-furniture.md.
    blob = (
        blob
        .replace("</", "<\\/")        # </script>, </style>, etc.
        .replace("<!--", "<\\!--")
        .replace("-->", "--\\>")
        .replace(" ", "\\u2028")  # JS line separator (breaks JS parse)
        .replace(" ", "\\u2029")  # JS paragraph separator
    )
    html = HTML_TEMPLATE.replace("{{DATA_JSON}}", blob)

    print(f"\nWriting {args.out.name} ...")
    args.out.write_text(html, encoding="utf-8")
    print(f"  {args.out.stat().st_size / 1024 / 1024:.2f} MB")

    print("\nDone. Open with:")
    print(f"  start {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
build_cognitive_map.py — Phase 1 Cognitive Topography

Reads 1,397 conversation embeddings from results.db, computes PCA projections,
KMeans clusters, similarity graph, temporal drift, and recurrence patterns.
Outputs a standalone interactive HTML dashboard (cognitive_map.html).

No new pip installs required. Uses numpy, sklearn, sqlite3 only.

Usage:
    python build_cognitive_map.py
"""

import json, sqlite3, numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

BASE = Path(__file__).parent.resolve()
DB_FILE = BASE / "results.db"
OUT_FILE = BASE / "cognitive_map.html"

N_CLUSTERS = 8
SIMILARITY_FLOOR = 0.82
RECURRENCE_MIN_DAYS = 30
RECURRENCE_MIN_SIM = 0.75
DRIFT_PIVOT_SIGMA = 1.5


# ── Step 1: Data Loading ─────────────────────────────────────────────────────

def load_data():
    con = sqlite3.connect(str(DB_FILE))
    cur = con.cursor()

    # Check embeddings exist
    count = cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    if count == 0:
        print("ERROR: No embeddings found. Run: python init_embeddings.py")
        exit(1)

    # Master query
    rows = cur.execute("""
        SELECT e.convo_id, e.embedding, e.text_length, ct.title, c.date,
               COALESCE(m.total_words, 0) as word_count
        FROM embeddings e
        LEFT JOIN convo_titles ct ON e.convo_id = ct.convo_id
        LEFT JOIN convo_time c ON e.convo_id = c.convo_id
        LEFT JOIN (
            SELECT convo_id, SUM(words) as total_words
            FROM messages GROUP BY convo_id
        ) m ON e.convo_id = m.convo_id
        ORDER BY CAST(e.convo_id AS INTEGER)
    """).fetchall()

    convo_ids, embeddings_list, titles, dates, text_lengths, word_counts = [], [], [], [], [], []

    for cid, emb_blob, text_len, title, date, wc in rows:
        convo_ids.append(cid)
        embeddings_list.append(np.frombuffer(emb_blob, dtype=np.float32))
        titles.append(title if title else "(untitled)")
        dates.append(date if date else "")
        text_lengths.append(text_len if text_len else 0)
        word_counts.append(wc if wc else 0)

    # Keywords lookup (top keywords per convo, concatenated)
    kw_rows = cur.execute("""
        SELECT convo_id, GROUP_CONCAT(topic, ', ')
        FROM (SELECT convo_id, topic FROM topics ORDER BY convo_id, weight DESC)
        GROUP BY convo_id
    """).fetchall()
    keywords = {cid: kws for cid, kws in kw_rows}

    con.close()

    return {
        "convo_ids": convo_ids,
        "matrix": np.array(embeddings_list),
        "titles": titles,
        "dates": dates,
        "text_lengths": text_lengths,
        "word_counts": word_counts,
        "keywords": keywords,
    }


# ── Step 2: PCA ──────────────────────────────────────────────────────────────

def compute_pca(matrix):
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(matrix)
    explained = pca.explained_variance_ratio_
    print(f"  PCA variance explained: {explained[0]:.3f} + {explained[1]:.3f} = {sum(explained):.3f}")
    return coords


# ── Step 3: KMeans ────────────────────────────────────────────────────────────

def compute_clusters(matrix):
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    labels = kmeans.fit_predict(matrix)
    return labels


# ── Step 4: Similarity Graph ─────────────────────────────────────────────────

def compute_similarity_graph(sim_matrix):
    n = sim_matrix.shape[0]
    upper_tri = sim_matrix[np.triu_indices(n, k=1)]

    percentile_threshold = float(np.percentile(upper_tri, 99))
    threshold = max(percentile_threshold, SIMILARITY_FLOOR)

    row_idx, col_idx = np.where(
        (sim_matrix > threshold) &
        (np.triu(np.ones((n, n), dtype=bool), k=1))
    )

    edges = []
    degree = np.zeros(n, dtype=int)
    for i, j in zip(row_idx, col_idx):
        edges.append({"s": int(i), "t": int(j), "v": float(round(sim_matrix[i, j], 4))})
        degree[i] += 1
        degree[j] += 1

    isolated_count = int(np.sum(degree == 0))

    return {
        "threshold": round(threshold, 4),
        "edges": edges,
        "degree": degree.tolist(),
        "edge_count": len(edges),
        "isolated_count": isolated_count,
    }


# ── Step 5: Temporal Drift ───────────────────────────────────────────────────

def compute_temporal_drift(matrix, dates):
    # Group by ISO week
    weekly = defaultdict(list)
    for i, d in enumerate(dates):
        if not d:
            continue
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            weekly[dt.strftime("%Y-W%W")].append(i)
        except ValueError:
            continue

    sorted_weeks = sorted(weekly.keys())
    if len(sorted_weeks) < 3:
        return {"weeks": [], "drift": [], "counts": [], "pivots": [], "mean": 0}

    centroids, week_labels, week_counts = [], [], []
    for wk in sorted_weeks:
        indices = weekly[wk]
        centroids.append(matrix[indices].mean(axis=0))
        week_labels.append(wk)
        week_counts.append(len(indices))

    drift = []
    for i in range(1, len(centroids)):
        a, b = centroids[i], centroids[i - 1]
        sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        drift.append(round(sim, 4))

    # Detect pivots
    pivots = []
    if drift:
        mean_d = float(np.mean(drift))
        std_d = float(np.std(drift))
        pivot_line = mean_d - DRIFT_PIVOT_SIGMA * std_d
        for i, score in enumerate(drift):
            if score < pivot_line:
                pivots.append({"week": week_labels[i + 1], "score": score})
    else:
        mean_d = 0.0

    return {
        "weeks": week_labels[1:],
        "drift": drift,
        "counts": week_counts[1:],
        "pivots": pivots,
        "mean": round(mean_d, 4),
    }


# ── Step 6: Recurrence Scanner ───────────────────────────────────────────────

def compute_recurrence(sim_matrix, dates, titles):
    n = sim_matrix.shape[0]

    parsed = []
    for d in dates:
        try:
            parsed.append(datetime.strptime(d, "%Y-%m-%d"))
        except (ValueError, TypeError):
            parsed.append(None)

    recurrence_count = np.zeros(n, dtype=int)
    seen_pairs = set()
    pairs = []

    for i in range(n):
        if parsed[i] is None:
            continue
        sims = sim_matrix[i].copy()
        sims[i] = -1
        top5 = np.argsort(sims)[-5:][::-1]

        for j in top5:
            if parsed[j] is None:
                continue
            days = abs((parsed[i] - parsed[j]).days)
            s = float(sims[j])
            if days > RECURRENCE_MIN_DAYS and s > RECURRENCE_MIN_SIM:
                key = (min(i, j), max(i, j))
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    pairs.append({
                        "a": int(i), "b": int(j),
                        "ta": titles[i][:60], "tb": titles[j][:60],
                        "da": dates[i], "db": dates[j],
                        "sim": round(s, 4), "days": days,
                    })
                recurrence_count[i] += 1

    # Top recurring conversations
    top = sorted(
        [(i, int(recurrence_count[i]), titles[i], dates[i])
         for i in range(n) if recurrence_count[i] > 0],
        key=lambda x: x[1], reverse=True
    )[:30]

    return {
        "pairs": pairs,
        "total_pairs": len(pairs),
        "top": [{"idx": i, "count": c, "title": t[:50], "date": d} for i, c, t, d in top],
    }


# ── Step 7: HTML Generation ──────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Cognitive Topography</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e5e5e5}
header{padding:20px 24px 0;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
header h1{font-size:22px;font-weight:700;letter-spacing:-0.5px}
header .sub{color:#888;font-size:12px}
.stats{display:flex;gap:12px;padding:12px 24px;flex-wrap:wrap}
.stat{background:#111118;border:1px solid #2a2a3a;border-radius:8px;padding:8px 14px;font-size:12px}
.stat b{color:#6366f1;font-size:16px;display:block;margin-bottom:2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:0 24px 24px}
.panel{background:#111118;border:1px solid #2a2a3a;border-radius:12px;padding:16px;overflow:hidden}
.panel-title{font-size:13px;font-weight:600;color:#aaa;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
@media(max-width:1000px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>Cognitive Topography</h1>
  <span class="sub">__SUBTITLE__</span>
</header>

<div class="stats" id="stats-bar"></div>

<div class="grid">
  <div class="panel">
    <div class="panel-title">1. Cognitive Topography (PCA 2D)</div>
    <div id="chart-topo"></div>
  </div>
  <div class="panel">
    <div class="panel-title">2. Similarity Network</div>
    <div id="chart-sim"></div>
  </div>
  <div class="panel">
    <div class="panel-title">3. Temporal Drift</div>
    <div id="chart-drift"></div>
  </div>
  <div class="panel">
    <div class="panel-title">4. Recurrence Scanner</div>
    <div id="chart-recur"></div>
  </div>
</div>

<script>
const D = __DATA_PAYLOAD__;

const COLORS = ['#6366f1','#22d3ee','#f59e0b','#ef4444','#10b981','#ec4899','#8b5cf6','#f97316'];
const LAYOUT_BASE = {
  paper_bgcolor:'rgba(0,0,0,0)',
  plot_bgcolor:'rgba(17,17,24,1)',
  font:{color:'#ccc',size:11},
  margin:{l:50,r:20,t:30,b:50},
  hovermode:'closest',
};

// ── Stats Bar ──
(function(){
  const s = D.stats;
  const bar = document.getElementById('stats-bar');
  const items = [
    ['Conversations', s.count],
    ['Clusters', s.clusters],
    ['Edges', s.edges + ' (≥' + s.threshold + ')'],
    ['Isolated', s.isolated],
    ['Pivots', s.pivots],
    ['Recurrence Pairs', s.recurrence_pairs],
  ];
  bar.innerHTML = items.map(([k,v])=>'<div class="stat"><b>'+v+'</b>'+k+'</div>').join('');
})();

// ── Chart 1: Topography ──
(function(){
  const t = D.topography;
  const traces = [];
  for(let c=0;c<__N_CLUSTERS__;c++){
    const mask = t.clusters.map(cl=>cl===c);
    const idx = t.clusters.map((_,i)=>i).filter(i=>mask[i]);
    if(idx.length===0) continue;
    traces.push({
      x: idx.map(i=>t.x[i]),
      y: idx.map(i=>t.y[i]),
      text: idx.map(i=>
        '<b>'+t.titles[i]+'</b><br>Date: '+t.dates[i]+
        '<br>Cluster: '+c+'<br>Keywords: '+t.keywords[i]
      ),
      mode:'markers',
      type:'scatter',
      name:'Cluster '+c+' ('+idx.length+')',
      marker:{
        color:COLORS[c%COLORS.length],
        size:idx.map(i=>t.sizes[i]),
        sizemode:'area',
        sizeref:2*Math.max(...t.sizes)/(35*35),
        opacity:0.75,
        line:{width:0.5,color:'rgba(255,255,255,0.15)'}
      },
      hovertemplate:'%{text}<extra></extra>',
    });
  }
  Plotly.newPlot('chart-topo',traces,Object.assign({},LAYOUT_BASE,{
    xaxis:{title:'PC1',showgrid:false,zeroline:false,color:'#666'},
    yaxis:{title:'PC2',showgrid:false,zeroline:false,color:'#666'},
    legend:{orientation:'h',y:-0.18,font:{size:10}},
    height:480,
  }),{responsive:true});
})();

// ── Chart 2: Similarity Network ──
(function(){
  const s = D.similarity;
  // edges as lines with null separators
  const ex=[],ey=[];
  for(const e of s.edges){
    ex.push(s.x[e.s],s.x[e.t],null);
    ey.push(s.y[e.s],s.y[e.t],null);
  }
  const edgeTrace = {
    x:ex, y:ey, mode:'lines', type:'scatter',
    line:{color:'rgba(99,102,241,0.12)',width:0.5},
    hoverinfo:'skip', showlegend:false,
  };
  const nodeTrace = {
    x:s.x, y:s.y,
    text:s.titles.map((t,i)=>
      '<b>'+t+'</b><br>Degree: '+s.degree[i]+'<br>Cluster: '+s.clusters[i]
    ),
    mode:'markers', type:'scatter',
    marker:{
      color:s.clusters.map(c=>COLORS[c%COLORS.length]),
      size:s.degree.map(d=>Math.max(3,Math.sqrt(d)*3.5)),
      opacity:0.85,
      line:{width:0.3,color:'rgba(255,255,255,0.1)'}
    },
    hovertemplate:'%{text}<extra></extra>',
    showlegend:false,
  };
  Plotly.newPlot('chart-sim',[edgeTrace,nodeTrace],Object.assign({},LAYOUT_BASE,{
    xaxis:{showgrid:false,zeroline:false,showticklabels:false},
    yaxis:{showgrid:false,zeroline:false,showticklabels:false},
    annotations:[{
      text:s.edge_count+' edges | threshold ≥'+s.threshold+' | '+s.isolated_count+' isolated',
      showarrow:false, x:0.5, y:1.02, xref:'paper', yref:'paper',
      font:{color:'#666',size:10}
    }],
    height:480,
  }),{responsive:true});
})();

// ── Chart 3: Temporal Drift ──
(function(){
  const t = D.temporal;
  if(!t.weeks.length){
    document.getElementById('chart-drift').innerHTML='<p style="color:#666;padding:40px">Insufficient date data for temporal analysis.</p>';
    return;
  }
  const mainTrace = {
    x:t.weeks, y:t.drift,
    type:'scatter', mode:'lines+markers',
    line:{color:'#6366f1',width:2},
    marker:{size:4,color:'#6366f1'},
    name:'Weekly Similarity',
    hovertemplate:'Week: %{x}<br>Similarity: %{y:.4f}<extra></extra>',
  };
  const meanTrace = {
    x:[t.weeks[0],t.weeks[t.weeks.length-1]],
    y:[t.mean,t.mean],
    mode:'lines', line:{color:'#555',width:1,dash:'dash'},
    name:'Mean ('+t.mean+')', showlegend:true,
  };
  const annotations = t.pivots.map(p=>({
    x:p.week, y:p.score,
    text:'PIVOT', showarrow:true, arrowhead:2,
    font:{color:'#ef4444',size:9}, arrowcolor:'#ef4444', ay:-30,
  }));
  Plotly.newPlot('chart-drift',[mainTrace,meanTrace],Object.assign({},LAYOUT_BASE,{
    xaxis:{title:'Week',tickangle:-45,color:'#666',showgrid:false},
    yaxis:{title:'Cosine Similarity (adjacent weeks)',color:'#666',gridcolor:'#1a1a2a'},
    annotations:annotations,
    legend:{orientation:'h',y:1.08,font:{size:10}},
    height:400,
  }),{responsive:true});
})();

// ── Chart 4: Recurrence Scanner ──
(function(){
  const r = D.recurrence;
  const top = r.top.slice(0,25);
  if(!top.length){
    document.getElementById('chart-recur').innerHTML='<p style="color:#666;padding:40px">No recurrences detected (>30 days apart, >0.75 similarity).</p>';
    return;
  }
  const trace = {
    y:top.map(t=>t.title),
    x:top.map(t=>t.count),
    type:'bar', orientation:'h',
    marker:{
      color:top.map(t=>t.count),
      colorscale:[[0,'#1e1b4b'],[0.5,'#4338ca'],[1,'#6366f1']],
    },
    hovertemplate:'<b>%{y}</b><br>Recurrences: %{x}<br>Date: %{customdata}<extra></extra>',
    customdata:top.map(t=>t.date),
  };
  Plotly.newPlot('chart-recur',[trace],Object.assign({},LAYOUT_BASE,{
    xaxis:{title:'Recurrence Count',color:'#666',gridcolor:'#1a1a2a'},
    yaxis:{autorange:'reversed',automargin:true,color:'#ccc',tickfont:{size:10}},
    height:Math.max(400, top.length*22+80),
    margin:{l:220,r:20,t:20,b:50},
  }),{responsive:true});
})();
</script>
</body>
</html>"""


def build_html(data, pca_coords, labels, sim_graph, temporal, recurrence):
    # Normalize marker sizes (5–40)
    tl = np.array(data["text_lengths"], dtype=float)
    if tl.max() > tl.min():
        sizes = (5 + 35 * (tl - tl.min()) / (tl.max() - tl.min())).tolist()
    else:
        sizes = [15.0] * len(tl)

    payload = {
        "stats": {
            "count": len(data["convo_ids"]),
            "clusters": N_CLUSTERS,
            "edges": sim_graph["edge_count"],
            "threshold": sim_graph["threshold"],
            "isolated": sim_graph["isolated_count"],
            "pivots": len(temporal["pivots"]),
            "recurrence_pairs": recurrence["total_pairs"],
        },
        "topography": {
            "x": pca_coords[:, 0].tolist(),
            "y": pca_coords[:, 1].tolist(),
            "clusters": labels.tolist(),
            "titles": data["titles"],
            "dates": data["dates"],
            "keywords": [data["keywords"].get(cid, "") for cid in data["convo_ids"]],
            "sizes": [round(s, 1) for s in sizes],
        },
        "similarity": {
            "x": pca_coords[:, 0].tolist(),
            "y": pca_coords[:, 1].tolist(),
            "edges": sim_graph["edges"],
            "degree": sim_graph["degree"],
            "clusters": labels.tolist(),
            "titles": data["titles"],
            "threshold": sim_graph["threshold"],
            "edge_count": sim_graph["edge_count"],
            "isolated_count": sim_graph["isolated_count"],
        },
        "temporal": temporal,
        "recurrence": recurrence,
    }

    payload_json = json.dumps(payload, ensure_ascii=False)
    n = len(data["convo_ids"])
    subtitle = f"{n} conversations | 384-dim embeddings | Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    page = HTML_TEMPLATE.replace("__DATA_PAYLOAD__", payload_json)
    page = page.replace("__SUBTITLE__", subtitle)
    page = page.replace("__N_CLUSTERS__", str(N_CLUSTERS))

    OUT_FILE.write_text(page, encoding="utf-8")
    print(f"  Output: {OUT_FILE} ({len(payload_json) // 1024} KB payload)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading data from results.db...")
    data = load_data()
    n = len(data["convo_ids"])
    print(f"  Loaded {n} conversations ({data['matrix'].shape[1]}D embeddings)")

    print("Computing PCA projection (384D -> 2D)...")
    pca_coords = compute_pca(data["matrix"])

    print("Computing KMeans clusters (k={})...".format(N_CLUSTERS))
    labels = compute_clusters(data["matrix"])
    for c in range(N_CLUSTERS):
        print(f"  Cluster {c}: {int(np.sum(labels == c))} conversations")

    print("Computing cosine similarity matrix ({}x{})...".format(n, n))
    sim_matrix = cosine_similarity(data["matrix"])

    print("Extracting similarity graph...")
    sim_graph = compute_similarity_graph(sim_matrix)
    print(f"  Threshold: {sim_graph['threshold']}")
    print(f"  Edges: {sim_graph['edge_count']}")
    print(f"  Isolated nodes: {sim_graph['isolated_count']}")

    print("Computing temporal drift...")
    temporal = compute_temporal_drift(data["matrix"], data["dates"])
    print(f"  Weeks analyzed: {len(temporal['weeks'])}")
    print(f"  Cognitive pivots: {len(temporal['pivots'])}")

    print("Scanning for recurrences (>{} days, >{} similarity)...".format(
        RECURRENCE_MIN_DAYS, RECURRENCE_MIN_SIM))
    recurrence = compute_recurrence(sim_matrix, data["dates"], data["titles"])
    print(f"  Recurrence pairs: {recurrence['total_pairs']}")
    print(f"  Top recurring: {recurrence['top'][0]['title'] if recurrence['top'] else 'none'}")

    print("Building HTML...")
    build_html(data, pca_coords, labels, sim_graph, temporal, recurrence)

    print("Done. Open cognitive_map.html in a browser.")


if __name__ == "__main__":
    main()

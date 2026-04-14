# Pre Atlas -- System Map

> A layered overview for someone joining the project. Start with the "what" and "why," then drill into the "how."

---

## 1. What This System Does

Pre Atlas is a personal behavioral governance system. It reads every message from ~1,400 AI conversations (~94K messages), analyzes thinking patterns, and tells you what to focus on.

The core problem it solves: you have hundreds of ideas, dozens of open projects, and no reliable way to decide what matters. Pre Atlas replaces gut-feel prioritization with data-driven directives.

It answers three questions every day:

1. **What topics do I actually spend time on?** (Cognitive Atlas -- clustering)
2. **Which ideas have real business value?** (Leverage scoring)
3. **What should I do right now?** (Mode system + daily directive)

The system runs entirely locally. No cloud, no server, no accounts. Python scripts + SQLite + JSON files.

---

## 2. What It Produces

| Output | What It Is | Who Reads It |
|--------|-----------|--------------|
| `cognitive_atlas.html` | Full-viewport interactive dashboard: 84K-point scatter plot (Plotly WebGL), force-directed cluster graph (Sigma.js), leverage ranking, cluster inspector, ROI analysis, and role distribution — all in a single self-contained HTML file (~5.9 MB) | Human (browser) |
| `leverage_map.json` | Ranked list of conversation clusters scored by business value (5 metrics: revenue potential, asset proximity, completion rate, recency, size) | Scripts + CycleBoard |
| `daily_payload.json` | Today's mode (RECOVER/CLOSURE/BUILD/etc.), risk level, primary action, and reasoning | CycleBoard |
| `IDEA_REGISTRY.md` | Prioritized list of extracted ideas with tiers (execute now, next up, backlog) | Human + Agents |
| `dashboard.html` | Analytics on conversation patterns, closure ratios, open loops, topic distribution | Human (browser) |
| `cognitive_state.json` | Snapshot of current cognitive metrics for the CycleBoard planning interface | CycleBoard app |

---

## 3. How Data Flows

```
Raw Conversations (memory_db.json, ~140MB)
    |
    v
[init_results_db.py] --> results.db (messages, topics, timestamps)
    |
    v
[init_titles.py + init_convo_time.py] --> conversation metadata
    |
    v
[init_embeddings.py] --> 384-dim vectors per message (all-MiniLM-L6-v2)
    |
    v
[build_cognitive_atlas.py] --> UMAP + HDBSCAN --> cognitive_atlas.html
    |
    v
[cluster_leverage_map.py] --> 5 metrics per cluster --> leverage_map.json
    |
    v
[Agent Pipeline] --> excavate ideas --> dedup --> classify --> prioritize
    |                                                            |
    v                                                            v
[Governors] --> daily brief, weekly packet          IDEA_REGISTRY.md
    |
    v
[CycleBoard + Dashboard] --> human-facing planning interfaces
```

Each arrow is a Python script that reads files/DB and writes files/DB. No shared state between steps -- just JSON and SQLite.

---

## 4. The Cognitive Atlas (Deep Dive)

This is the visual centerpiece. It takes 84,848 message embeddings and produces an interactive HTML dashboard.

**Pipeline:**
1. Load 384-dimensional sentence embeddings from SQLite
2. UMAP reduces 384D to 2D (cosine metric, 30 neighbors)
3. HDBSCAN finds density-based clusters (~207 clusters, ~31% noise)
4. Build 5 toggle layers: Cluster, Role (user/assistant), Time, Conversation, Leverage
5. Build force-directed graph: nodes = clusters, edges = conversation overlap + cosine similarity
6. Embed everything into a single self-contained HTML file

**Visualization stack:**
- Plotly (WebGL/scattergl) renders 84K points as an interactive scatter plot
- Sigma.js + Graphology renders the cluster relationship graph
- 6 view modes toggled by buttons: Cluster, Role, Time, Conversation, Leverage, Graph

**Key files (after refactor):**

| File | Purpose |
|------|---------|
| `build_cognitive_atlas.py` | Entry point -- thin orchestrator (~75 lines) |
| `atlas_data.py` | Loads messages + embeddings from `results.db` |
| `atlas_projection.py` | UMAP dimensionality reduction + HDBSCAN clustering |
| `atlas_layers.py` | Builds toggle layer arrays + cluster summary stats |
| `atlas_layout.py` | ForceAtlas2 force-directed layout (pure NumPy) |
| `atlas_graph.py` | Constructs graph nodes/edges with dual edge strategy |
| `atlas_render.py` | Assembles JSON payload, fills HTML template |
| `atlas_template.html` | HTML/CSS/JS dashboard template (viewport-governed flex layout, Plotly + Sigma.js) |

**Dashboard UI Architecture (`atlas_template.html`):**

The template implements a viewport-governed flex layout with scroll isolation:

```
<body>                          display:flex; flex-direction:column; overflow:hidden
  <header>                      flex-shrink:0
  <div.stats>                   flex-shrink:0  (6 stat cards)
  <div.controls>                flex-shrink:0  (mode toggle + 5 layer buttons)
  <div.main-area>               flex:1; overflow:hidden; display:flex (row)
    <div.atlas-box>             flex:1; overflow:hidden
      #atlas-chart              Plotly scattergl (container-bound, no hardcoded height)
      #graph-container          Sigma.js (100% width/height)
    <div.sidebar>               width:420px; display:block; overflow-y:auto (SOLE SCROLLER)
      #lev-panel                Leverage Ranking table (max-height:260px, internal scroll)
      #insp-panel               Cluster Inspector (metrics, n-grams, central messages)
      #summary-panel            Cluster Summary table (max-height:300px, internal scroll)
      #roi-panel                Cognitive ROI by revenue tag
      #av-panel                 Asset Vectors by type
      Role Distribution         Plotly bar chart (User/Assistant/Tool)
```

Key design decisions:
- `html,body` set to `height:100%; overflow:hidden` — no global scrollbar
- Only the sidebar scrolls (`overflow-y:auto`); everything else is `overflow:hidden`
- Plotly chart dimensions computed from `.atlas-box.clientWidth/clientHeight` via `getChartLayout()` — no hardcoded pixel heights
- `window.resize` event triggers `Plotly.relayout()` and `sigmaInst.refresh()`
- Collapsible panels via `togglePanel()` — click title to expand/collapse, auto-expand on cluster inspect
- Panels with `max-height` constraints (`#lev-panel`, `#summary-panel`) use `overflow-y:auto` for internal scrolling
- Responsive breakpoint at ≤1200px switches to column layout (sidebar below at 50vh)

---

## 5. The Mode System

Pre Atlas has 6 behavioral modes arranged as a progression:

```
RECOVER --> CLOSURE --> MAINTENANCE --> BUILD --> COMPOUND --> SCALE
```

The system determines which mode you're in based on 5 signals:
- Sleep / energy (are you functional?)
- Open loops (how many unfinished things?)
- Assets shipped (have you completed anything recently?)
- Deep work hours (are you doing focused work?)
- Revenue signals (is anything generating money?)

Each mode constrains what actions are "legal." In RECOVER mode, the only legal action is rest. In BUILD mode, you can start new projects. The system tells you your mode each morning via the daily directive.

This logic lives in `delta-kernel` (TypeScript/Express service, port 3001) which is separate from `cognitive-sensor` but consumes its data.

---

## 6. The Agent Pipeline

8 specialized agents process ideas extracted from conversations:

| Agent | Role |
|-------|------|
| `agent_excavator.py` | Extracts raw ideas from conversation text |
| `agent_deduplicator.py` | Merges duplicate/similar ideas |
| `agent_classifier.py` | Categorizes ideas (product, content, system, etc.) |
| `agent_classifier_convo.py` | Classifies entire conversations by type |
| `agent_orchestrator.py` | Routes ideas through the pipeline |
| `agent_reporter.py` | Generates human-readable summaries |
| `agent_synthesizer.py` | Combines insights across clusters |
| `agent_book_miner.py` | Extracts actionable frameworks from book discussions |

Run them all: `python run_agents.py`

---

## 7. Technical Architecture

**Stack:**
- Python 3.13 + SQLite (no server, no cloud)
- `all-MiniLM-L6-v2` for 384-dim sentence embeddings
- UMAP for dimensionality reduction
- HDBSCAN for density-based clustering
- ForceAtlas2 (custom NumPy implementation) for graph layout
- Plotly WebGL for 84K-point scatter rendering
- Sigma.js + Graphology for graph visualization

**Architecture style:** Flat scripts. No Python packages, no `__init__.py`, no framework. Each script imports siblings directly and runs independently. Communication between stages is via JSON files and SQLite -- never shared memory or running processes.

**Why this works:** The system processes data in batches (daily/weekly), not in real-time. A simple pipeline of scripts is easier to debug, modify, and reason about than a microservice architecture. Each script can be run and tested independently.

**Database:** Single SQLite file (`results.db`) with tables:
- `message_embeddings` -- one row per message with embedding blob
- `convo_titles` -- conversation ID to title mapping
- `convo_time` -- conversation timestamps
- Various topic/cluster tables

---

## 8. How to Run Things

**First-time setup:**
```bash
cd services/cognitive-sensor
pip install -r requirements.txt
```

**Initialize database (run once, or when source data changes):**
```bash
python init_results_db.py       # Parse memory_db.json into SQLite
python init_titles.py           # Extract conversation titles
python init_convo_time.py       # Extract timestamps
python init_embeddings.py       # Generate 384D embeddings (slow, ~20 min)
```

**Generate the atlas:**
```bash
python build_cognitive_atlas.py  # UMAP + HDBSCAN + HTML (~60s)
```

**Run leverage scoring:**
```bash
python cluster_leverage_map.py   # Score clusters by business value
```

**Run agent pipeline:**
```bash
python run_agents.py             # Extract + classify + prioritize ideas
```

**Run governance:**
```bash
python run_daily.py              # Daily directive
python run_weekly.py             # Weekly review packet
```

**Run tests:**
```bash
python -m pytest tests/ -m "not slow" -v    # Fast tests (~2s)
python -m pytest tests/ -v                  # All tests including UMAP/HDBSCAN
```

---

## 9. Key Concepts Glossary

| Term | Meaning |
|------|---------|
| **Embedding** | A 384-number vector representing the meaning of a message. Similar messages have similar vectors. |
| **UMAP** | Algorithm that compresses 384 dimensions down to 2 so you can plot messages on a flat surface. Preserves neighborhood structure. |
| **HDBSCAN** | Clustering algorithm that finds groups of nearby points. Doesn't need you to specify how many clusters -- it discovers them. Also identifies "noise" (messages that don't belong to any cluster). |
| **Leverage score** | A composite metric (0-100) measuring how much business value a conversation cluster has. Combines revenue potential, asset proximity, completion rate, recency, and size. |
| **ForceAtlas2** | Physics simulation for graph layout. Nodes repel each other (springs), edges attract connected nodes. Produces visually intuitive cluster relationship graphs. |
| **Mode** | Your current behavioral state (RECOVER through SCALE). Determines what the system recommends you do today. |
| **Delta-kernel** | The TypeScript state engine that tracks modes, tasks, and behavioral signals. Separate service from cognitive-sensor. |
| **Noise** | Messages that HDBSCAN couldn't assign to any cluster. Typically ~31% of messages. These are one-off or highly unique conversations. |
| **Flat script architecture** | Design choice: no packages, no frameworks, no class hierarchies. Each `.py` file is a standalone script that imports siblings and reads/writes files. |

---

## 10. Repository Structure

```
Pre Atlas/
  services/
    cognitive-sensor/          <-- Python/SQLite analysis pipeline (you are here)
      build_cognitive_atlas.py     Entry point for atlas generation
      atlas_data.py                DB loading
      atlas_projection.py          UMAP + HDBSCAN
      atlas_layers.py              Layer building
      atlas_layout.py              ForceAtlas2 layout
      atlas_graph.py               Graph construction
      atlas_render.py              HTML generation
      atlas_template.html          HTML template
      cluster_leverage_map.py      Leverage scoring
      agent_*.py                   8 idea processing agents
      governor_daily.py            Daily directive generator
      governor_weekly.py           Weekly review generator
      run_agents.py                Agent pipeline runner
      run_daily.py / run_weekly.py Governance runners
      init_*.py                    Database initialization scripts
      results.db                   SQLite database (generated)
      memory_db.json               Raw conversation export (~140MB)
      tests/                       pytest test suite (54 tests)
      cycleboard/                  Planning interface (HTML/JS)
    delta-kernel/              <-- TypeScript/Express state engine
      src/core/                    Mode system, task lifecycle, messaging
  contracts/
    schemas/                   <-- JSON Schema data contracts (draft-07)
```

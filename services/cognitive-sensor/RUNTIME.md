# Atlas Runtime

Single CLI interface for the Atlas governance stack.

## Install

```
cd services/cognitive-sensor
pip install -r requirements.txt
```

Requirements: `sentence-transformers`, `numpy`, `scikit-learn` (already in `requirements.txt`).

## Commands

```bash
python atlas_cli.py daily     # Full daily loop
python atlas_cli.py weekly    # Full weekly loop
python atlas_cli.py backlog   # Idea pipeline + backlog maintenance
python atlas_cli.py briefs    # Briefs only (no refresh)
python atlas_cli.py status    # System status + file freshness
```

## What each command does

### `atlas daily`

Full daily governance loop. ~30s.

```
Phase 1: Ingest & Analyze (Level 2 — AI-for-itself)
  loops.py              -> loops_latest.json
  completion_stats.py   -> completion_stats.json
  export_cognitive_state.py -> cognitive_state.json
  route_today.py        -> daily_directive.txt
  export_daily_payload.py -> daily_payload.json

Phase 2: Wire Dashboards (Level 2)
  wire_cycleboard.py    -> cycleboard/brain/*
  reporter.py           -> STATE_HISTORY.md
  build_dashboard.py    -> dashboard.html

Phase 3: Governor Brief (Level 1 — AI-for-you)
  governor_daily.py     -> daily_brief.md + governance_state.json
```

**Output:** `daily_brief.md` — your brief with binary decisions.

### `atlas weekly`

Full weekly governance loop. Runs daily loop first, then audit + weekly packet. ~90s.

```
Phase 1: Daily loop (all steps above)
Phase 2: Behavioral Audit (Level 2)
  agent_classifier_convo.py -> conversation_classifications.json
  agent_synthesizer.py      -> BEHAVIORAL_AUDIT.md

Phase 3: Governor Weekly Packet (Level 1)
  governor_weekly.py    -> weekly_governor_packet.md
```

**Output:** `weekly_governor_packet.md` — your weekly packet with 3-5 decisions.

### `atlas backlog`

Re-runs the full idea intelligence pipeline + conversation classifier. ~120s.

```
Phase 1: Idea Pipeline (Level 2)
  agent_excavator.py    -> excavated_ideas_raw.json
  agent_deduplicator.py -> ideas_deduplicated.json
  agent_classifier.py   -> ideas_classified.json
  agent_orchestrator.py -> idea_registry.json
  agent_reporter.py     -> IDEA_REGISTRY.md

Phase 2: Classifications (Level 2)
  agent_classifier_convo.py -> conversation_classifications.json
```

**Output:** `idea_registry.json` + `IDEA_REGISTRY.md` — updated idea registry.

### `atlas briefs`

Generates governor briefs from whatever state currently exists on disk. No upstream refresh — fast (<5s).

```
governor_daily.py   -> daily_brief.md
governor_weekly.py  -> weekly_governor_packet.md
```

### `atlas status`

Shows current config (North Star, lanes, moratorium) and file freshness.

## Autonomy levels

All scripts called by the agent are Level 2 (execute & report) — they only mutate internal files:
- JSON state files (`cognitive_state.json`, `governance_state.json`, etc.)
- SQLite database (`results.db`)
- Markdown reports (`daily_brief.md`, `BEHAVIORAL_AUDIT.md`, etc.)
- HTML dashboards (`dashboard.html`, `idea_dashboard.html`)

No external side effects. No network calls. No public-facing mutations.

The governor briefs (Level 1) produce markdown for your review — they don't execute decisions.

## Architecture

```
atlas_cli.py
  -> AtlasAgent (atlas_agent.py)
       -> subprocess calls to existing scripts
       -> config from atlas_config.py
```

`AtlasAgent` is a thin wrapper. It does not re-implement any logic.
Each script runs in its own subprocess with `cwd` set to `services/cognitive-sensor/`.

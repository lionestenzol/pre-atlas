# Agent Directory

17 scripts across 5 categories. All agents live in `services/cognitive-sensor/`.

---

## Entry Points

| Script | Command | What it does |
|--------|---------|-------------|
| `atlas_cli.py` | `python atlas_cli.py daily` | Single CLI entry point — `daily`, `weekly`, `backlog`, `briefs`, `status` |
| `atlas_agent.py` | (imported) | Unified runtime interface wrapping all pipelines into one class |
| `atlas_config.py` | (imported) | Config: North Star, targets, kernel rules, active lanes, autonomy levels |

---

## Idea Intelligence Pipeline

Runs in sequence via `run_agents.py`. Extracts, deduplicates, classifies, prioritizes, and reports on ideas from 1,397+ conversations.

```
memory_db.json ─► excavator ─► deduplicator ─► classifier ─► orchestrator ─► reporter
                      │              │               │              │              │
                      ▼              ▼               ▼              ▼              ▼
              excavated_ideas  ideas_dedup'd   ideas_classified  idea_registry  IDEA_REGISTRY.md
              _raw.json        .json           .json             .json
```

| # | Script | Input | Output | Method |
|---|--------|-------|--------|--------|
| 1 | `agent_excavator.py` | memory_db.json, results.db | excavated_ideas_raw.json | Regex + semantic similarity (threshold 0.40) |
| 2 | `agent_deduplicator.py` | excavated_ideas_raw.json | ideas_deduplicated.json | Cosine similarity + union-find (same ≥0.70, related ≥0.55) |
| 3 | `agent_classifier.py` | ideas_deduplicated.json | ideas_classified.json | Hierarchical clustering + status detection + alignment scoring |
| 4 | `agent_orchestrator.py` | ideas_classified.json | idea_registry.json | Priority scoring: freq(20%) + recency(20%) + alignment(25%) + feasibility(15%) + compounding(20%) |
| 5 | `agent_reporter.py` | idea_registry.json | IDEA_REGISTRY.md | Renders tables, hierarchy trees, timelines, recommendations |

**Schema validation**: Agents 1-4 call `require_valid()` before writing JSON output, enforcing `ExcavatedIdeas.v1.json` or `IdeaRegistry.v1.json` contracts.

---

## Behavioral Analysis Pipeline

Runs via `run_audit.py`. Classifies conversations and synthesizes a behavioral profile.

| # | Script | Input | Output | Method |
|---|--------|-------|--------|--------|
| 6 | `agent_classifier_convo.py` | memory_db.json, results.db | conversation_classifications.json | Semantic signatures + keyword signals for domain/outcome/emotion/intensity |
| 7 | `agent_synthesizer.py` | All analysis .md files, classifications, registry, cognitive_state | BEHAVIORAL_AUDIT.md | 30-question analysis across 6 layers (identity, power, execution, decisions, cognition, opportunity) |
| 8 | `agent_book_miner.py` | memory_db.json, results.db | book_raw_material.json, BOOK_OUTLINE.md | Extracts power dynamics content, clusters into chapter themes |

---

## Governors

Daily and weekly governance loops that consume pipeline outputs and produce actionable briefs.

| # | Script | Input | Output | Cadence |
|---|--------|-------|--------|---------|
| 9 | `governor_daily.py` | cognitive_state, idea_registry, classifications, daily_payload | daily_brief.md, governance_state.json | Daily |
| 10 | `governor_weekly.py` | governance_state, idea_registry, classifications, BEHAVIORAL_AUDIT | weekly_governor_packet.md | Weekly |

**Autonomy model**:
- Level 2 (AI-for-itself): Ingest, classify, maintain backlog, park new ideas — no human approval needed
- Level 1 (AI-for-you): Generate briefs with binary decisions — human approves/rejects

---

## Orchestrators

| Script | What it runs |
|--------|-------------|
| `run_agents.py` | Idea pipeline: excavator → deduplicator → classifier → orchestrator → reporter |
| `run_audit.py` | Behavioral pipeline: classifier_convo → synthesizer |
| `run_daily.py` | Full daily loop: ingest + analyze + backlog + daily brief |
| `run_weekly.py` | Full weekly loop: daily + audit + weekly packet |

---

## Shared Dependencies

| Module | Purpose |
|--------|---------|
| `validate.py` | JSON Schema enforcement via `require_valid()` — contracts in `contracts/schemas/` |
| `atlas_config.py` | North Star, targets, routing rules, autonomy split |
| `model_cache.py` | Cached sentence-transformer embeddings for semantic similarity |

---

## Archived Scripts

12 dead scripts moved to `_archive/` (2026-02-11 audit):
brain.py, brain_2.py, belief_core.py, belief_grammar.py, decision_engine.py, language_loops.py, profile_report.py, semantic_loops.py, search_loops.py, cluster_topics.py, cluster_business_topics.py, test_vectorization.py

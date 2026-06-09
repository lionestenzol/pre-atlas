# memory-hub

One REST surface over Pre Atlas's three memory stores.

Port **3071**. Sits in front of:

- **DropList** (`services/droplist/data/packets.jsonl`) — every drop you've made
- **Cognitive Sensor** (`services/cognitive-sensor/atlas_query.py`) — embedding cluster search over conversation history
- **Idea Registry** (`services/cognitive-sensor/cycleboard/brain/idea_registry.json`) — 20 prioritized canonical ideas (execute_now + next_up)
- **Mirofish** (`services/mirofish/.../neo4j_client.py`) — conversation/topic/idea graph (degrades silently if Neo4j isn't running)

Each store stays where it is. memory-hub doesn't own data — it routes queries to the right backend and merges results.

## Endpoints

```text
GET  /healthz                          → store availability
POST /search   {q, max_results, sources?}  → merged hits across all stores
GET  /idea/{canonical_id}              → exact lookup in idea_registry
GET  /entity/{name}                    → mirofish 1-hop neighbors (when Neo4j up)
POST /save     {type, content, source}     → persist as DropList packet
```

## Run

```bash
cd services/memory-hub
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m memory_hub.server   # binds 127.0.0.1:3071
```

## How search-stack uses it

The `memory` provider in [services/search-stack/src/search_stack/providers/memory.py](../search-stack/src/search_stack/providers/memory.py) HTTP-calls `localhost:3071/search` when memory-hub is reachable, falls back to in-process logic when it isn't. Either way, callers get the same `SearchResult` shape.

## Doctrine

- Each store stays where it is — memory-hub is router, not warehouse
- Backends that can't reach their data return [] (no exceptions)
- Token-overlap and embedding search are both first-class; the consumer doesn't care which fired

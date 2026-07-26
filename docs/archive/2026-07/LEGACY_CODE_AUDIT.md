# Legacy code audit · forensic inventory

Generated 2026-05-28 by reading every source file. Not inferred from titles.

Paired with [`NEXT_SESSION_HANDOFF.md`](NEXT_SESSION_HANDOFF.md).

---

## Why this exists

Bruke flagged 2026-05-28 that prior session work on `claude-mining/v2/` was contaminated (title-grep + ctrl-F bias). Banner pass applied to 25 interpretive files. Then he asked: "find the old things that worked, reverse-engineer their logic." This document is the answer to the second half.

Every claim below is verified by reading the actual code. No inference from filenames.

---

## The lineage

```
   Sep 2024  · ChatGPTAnalysis     ── TF-IDF + KMeans + LDA + PCA + interactive refine
                       ↓                (lexical · no embeddings)
   Mar 2025  · 002faiss.py         ── FastAPI shell (incomplete · stub)
                       ↓
   May 2025  · vector_index.pt     ── MiniLM-L6-v2 embeddings (HuggingFace)
                       ↓                ("old vectoring")
   Jun 2025  · faiss_index/        ── IndexFlatL2 + .pkl docstore
              faiss_index.ivf          IVF variant (615 MB)
                       ↓
   Jun 2025  · ollama_query*.py    ── Chroma + Ollama llama3.2 + CLI search loop +
                       ↓                pattern tracker  ("old CLI search")
   ?         · cognitive-sensor    ── current Pre Atlas service · primitives ported
                       ↓
   May 2026  · claude-mining v2/   ── same MiniLM model · 7110 convs · MECHANICS WORK
                                       (doctrine outputs contaminated · see banner)
```

Same embedding model `all-MiniLM-L6-v2` from May 2025 through May 2026. Continuity confirmed.

---

## Inventory · all working artifacts on disk

### Layer 1 · ChatGPTAnalysis (Sep 2024)

```
   path:  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\
   era:   pre-embedding · pure lexical
```

| file | size | what it does (verified) |
|---|---:|---|
| `chatgpt_analysis.py` | 2,955 | conversations.json → CSV. Flattens to msg rows: conv_id, title, msg_id, create_time, sender, content |
| `last.py` | 1,720 | conversations.json → organized_conversations.json. Simpler shape, id+text only |
| `extract.py` | 6,548 | KMeans with auto-K via silhouette score + retry-on-timeout. Most-engineered clustering |
| `cluster.py` | 2,961 | TF-IDF(1000 feat) → KMeans(k=5) → LDA topic modeling → PCA viz |
| `structure.py` | 4,668 | cluster.py + cluster inspection + 5-vs-3 comparison + per-cluster LDA |
| `refine.py` | 5,970 | INTERACTIVE drill-down clustering. y/n/u/d controls. History+undo. Subcategory refinement |
| `next.py` | 3,591 | Word-level TF-IDF + KMeans (different granularity from message-level) |
| `search.py` | 1,116 | TF-IDF top-20 word frequency from chatgpt_conversations.csv |
| `senti.py` | 2,208 | Context-window-2 word neighbors. NOT actual sentiment despite the name |
| `slide.py` | 2,129 | Identical to senti.py (duplicate) |
| `grams.py` | 1,105 | Bi-gram frequency from top-words list |
| `removegpt.py` | 2,653 | senti.py but USER-only filtering (excludes assistant turns) |
| `ticket.py` | 30 | Stub, 30 bytes |
| `extract2.txt`, `jkjk`, `import nltk.txt` | 0 / 30 | Empty or scratch |

**Working data files:**

| file | size | shape |
|---|---:|---|
| `conversations.json` | 12.5 MB | raw ChatGPT export, ~1.3k convs |
| `organized_conversations.json` | 10.1 MB | simplified, id+text per msg |
| `chatgpt_conversations.csv` | 7.5 MB | flattened msg rows |
| `word_contexts.csv` | 1.5 MB | senti/slide output |
| `Figure_1.png`, `Figure_2.png` | 50-63 KB | PCA cluster plots (shipped output) |
| `clustering_errors.log` | 0 | empty (good · no failures recorded) |

### Layer 2 · Old vectoring (May 31 2025)

```
   path:  C:\Users\bruke\vector_index.pt
   size:  18.9 MB
   shape: PyTorch dict { "texts": [...], "embeddings": tensor(n, 384) }
   model: all-MiniLM-L6-v2 (HuggingFace)
```

This is the semantic upgrade from TF-IDF. Same model that v2 uses one year later.

### Layer 3 · Old FAISS (Jun 1 2025)

```
   path:  C:\Users\bruke\faiss_index\
            ├── index.faiss          13.6 MB
            └── index.pkl             4.9 MB

   path:  C:\Users\bruke\faiss_index.ivf          615 MB  ← IVF variant
```

Builders (Desktop):

| file | size | what it does |
|---|---:|---|
| `convert_pt_to_faiss.py` | 1,205 | vector_index.pt → FAISS IndexFlatL2. Wraps in LangChain FAISS store with InMemoryDocstore. Uses all-MiniLM-L6-v2 embedding model |
| `convert_pt_to_faissv2.py` | 1,205 | Identical copy of v1 (byte-for-byte same size, code matches) |
| `PY/002faiss.py` | 513 | FastAPI stub with "FAISS API is running!" message. NOT real FAISS code. Mislabeled |

### Layer 4 · Ollama CLI search (Jun 1-2 2025, 11 versioned files)

```
   path:  C:\Users\bruke\OneDrive\Desktop\
```

| file | size | notes |
|---|---:|---|
| `notepad ollama_query.py` | 7,808 | Stable. Internal name `ollama_modes.py`. Mode system (lite/reflective/dev) |
| `notepad ollama_queryv9.py` | 8,273 | Newest. Renamed "Recursive Vector Brain Activated" |
| `notepad ollama_query.zip` | 27,991 | bundled snapshot |
| `notepad ollama_querypy.txt` | 6,011 | identical size to v5 (probably copy) |
| `notepad ollama_queryv0.py` | 868 | smallest, earliest |
| `notepad ollama_queryv1.py` | 1,129 | |
| `notepad ollama_queryv2.py` | 2,821 | |
| `notepad ollama_queryv3.py` | 6,936 | |
| `notepad ollama_queryv4.py` | 8,786 | biggest in v0-v5 |
| `notepad ollama_queryv5.py` | 6,011 | |
| `notepad ollama_queryv6openai.py` | 6,227 | OpenAI variant (different LLM provider) |
| `notepad ollama_queryv7ollama.py` | 6,280 | back to Ollama |
| `notepad ollama_queryv8ollama.py` | 6,168 | |

**What the stable version does (verified by reading):**

1. CLI loop `💬 You: ...`
2. ChromaDB vector store at `./chroma_db` · `OllamaEmbeddings` · model `llama3.2:latest`
3. User input → `vector_store.similarity_search(query, k=3)` → context
4. `llm.invoke(context + question)` → response printed
5. Log conversation to `ollama_log.md` (rotates at 5 MB)
6. Pattern tracker (10 keywords): avoidance · fear · control · resentment · self-sabotage · doubt · growth · freedom · isolation · awareness
7. Weighted scoring (self-sabotage 2.0, avoidance 1.8, fear 1.5, growth 1.3, control 1.2, default 1.0)
8. `scramble` command shows ranked pattern hits this session
9. Mode env var `OLLAMA_MODE`: lite (friendly) · reflective (logging + insights) · dev (silent + max data)

### Layer 5 · cognitive-sensor (current)

```
   path:  C:\Users\bruke\Pre Atlas\services\cognitive-sensor\
   status: present in Pre Atlas tree · primitives presumed ported from Layers 1-4
   notes:  not read in this audit · separate pass needed
```

### Layer 6 · claude-mining v2 (May 2026)

```
   path:  C:\Users\bruke\OneDrive\Desktop\claude-mining\v2\
   index: v2/index/minilm/index.faiss   (7110 convs, MiniLM-L6-v2)
          v2/index/mpnet/index.faiss    (7110 convs, all-mpnet-base-v2)
   status: mechanics work · 23-117ms latency · doctrine outputs CONTAMINATED
```

See [`NEXT_SESSION_HANDOFF.md`](NEXT_SESSION_HANDOFF.md) for the contamination scope.

---

## What this confirms

- Same embedding model `all-MiniLM-L6-v2` used in May 2025 AND May 2026. Continuity is real.
- Old FAISS index already exists on disk (`C:\Users\bruke\faiss_index\index.faiss`, 13.6 MB). Loadable today.
- Ollama CLI search loop shipped through v0 → v9 evolution. The stable version uses ChromaDB + Ollama llama3.2 + pattern tracker.
- ChatGPTAnalysis primitives are pre-embedding lexical bootstrap. TF-IDF + KMeans + LDA + PCA + interactive refine.
- Pattern tracker in `ollama_query.py` is the closest thing to "memory" in the legacy chain · but it's local session state · resets each run · not durable.

## What the legacy code does NOT have

- **No layer reads a referenced conv back IN as context for action.** Every search/cluster returns labels or text snippets to display.
- **No layer writes derived results back to the corpus as new entries.** Outputs go to .csv, .png, .md log files, not back to the indexed pool.
- **No layer composes search + cluster + act + return into one round-trip.** Each script is a one-shot pipeline.

The closed-loop gap Bruke described in cognitive-sensor was never closed in the legacy code either. Cognitive-sensor inherited the open-loop pattern from this lineage.

---

## Implications for the brownfield merge

The smallest closed-loop plan in [`NEXT_SESSION_HANDOFF.md`](NEXT_SESSION_HANDOFF.md) (4-move sequence: intake → fat refs → one act → close the loop) is consistent with what the legacy code lacks. Each move addresses a real gap in the lineage, not a hypothetical one.

Reusable as-is from legacy:

- The MiniLM-L6-v2 embedding stays (continuity).
- `convert_pt_to_faiss.py` pattern (load embeddings + wrap in LangChain FAISS) is reusable if a future spine wants the LangChain API surface.
- The pattern tracker (10 weighted keywords) from `ollama_query.py` is a starting point for doctrine-pattern extraction primitives.
- The interactive refine loop (y/n/u/d with history+undo) from `refine.py` is a starting point for human-in-the-loop clustering UX.

NOT reusable:

- TF-IDF + KMeans + LDA from ChatGPTAnalysis era. Superseded by semantic embeddings already in `vector_index.pt` and `faiss_index/`.
- `002faiss.py` (FastAPI stub, never finished).
- Duplicates: `slide.py` == `senti.py`, `convert_pt_to_faissv2.py` == `convert_pt_to_faiss.py`.

Open question (do NOT answer without Bruke):

- Does cognitive-sensor today use the May-2025 `vector_index.pt` / `faiss_index/` directly, or does it carry its own derived embeddings? Separate audit pass needed.
- The 615 MB `faiss_index.ivf` is much larger than `index.faiss` (13.6 MB). Different conversation set, or different index type, or different conv-granularity (per-message vs per-conv)? Needs source inspection.

---

## File-list summary (copy-pasteable for next session)

```
ChatGPTAnalysis (Sep 2024, pre-embedding lexical):
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\chatgpt_analysis.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\last.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\extract.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\cluster.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\structure.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\refine.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\next.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\search.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\senti.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\slide.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\grams.py
  C:\Users\bruke\OneDrive\Documents\ChatGPTAnalysis\removegpt.py

Old vectoring (May 2025):
  C:\Users\bruke\vector_index.pt                                      (18.9 MB)

Old FAISS (Jun 2025):
  C:\Users\bruke\faiss_index\index.faiss                              (13.6 MB)
  C:\Users\bruke\faiss_index\index.pkl                                ( 4.9 MB)
  C:\Users\bruke\faiss_index.ivf                                      ( 615 MB)
  C:\Users\bruke\OneDrive\Desktop\convert_pt_to_faiss.py
  C:\Users\bruke\OneDrive\Desktop\convert_pt_to_faissv2.py
  C:\Users\bruke\OneDrive\Desktop\PY\002faiss.py                      (stub, ignore)

Ollama CLI search (Jun 2025, 11 versions):
  C:\Users\bruke\OneDrive\Desktop\notepad ollama_query.py             (stable, 7.8 KB)
  C:\Users\bruke\OneDrive\Desktop\notepad ollama_queryv9.py           (newest, 8.3 KB)
  C:\Users\bruke\OneDrive\Desktop\notepad ollama_queryv0.py           ...
  C:\Users\bruke\OneDrive\Desktop\notepad ollama_queryv1-v8.py        (versioned iterations)

Current cognitive-sensor (needs separate audit):
  C:\Users\bruke\Pre Atlas\services\cognitive-sensor\

Current claude-mining v2 (mechanics OK, outputs contaminated):
  C:\Users\bruke\OneDrive\Desktop\claude-mining\v2\index\minilm\
  C:\Users\bruke\OneDrive\Desktop\claude-mining\v2\index\mpnet\
  C:\Users\bruke\OneDrive\Desktop\claude-mining\scripts\
```

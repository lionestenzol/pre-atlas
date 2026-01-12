# Vectorization System Documentation

## Overview

This document describes the **semantic vectorization layer** added to the Cognitive Operating System. It extends the original keyword-based analysis with deep semantic understanding using sentence embeddings.

## What Vectorization Adds

### Before (Keyword-Based)
- Exact word matching only
- "run" ≠ "running"
- "want to build" ≠ "plan to create"
- No semantic similarity

### After (Vector-Based)
- Semantic meaning captured
- Synonyms understood automatically
- Related concepts discovered
- Conversation clustering by theme

---

## Architecture

### New Components

```
LAYER 1: DATA
├─ embeddings table (in results.db)
│   └─ 384-dimensional vectors per conversation
│
LAYER 2: GENERATION
├─ init_embeddings.py → generates vectors
│
LAYER 3: INTELLIGENCE
├─ semantic_loops.py → hybrid loop detection
├─ search_loops.py → semantic search
└─ cluster_topics.py → theme discovery
│
LAYER 4: OUTPUTS
├─ semantic_loops.json → enhanced loop detection
├─ search_results.json → query results
└─ topic_clusters.json → conversation themes
```

---

## Database Schema

### New Table: `embeddings`

```sql
CREATE TABLE embeddings (
    convo_id TEXT PRIMARY KEY,
    embedding BLOB,          -- 384-dim vector as binary
    model TEXT,              -- 'all-MiniLM-L6-v2'
    created_at TEXT,         -- ISO timestamp
    text_length INTEGER      -- Original text length
)
```

**Storage:**
- 1,397 conversations × 384 dimensions × 4 bytes = ~2.1 MB
- Stored as numpy float32 binary blobs
- Fast retrieval and cosine similarity computation

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Packages installed:**
- `sentence-transformers` - Embedding model
- `numpy` - Vector operations
- `scikit-learn` - Clustering algorithms

**Total download:** ~200 MB (includes model weights)

### 2. Generate Embeddings

```bash
python init_embeddings.py
```

**What happens:**
1. Downloads model on first run (~80 MB)
2. Loads all 1,397 conversations from memory_db.json
3. Generates 384-dimensional embedding per conversation
4. Stores in `embeddings` table
5. Takes 2-3 minutes total

**Output:**
```
✓ Successfully generated 1397 embeddings
  Model: all-MiniLM-L6-v2
  Dimensions: 384
  Database size increase: ~2.1 MB
```

---

## Usage

### 1. Semantic Loop Detection

**Enhanced loop detection using hybrid scoring:**

```bash
python semantic_loops.py
```

**Algorithm:**
```python
# Semantic component (0-100 scale)
semantic_score = (intent_similarity × 100) - (done_similarity × 100)

# Keyword component (original algorithm)
keyword_score = user_words + (intent_keywords × 30) - (done_keywords × 50)

# Final score (60% semantic, 40% keyword)
final_score = (semantic_score × 0.6) + (keyword_score × 0.4)
```

**Output:**
```
=== SEMANTIC OPEN LOOPS (Top 15) ===

 1. Extrinsic vs Intrinsic Rewards
    Score:  45621.3  (semantic:  62.4, keyword: 60406.0)
    Intent: 0.487  Done: 0.123

 2. Understanding Doublespeak
    Score:  31245.7  (semantic:  41.2, keyword: 31960.0)
    Intent: 0.453  Done: 0.041
```

**Also shows:**
- Loops found by semantic but not keyword (new discoveries)
- Loops found by keyword but not semantic (false positives)
- Overlap analysis

**Exports:** `semantic_loops.json`

---

### 2. Semantic Search

**Natural language queries across all conversations:**

```bash
python search_loops.py <query>
```

**Examples:**

```bash
# Find career-related conversations
python search_loops.py career decisions

# Find Python programming discussions
python search_loops.py "python programming"

# Find productivity systems
python search_loops.py productivity workflow systems
```

**Output:**
```
=== SEARCH RESULTS ===

 1. [87.2%] STRONG | Professional Path Confusion
    Date: 2024-11-15  ConvoID: 847

 2. [83.4%] STRONG | Job vs Passion Dilemma
    Date: 2024-10-22  ConvoID: 723

 3. [79.1%] MEDIUM | What Should I Do With My Life
    Date: 2024-09-08  ConvoID: 512
```

**Relevance levels:**
- **STRONG** (>50%): Highly relevant
- **MEDIUM** (30-50%): Related concepts
- **WEAK** (<30%): Tangentially related

**Exports:** `search_results.json`

---

### 3. Topic Clustering

**Automatically discover conversation themes:**

```bash
python cluster_topics.py
```

**What it does:**
1. Groups all 1,397 conversations into 10 clusters
2. Finds most common keywords per cluster
3. Shows sample conversations
4. Identifies natural topic boundaries

**Output:**
```
=== DISCOVERED TOPIC CLUSTERS ===

CLUSTER 1 (142 conversations)
----------------------------------------------------------------------
Keywords: python, code, function, debug, error

Sample conversations:
  • Python List Comprehension Help  (2024-11-20)
  • Debugging AttributeError  (2024-11-15)
  • How to Use Decorators  (2024-11-03)

CLUSTER 2 (87 conversations)
----------------------------------------------------------------------
Keywords: career, job, decision, professional, path

Sample conversations:
  • Should I Change Jobs?  (2024-10-28)
  • Career Path Confusion  (2024-10-15)
```

**Configuration:**
- Change `NUM_CLUSTERS` in script (default: 10)
- Adjust `MIN_CLUSTER_SIZE` to filter tiny clusters (default: 3)

**Exports:** `topic_clusters.json`

---

## Technical Details

### Model: all-MiniLM-L6-v2

**Specs:**
- Dimensions: 384
- Speed: ~500 sentences/second on CPU
- Quality: 68.7% on semantic similarity benchmarks
- Size: 80 MB
- Training: Trained on 1B+ sentence pairs

**Why this model:**
- Fast enough for local CPU
- Good quality/speed tradeoff
- No API costs
- Completely private (runs locally)

**Alternatives:**
- `all-mpnet-base-v2` - Better quality (768 dims), slower
- `text-embedding-3-small` - OpenAI API, costs money, better quality

---

### Vector Operations

**Cosine Similarity:**
```python
# How similar are two vectors?
similarity = np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))

# Returns: 0.0 to 1.0
# 1.0 = identical meaning
# 0.5 = somewhat related
# 0.0 = completely unrelated
```

**Why cosine similarity:**
- Direction matters, not magnitude
- Normalized (0-1 scale)
- Industry standard for embeddings
- Fast to compute

---

## Performance

### Generation (One-Time)

| Task | Time | Notes |
|------|------|-------|
| Model download | 30s | First run only |
| Generate 1,397 embeddings | 2-3 min | ~1.7 conversations/sec |
| Database write | 5s | Bulk insert |

**Total first run:** ~3-4 minutes

### Query (Repeated)

| Task | Time | Notes |
|------|------|-------|
| Load model | 2s | Cached in memory |
| Semantic search | <1s | 1,397 comparisons |
| Clustering | 3-4s | K-means on 1,397 vectors |
| Loop detection | 2-3s | Hybrid scoring |

**All queries:** Sub-second after model loads

---

## Integration with Existing System

### Hybrid Approach (Recommended)

**Current strategy:**
- **60% semantic** - Captures meaning
- **40% keyword** - Preserves proven logic

**Why hybrid:**
- Semantic finds patterns keywords miss
- Keywords catch explicit signals ("done", "finished")
- Best of both worlds

### Migration Path

**Phase 1 (Current):** Parallel systems
- Keep original `loops.py` unchanged
- New `semantic_loops.py` as alternative
- Compare outputs manually

**Phase 2 (Optional):** Replace keyword system
- Update `refresh.py` to call `semantic_loops.py`
- Archive `loops.py` for reference
- Pure semantic scoring

**Phase 3 (Advanced):** Adaptive weighting
- Track which method performs better
- Auto-adjust semantic/keyword ratio
- Learn from user decisions

---

## Use Cases

### 1. Better Loop Detection

**Problem:** Keyword system misses paraphrased intent

**Example:**
```
Keyword: "I'm going to build a todo app" → HIGH SCORE
         "I'm planning to create a task manager" → LOW SCORE (different words)

Semantic: Both score HIGH (same meaning)
```

### 2. Find Related Conversations

**Problem:** Can't find "that conversation about X"

**Solution:**
```bash
python search_loops.py goal setting systems
# Finds: "OKRs", "habit tracking", "New Year resolutions"
```

### 3. Discover Hidden Themes

**Problem:** Don't know what topics you discuss most

**Solution:**
```bash
python cluster_topics.py
# Output: "You have 87 conversations about career decisions"
```

### 4. Reduce False Positives

**Keyword approach:**
- High score if says "want" many times
- Even if context is "I don't want..."

**Semantic approach:**
- Understands negation
- Captures actual intent
- Fewer false alarms

---

## Limitations

### 1. Context Window
- First 5,000 characters per conversation
- Long conversations truncated
- May miss late-conversation signals

**Solution:** Could split into chunks, average embeddings

### 2. Language
- English only
- Other languages have poor quality
- Model trained on English text

### 3. Recency Bias
- No timestamp weighting
- Old and new conversations treated equally
- May surface irrelevant old loops

**Solution:** Could add recency penalty in scoring

### 4. Computational Cost
- Requires ~200 MB disk space
- 2-3 minute initialization
- Needs numpy/sklearn dependencies

**Trade-off:** Acceptable for semantic understanding gain

---

## Maintenance

### Regenerating Embeddings

**When to regenerate:**
- Added new conversations to memory_db.json
- Want to try different model
- Database corrupted

**How:**
```bash
python init_embeddings.py
# Prompts: "Found 1397 existing embeddings. Regenerate? (y/n)"
```

### Updating Model

**To switch models:**

1. Edit `init_embeddings.py`:
```python
MODEL_NAME = 'all-mpnet-base-v2'  # Better quality
```

2. Regenerate embeddings:
```bash
python init_embeddings.py
```

3. Update all scripts with new model name

### Database Size

**Current:**
- embeddings table: ~2.1 MB
- Total database: ~5.0 MB (was 2.9 MB)

**Scaling:**
- Linear growth: 1.5 KB per conversation
- 10,000 conversations = ~15 MB
- 100,000 conversations = ~150 MB

**Still very manageable.**

---

## Troubleshooting

### "ModuleNotFoundError: sentence_transformers"

**Fix:**
```bash
pip install -r requirements.txt
```

### "No embeddings found in database"

**Fix:**
```bash
python init_embeddings.py
```

### Slow performance

**Causes:**
- First run downloading model
- CPU overloaded
- Large number of conversations

**Solutions:**
- Wait for model download to complete
- Close other applications
- Reduce `NUM_CLUSTERS` in cluster_topics.py

### Model download fails

**Causes:**
- No internet connection
- Firewall blocking HuggingFace

**Solution:**
- Check internet connection
- Try again later
- Manually download model from HuggingFace

---

## Future Enhancements

### Short Term
- [ ] Add semantic search to control panel UI
- [ ] Visualize clusters in dashboard
- [ ] Cache model in memory for faster queries
- [ ] Add progress bars to long operations

### Medium Term
- [ ] Conversation summarization using embeddings
- [ ] Detect topic drift over time (semantic version of radar)
- [ ] Find conversations similar to current open loops
- [ ] Auto-suggest related loops when making decisions

### Long Term
- [ ] Fine-tune model on your conversation style
- [ ] Multi-lingual support
- [ ] Real-time embedding as you chat
- [ ] Predictive loop detection (will this become a loop?)

---

## Files Reference

### Scripts
- `init_embeddings.py` - Generate embeddings (run once)
- `semantic_loops.py` - Hybrid loop detection
- `search_loops.py` - Semantic search queries
- `cluster_topics.py` - Topic clustering

### Data Files
- `semantic_loops.json` - Hybrid loop scores
- `search_results.json` - Search query results
- `topic_clusters.json` - Discovered themes

### Dependencies
- `requirements.txt` - Python packages

---

## Comparison: Keyword vs Semantic

| Feature | Keyword | Semantic | Winner |
|---------|---------|----------|--------|
| Speed | ⚡ Instant | 🐢 2-3 sec | Keyword |
| Accuracy | 📊 Good | 🎯 Excellent | Semantic |
| Setup | ✅ None | 📦 3-4 min | Keyword |
| Dependencies | ✅ None | 📚 3 packages | Keyword |
| Synonyms | ❌ Missed | ✅ Detected | Semantic |
| Search | ❌ Exact only | ✅ Fuzzy | Semantic |
| Clustering | ❌ Can't do | ✅ Yes | Semantic |
| Privacy | ✅ Local | ✅ Local | Tie |
| False positives | ⚠️ Common | ✅ Rare | Semantic |

**Verdict:** Hybrid approach combines strengths of both.

---

## Credits

**Models:**
- all-MiniLM-L6-v2 by [sentence-transformers](https://www.sbert.net/)
- Trained on 1B+ sentence pairs
- Released under Apache 2.0 license

**Libraries:**
- sentence-transformers
- numpy
- scikit-learn

---

## Questions?

**Common questions:**

**Q: Do I need to regenerate embeddings after every conversation?**
A: No. Only when you export fresh ChatGPT data and run `init_results_db.py`.

**Q: Can I use OpenAI embeddings instead?**
A: Yes, but costs money and requires API key. Current approach is free and private.

**Q: Will this slow down my daily refresh?**
A: No. Vectorization is separate. Original `refresh.py` unchanged.

**Q: How do I integrate semantic loops into the main system?**
A: Edit `refresh.py` to call `semantic_loops.py` instead of `loops.py`.

**Q: What if I have 10,000 conversations?**
A: Still works. Generation takes ~20 minutes, queries still sub-second.

---

**Last updated:** 2026-01-04

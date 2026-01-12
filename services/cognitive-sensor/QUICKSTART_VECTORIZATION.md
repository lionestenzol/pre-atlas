# Vectorization Quick Start

Get semantic understanding of your conversations in **5 minutes**.

---

## Step 1: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

**Downloads:**
- sentence-transformers
- numpy
- scikit-learn
- Total: ~200 MB

---

## Step 2: Generate Embeddings (3 minutes)

```bash
python init_embeddings.py
```

**What happens:**
- Downloads model (~80 MB, first run only)
- Generates 384-dimensional vector for each conversation
- Stores in `results.db`
- Progress shown every 50 conversations

**Output:**
```
✓ Successfully generated 1397 embeddings
  Model: all-MiniLM-L6-v2
  Dimensions: 384
  Database size increase: ~2.1 MB
```

---

## Step 3: Try It Out (1 minute)

### A. Semantic Loop Detection

```bash
python semantic_loops.py
```

See hybrid scoring that combines keyword + semantic signals.

### B. Search Your Conversations

```bash
python search_loops.py "career decisions"
```

Find related conversations even if exact words don't match.

### C. Discover Themes

```bash
python cluster_topics.py
```

Automatically group conversations into topic clusters.

---

## What You Get

### Before (Keyword-Only)
```bash
python loops.py
# Output: Loops based on exact word matching
```

### After (Semantic)
```bash
python semantic_loops.py
# Output: Loops based on meaning + keywords
# Finds: paraphrases, synonyms, related concepts
```

---

## Integration Options

### Option 1: Keep Both (Recommended)

Run both systems in parallel:
- `loops.py` - Original keyword approach
- `semantic_loops.py` - New semantic approach
- Compare outputs manually

### Option 2: Replace Keyword System

Edit `refresh.py`:
```python
# Before
subprocess.run(["python", "loops.py"])

# After
subprocess.run(["python", "semantic_loops.py"])
```

### Option 3: Hybrid Scoring

Already done! `semantic_loops.py` uses:
- 60% semantic signals
- 40% keyword signals
- Best of both worlds

---

## Daily Usage

### When You Add New Conversations

1. Export fresh ChatGPT data
2. Replace `memory_db.json`
3. Run:
```bash
python init_results_db.py
python init_embeddings.py  # Regenerate vectors
python refresh.py          # Update everything
```

### When You Want to Search

```bash
python search_loops.py "your query here"
```

### When You Want Insights

```bash
python cluster_topics.py
# See what topics dominate your conversations
```

---

## Troubleshooting

### "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### "No embeddings found"
```bash
python init_embeddings.py
```

### Slow performance
- First run: Wait for model download
- Subsequent: Should be 2-3 seconds max

---

## Next Steps

1. ✅ Read full docs: `VECTORIZATION.md`
2. 🔍 Try semantic search with different queries
3. 📊 Explore topic clusters
4. 🔄 Decide if you want to integrate into `refresh.py`

---

**That's it!** You now have semantic understanding of your conversation history.

# Technical Documentation

## System Architecture

### Data Flow

```
conversations.json (raw ChatGPT export)
    ↓ init_results_db.py
    ↓ init_topics.py
    ↓ init_convo_time.py
    ↓ init_titles.py
results.db (SQLite - source of truth)
    ↓ loops.py
    ↓ completion_stats.py
    ↓ radar.py
cognitive_state.json (intelligence layer)
    ↓ export_daily_payload.py
daily_payload.json (execution law)
    ↓ wire_cycleboard.py
cycleboard/brain/* (interface integration)
```

### Dependencies

**Python Standard Library Only:**
- `json` - Data serialization
- `sqlite3` - Database operations
- `subprocess` - Script orchestration
- `pathlib` - File path handling
- `datetime` - Timestamp generation
- `collections.Counter` - Frequency analysis
- `shutil` - File copying
- `re` - Regex for text processing

**No external packages required.**

### Database Indexes

```sql
CREATE INDEX idx_topics_convo ON topics(convo_id);
CREATE INDEX idx_topics_topic ON topics(topic);
CREATE INDEX idx_time_convo ON convo_time(convo_id);
CREATE INDEX idx_time_date ON convo_time(date);
```

**Purpose:** Accelerate join operations in queries like radar analysis and loop detection.

## Algorithm Details

### Topic Extraction

```python
def normalize(text):
    # Remove non-alphanumeric characters
    text = re.sub(r"[^a-zA-Z0-9 ]", " ", text.lower())

    # Split and filter
    words = text.split()
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    return words

# For each conversation
word_counts = Counter(normalize(all_messages))
top_10_topics = word_counts.most_common(10)
```

**Limitations:**
- No stemming (run/running treated as different)
- No semantic analysis (bank vs. river bank)
- Frequency only (no TF-IDF weighting)

**Why this is acceptable:**
- Fast enough for daily execution
- Transparent enough to understand
- Good enough for pattern detection

### Loop Detection Scoring

```python
def score_loop(conversation):
    score = 0

    # Base: user engagement
    score += sum(word_count for role, word_count in messages if role == "user")

    # Intent signals
    intent_words = ["want", "need", "should", "plan", "start", "build", ...]
    for topic, weight in topics:
        if topic in intent_words:
            score += weight * 30  # Amplify intent

    # Completion signals (penalty)
    done_words = ["did", "done", "finished", "completed", "solved", ...]
    for topic, weight in topics:
        if topic in done_words:
            score -= weight * 50  # Strong penalty

    return score
```

**Interpretation:**
- High score = lots of user engagement + intent language - completion language
- Score > 30,000 typically indicates strong intent without closure
- Penalizing completion words harder than boosting intent prevents false positives

**False positives:**
- Exploratory conversations (lots of questions, no intent to complete)
- How-to discussions (intent to learn, not build)

**False negatives:**
- Completed work not discussed in final messages
- External completion (work done offline)

### Routing Logic

```python
def determine_mode(open_loops, closure_ratio):
    if closure_ratio < 15:
        return "CLOSURE", False, "HIGH"  # mode, build_allowed, risk
    elif open_loops > 20:
        return "CLOSURE", False, "HIGH"
    elif open_loops > 10:
        return "MAINTENANCE", True, "MEDIUM"
    else:
        return "BUILD", True, "LOW"
```

**Thresholds explained:**

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Closure ratio < 15% | RED | You're abandoning > 85% of what you start |
| Open loops > 20 | RED | Cognitive overload, backlog unsustainable |
| Open loops > 10 | YELLOW | Warning zone, needs attention |
| Otherwise | GREEN | Healthy completion behavior |

**Why these numbers:**
- Based on analysis of your current state (6.67% ratio, 14 loops)
- Tuned to be strict enough to enforce discipline
- Loose enough to allow normal exploration

**Adjusting thresholds:**
Edit `export_daily_payload.py` lines 17-28:
```python
if ratio < 15:  # ← Change this number
```

### Drift Detection

```python
def calculate_drift():
    # Recent window
    recent = query("""
        SELECT topic, SUM(weight)
        FROM topics JOIN convo_time USING(convo_id)
        WHERE date >= date(MAX(date), '-90 day')
        GROUP BY topic
        ORDER BY SUM(weight) DESC
        LIMIT 10
    """)

    # Previous window
    previous = query("""
        SELECT topic, SUM(weight)
        FROM topics JOIN convo_time USING(convo_id)
        WHERE date >= date(MAX(date), '-180 day')
          AND date < date(MAX(date), '-90 day')
        GROUP BY topic
        ORDER BY SUM(weight) DESC
        LIMIT 10
    """)

    # Calculate delta
    for topic in all_topics:
        delta[topic] = recent[topic] - previous[topic]

    # Sort by delta
    rising = sorted(delta, key=lambda x: delta[x], reverse=True)
    fading = sorted(delta, key=lambda x: delta[x])
```

**Window size:** 90 days
- Small enough to detect shifts
- Large enough to avoid noise

**Why compare windows:**
- Absolute values don't show direction
- Delta reveals acceleration/deceleration

## Performance Characteristics

### Database Size
- **Memory DB JSON:** 140 MB
- **SQLite DB:** ~50 MB (compressed)
- **Indexes:** ~5 MB additional

### Query Performance
- **Loop detection:** ~2 seconds (13,934 topic rows)
- **Drift analysis:** ~1 second (date-filtered aggregation)
- **State export:** <100ms (simple queries)
- **Full refresh:** ~30 seconds total

### Optimization Opportunities
1. **Cache frequently accessed queries** (current drift, top loops)
2. **Incremental updates** (only process new conversations)
3. **Materialized views** (pre-calculate rising/fading topics)

**Why not optimized yet:**
- 30 seconds is acceptable for daily execution
- Premature optimization = complexity without benefit
- Current bottleneck is human decision-making, not computation

## Security Considerations

### Local-Only Architecture
- No network calls (except local web server)
- No cloud sync
- No external APIs
- All data stays on disk

### Data Exposure Risks
1. **Unencrypted database** - SQLite file is plaintext
2. **Web server open** - localhost:8080 accessible to local machine
3. **No authentication** - Anyone with file access can read

### Threat Model
**Protected against:**
- Remote attackers (no network exposure)
- Accidental cloud sync (no credentials)

**Not protected against:**
- Local file access (anyone on your machine)
- Physical access (steal the drive)
- Malware (if compromised, data is readable)

### Hardening Options
```bash
# Encrypt database
sqlite3 results.db
PRAGMA key = 'your-password';
```

**Trade-off:** Every query requires password

## Error Handling

### Current Strategy
**Fail fast:**
```python
data = json.load(open("cognitive_state.json"))
```

If file missing → crash with clear error.

**Why:**
- Better than silent failures
- Forces user to run refresh
- No partial/corrupt state

### Known Failure Modes

| Scenario | Behavior | Fix |
|----------|----------|-----|
| memory_db.json missing | FileNotFoundError on init scripts | Export from ChatGPT |
| results.db corrupted | sqlite3.DatabaseError | Delete and rebuild |
| cognitive_state.json stale | Outdated directive shown | Run refresh.py |
| daily_payload.json missing | Control panel shows OFFLINE | Run export_daily_payload.py |
| CycleBoard brain/ folder missing | Fetch fails in browser | Run wire_cycleboard.py |

### Recovery Procedures

**Complete rebuild:**
```bash
# Delete everything except source data
rm results.db cognitive_state.json daily_payload.json loops_latest.json completion_stats.json

# Rebuild from scratch
python init_results_db.py
python init_topics.py
python init_convo_time.py
python init_titles.py
python refresh.py
```

**Partial rebuild (keep database):**
```bash
# Just regenerate intelligence layer
python refresh.py
```

## Testing Strategy

### Manual Verification

**After each change:**
1. Run `python refresh.py`
2. Check control panel shows expected mode
3. Verify loop count matches manual inspection
4. Confirm closure ratio calculation

**Test scenarios:**
```python
# Simulate closing a loop
import sqlite3
con = sqlite3.connect("results.db")
con.execute("INSERT INTO loop_decisions VALUES ('1356', 'CLOSE', '2026-01-04 09:00')")
con.commit()

# Run refresh
# Expect: closure_ratio increases, open_count decreases
```

### Data Integrity Checks

```sql
-- Verify all conversations have titles
SELECT COUNT(*) FROM convo_time t
LEFT JOIN convo_titles USING(convo_id)
WHERE title IS NULL;
-- Should be 0

-- Verify topic linkage
SELECT COUNT(DISTINCT convo_id) FROM topics;
SELECT COUNT(DISTINCT convo_id) FROM convo_time;
-- Should match

-- Check for orphaned decisions
SELECT * FROM loop_decisions
WHERE convo_id NOT IN (SELECT convo_id FROM convo_titles);
-- Should be empty
```

## Extension Points

### Adding New Modes

Edit `export_daily_payload.py`:
```python
elif some_new_condition:
    mode = "FOCUS"
    build_allowed = True
    risk = "MEDIUM"
    primary_action = "Deep work on single project"
```

Update `cognitive_controller.js` to handle new mode:
```javascript
if (payload.mode === 'FOCUS') {
    banner.style.background = 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)';
}
```

### Adding New Metrics

1. **Capture data** in init scripts:
```python
# In init_results_db.py
cur.execute("""
CREATE TABLE IF NOT EXISTS sentiment (
    convo_id TEXT,
    sentiment_score REAL
)
""")
```

2. **Expose in API:**
```python
# In cognitive_api.py
def get_sentiment():
    return cur.execute("SELECT AVG(sentiment_score) FROM sentiment").fetchone()[0]
```

3. **Use in routing:**
```python
# In export_daily_payload.py
sentiment = get_sentiment()
if sentiment < 0.3:
    mode = "RECOVERY"  # New mode for low morale
```

### Integrating Other Data Sources

```python
# Example: Add GitHub commits
import requests

def fetch_github_activity():
    commits = requests.get("https://api.github.com/users/you/events").json()
    # Parse and insert into results.db
```

**Architecture supports:**
- Multiple data sources feeding one database
- Federated state (combine ChatGPT + GitHub + email)
- Cross-correlation (topics vs. commits vs. calendar)

## Maintenance

### Daily
```bash
python refresh.py  # Regenerate all state
```

### Weekly
```bash
# Check database size
du -h results.db

# Review STATE_HISTORY.md for trends
tail -50 STATE_HISTORY.md
```

### Monthly
```bash
# Export backup
cp results.db results_backup_$(date +%Y%m%d).db

# Clean old backups (keep last 3 months)
ls -t results_backup_*.db | tail -n +4 | xargs rm
```

### On New ChatGPT Export
```bash
# Replace source data
cp ~/Downloads/conversations.json memory_db.json

# Rebuild database
rm results.db
python init_results_db.py
python init_topics.py
python init_convo_time.py
python init_titles.py

# Regenerate state
python refresh.py
```

## Version Control

**What to commit:**
- All `.py` scripts
- `README.md`, `QUICKSTART.md`, `TECHNICAL.md`
- `.html` interface files
- Schema definitions

**What to ignore:**
```gitignore
# Data files
memory_db.json
results.db
cognitive_state.json
daily_payload.json
daily_directive.txt
loops_latest.json
completion_stats.json
STATE_HISTORY.md
RESURFACER_LOG.md
dashboard.html

# Temporary files
*.pyc
__pycache__/
.DS_Store
```

**Why:** Scripts are generic, data is personal.

## Known Limitations

### Architectural
1. **No semantic understanding** - Keyword-based, not meaning-based
2. **Historical only** - Can't predict future, only reflect past
3. **Single user** - Designed for personal use, not collaborative
4. **English only** - Topic extraction assumes English text

### Operational
1. **Manual execution** - User must run refresh.py daily
2. **No real-time updates** - State is snapshot, not live
3. **Browser required** - Control panel needs web server
4. **File-based integration** - CycleBoard reads files, no API

### Behavioral
1. **Assumes compliance** - System can't force you to obey
2. **Binary thinking** - Projects are open/closed, no partial states
3. **Context blind** - Can't tell if abandonment was appropriate
4. **Numeric thresholds** - 15% ratio may not fit everyone

## Future Improvements

### Short Term (Easy)
- [ ] Add "snooze" option for loops (defer decision)
- [ ] Export STATE_HISTORY as CSV for graphing
- [ ] Add keyboard shortcuts to control panel
- [ ] Email digest of weekly state

### Medium Term (Moderate Complexity)
- [ ] Natural language summaries of state changes
- [ ] Trend graphs in dashboard (closure ratio over time)
- [ ] Mobile-friendly control panel
- [ ] Voice interface for decide.py

### Long Term (Significant Work)
- [ ] Semantic topic analysis (replace keywords)
- [ ] Predictive routing (forecast next week's mode)
- [ ] Multi-user support (compare with peer group)
- [ ] Integration with calendar/email/GitHub
- [ ] Machine learning for loop scoring

## Support

**Issues:**
This is a personal system built in a single conversation. No official support.

**Questions:**
Read `README.md` for concepts, this file for implementation.

**Bugs:**
Scripts are ~500 lines total. Debug directly.

**Contributions:**
Fork and modify. Architecture is extensible.

---

*Built: 2026-01-03*
*Last updated: 2026-01-03*
*Version: 1.0 (initial release)*

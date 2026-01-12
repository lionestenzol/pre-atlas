# Cognitive Operating System

A personal behavioral governance system that analyzes your conversation history, detects patterns, and enforces completion discipline through interface control.

## What This Is

This is **not** a productivity app or habit tracker.

This is a **closed-loop behavioral governor** that:
- Reads your entire ChatGPT conversation history
- Detects unfinished projects (open loops)
- Calculates risk metrics from your behavior
- Generates daily executable law
- Enforces that law on your planning interfaces
- Prevents you from starting new projects until you close old ones

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: MEMORY                                         │
│ results.db - Canonical database of all conversations    │
│ • 93,898 messages across 1,397 conversations            │
│ • Topics, timestamps, roles, intensity metrics          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: INTELLIGENCE                                   │
│ Scripts that extract meaning from memory                │
│ • radar.py - Detects attention drift over time         │
│ • loops.py - Finds unfinished conversations            │
│ • completion_stats.py - Tracks closure behavior        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: NERVOUS SYSTEM                                 │
│ cognitive_state.json - Machine-readable brain state     │
│ • Current open loops with titles and scores             │
│ • Closure ratio and backlog metrics                     │
│ • Topic drift analysis                                  │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 4: LAW GENERATION                                 │
│ daily_payload.json - Executable behavioral directive    │
│ • MODE: CLOSURE / MAINTENANCE / BUILD                   │
│ • build_allowed: true/false (enforces lockouts)         │
│ • primary_action: Single directive for today            │
│ • risk: HIGH / MEDIUM / LOW                             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 5: INTERFACE GOVERNANCE                           │
│ Your planning tools become governed surfaces            │
│ • CycleBoard - Shows red banner, locks create buttons   │
│ • Dashboard - Displays analytics and trends             │
│ • Control Panel - Master control interface              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ LAYER 6: DECISION TRACKING                              │
│ loop_decisions table - Records every closure decision   │
│ • Tracks CLOSE / CONTINUE / ARCHIVE choices             │
│ • Feeds back into tomorrow's routing logic              │
└─────────────────────────────────────────────────────────┘
```

## Delta Integration (Phase 2)

The cognitive sensor now integrates with Delta Kernel:

### Contract Validation
All exports are validated against JSON Schema before writing:
- `export_cognitive_state.py` → `CognitiveMetricsComputed.json`
- `export_daily_payload.py` → `DailyPayload.v1.json`
- `build_projection.py` → `DailyProjection.v1.json`

### Daily Projection
A combined artifact at `data/projections/today.json` merges cognitive state and directive.

### C→D Bridge
`push_to_delta.py` POSTs the projection to Delta API at `POST /api/ingest/cognitive`.

### New Scripts
| File | Purpose |
|------|---------|
| `validate.py` | Contract validation module |
| `build_projection.py` | Builds combined `today.json` |
| `push_to_delta.py` | POSTs to Delta API |

---

## Vectorization

The system now includes **semantic understanding** via sentence embeddings.

**What it adds:**
- Semantic loop detection (understands meaning, not just keywords)
- Natural language search across all conversations
- Automatic topic clustering and theme discovery
- Better accuracy (finds paraphrases, synonyms, related concepts)

**Quick start:**
```bash
pip install -r requirements.txt
python init_embeddings.py
python semantic_loops.py
```

**Full docs:** See `VECTORIZATION.md` and `QUICKSTART_VECTORIZATION.md`

---

## Daily Workflow

### Every Morning

```bash
# From repo root:
.\scripts\run_all.ps1

# Or run cognitive sensor only:
python services/cognitive-sensor/refresh.py
```

This runs the complete system refresh:
1. Detects open loops from conversation history
2. Calculates completion statistics
3. Exports cognitive state
4. Generates daily routing directive
5. Creates payload with execution law
6. Wires data to CycleBoard brain folder
7. Updates state history log
8. Builds analytics dashboard

**Output:**
- `cognitive_state.json` - Your brain's current state
- `daily_payload.json` - Today's execution law
- `daily_directive.txt` - Human-readable routing
- `STATE_HISTORY.md` - Timestamped state log
- `dashboard.html` - Analytics interface

### View Your Command Center

```bash
# Start web server for control panel
cd services/cognitive-sensor
python -m http.server 8080
```

Open: `http://localhost:8080/control_panel.html`

### Launch CycleBoard

Open `services/cognitive-sensor/cycleboard_app3.html` in your browser.

You'll see:
- Red/yellow/green directive banner based on mode
- Your required action for today
- Risk level indicator
- Interface lockouts if build is not allowed

### Make Decisions on Loops

When the system surfaces a loop that needs closure:

```bash
cd services/cognitive-sensor
python decide.py
```

Choose:
- **1 = CLOSE** - Mark loop as resolved
- **2 = CONTINUE** - Keep working on it
- **3 = ARCHIVE** - Consciously abandon it

The system tracks your decision and will never resurface closed/archived loops.

## Routing Logic

The system uses simple, transparent rules to determine your daily mode:

### CLOSURE Mode (Red)
**Triggers:**
- Closure ratio < 15%
- OR open loops > 20

**Result:**
- `build_allowed: false` (locks create functionality)
- `risk: HIGH`
- Primary action: Close or archive specific loop

### MAINTENANCE Mode (Yellow)
**Triggers:**
- Open loops > 10 (but < 20)
- AND closure ratio >= 15%

**Result:**
- `build_allowed: true`
- `risk: MEDIUM`
- Primary action: Review specific loop

### BUILD Mode (Green)
**Triggers:**
- Open loops <= 10
- AND closure ratio >= 15%

**Result:**
- `build_allowed: true`
- `risk: LOW`
- Primary action: Create freely

## File Reference

### Core Scripts

| File | Purpose |
|------|---------|
| `init_results_db.py` | Builds messages table from memory_db.json |
| `init_topics.py` | Extracts topic weights from conversations |
| `init_convo_time.py` | Adds timestamps to database |
| `init_titles.py` | Loads conversation titles for loop detection |
| `radar.py` | Shows what's rising/fading/constant in attention |
| `loops.py` | Detects unfinished conversations with high intent |
| `resurfacer.py` | Surfaces one unresolved loop weekly |
| `decide.py` | Interactive tool to close/continue/archive loops |
| `completion_stats.py` | Calculates closure metrics |
| `cognitive_api.py` | Machine-readable query interface |
| `export_cognitive_state.py` | Exports brain state as JSON |
| `route_today.py` | Generates daily directive text |
| `export_daily_payload.py` | Creates execution law JSON |
| `wire_cycleboard.py` | Copies data to CycleBoard brain folder |
| `reporter.py` | Logs state to STATE_HISTORY.md |
| `build_dashboard.py` | Generates analytics HTML |
| `refresh.py` | **Master script - runs entire pipeline** |

### Data Files

| File | Content |
|------|---------|
| `results.db` | SQLite database (messages, topics, convo_time, convo_titles, loop_decisions) |
| `memory_db.json` | Source data (140MB conversation archive) |
| `cognitive_state.json` | Live brain state (loops, drift, closure metrics) |
| `daily_payload.json` | Execution law (mode, build_allowed, primary_action, risk) |
| `daily_directive.txt` | Human-readable routing directive |
| `loops_latest.json` | Current top 15 open loops with scores |
| `completion_stats.json` | Weekly and lifetime closure statistics |
| `STATE_HISTORY.md` | Rolling log of cognitive state snapshots |

### Interfaces

| File | Purpose |
|------|---------|
| `dashboard.html` | Analytics dashboard (state, loops, completion, anchors) |
| `control_panel.html` | Master control interface with action buttons |
| `cycleboard_working.html` | Planning tool with cognitive directive overlay |

### Self-Analysis Profiles

Deep pattern analysis extracted from 40,946 messages and 2.3 million words:

| File | Content |
|------|---------|
| `THE_CYCLE.md` | The 5-step stuck loop: INTEND → OBSTACLE → JUSTIFY → DISMISS → RESET |
| `DERAILMENT_FACTORS.md` | Top 10 things that knock you off course (phone, exhaustion, disrespect) |
| `CONVERSATION_PATTERNS.md` | How you talk, what about, repetitive phrases |
| `EMOTIONAL_PROFILE.md` | Complete emotional landscape (triggers, coping, needs) |
| `DEEP_PSYCHOLOGICAL_PROFILE.md` | Core wounds, attachment style, values hierarchy, defenses |
| `GROWTH_REPORT.md` | Cognitive fallacies, blindspots, projections, growth opportunities |

## Database Schema

### messages
```sql
convo_id TEXT
role TEXT          -- system/user/assistant
words INTEGER      -- word count
chars INTEGER      -- character count
```

### topics
```sql
convo_id TEXT
topic TEXT         -- normalized keyword
weight INTEGER     -- frequency in conversation
```

### convo_time
```sql
convo_id TEXT
date TEXT          -- YYYY-MM-DD
```

### convo_titles
```sql
convo_id TEXT
title TEXT         -- conversation title from ChatGPT
```

### loop_decisions
```sql
convo_id TEXT
decision TEXT      -- CLOSE/CONTINUE/ARCHIVE
date TEXT          -- YYYY-MM-DD HH:MM
```

## Loop Detection Algorithm

Loops are scored using:

```python
score = user_words + (intent_topic_weight × 30) - (done_topic_weight × 50)
```

**Intent topics:** want, need, should, plan, going, gonna, start, try, build, create, make, learn, begin

**Done topics:** did, done, finished, completed, solved, shipped, fixed, achieved

High scores = lots of intention with no completion signals = open loop

## Understanding Your Metrics

### Closure Ratio
```
closed_loops / (closed_loops + archived_loops)
```

**What it means:**
- 100% = You close everything you start
- 50% = Half closed, half abandoned
- 0% = You abandon everything

**Your current ratio:** 6.67% (1 archived, 0 closed out of 15 total)

### Open Loop Count
Number of unresolved conversations with high intent signals.

**What it means:**
- < 10 = Healthy backlog
- 10-20 = Warning zone
- > 20 = Cognitive overload

**Your current count:** 14 loops

### Risk Level
Derived from closure ratio and loop count:
- **HIGH** = Pattern of abandonment, backlog building
- **MEDIUM** = Manageable but needs attention
- **LOW** = Healthy completion behavior

**Your current risk:** HIGH

## Automation Setup

### Weekly Resurfacing (Optional)

Open Task Scheduler → Create Basic Task:
- **Name:** Cognitive Resurfacer
- **Trigger:** Weekly (pick a day/time)
- **Action:** Start a program
  - Program: `python`
  - Arguments: `resurfacer.py`
  - Start in: `<repo-root>\services\cognitive-sensor`

This will append one unresolved loop to `RESURFACER_LOG.md` every week.

### Weekly State Snapshot (Optional)

Open Task Scheduler → Create Basic Task:
- **Name:** Cognitive State Reporter
- **Trigger:** Weekly (pick a day/time)
- **Action:** Start a program
  - Program: `python`
  - Arguments: `reporter.py`
  - Start in: `<repo-root>\services\cognitive-sensor`

This logs your radar output to `STATE_HISTORY.md` automatically.

## Troubleshooting

### "Failed to fetch" errors in browser

**Cause:** Browsers block file:// protocol for security.

**Fix:** Always use a local web server:
```bash
python -m http.server 8080
```

Then open `http://localhost:8080/filename.html`

### "No module named X" errors

**Cause:** Missing Python dependencies.

**Fix:** This system has no external dependencies. Uses only Python standard library.

### Empty or missing data files

**Cause:** Scripts not run in correct order.

**Fix:** Run the full refresh:
```bash
python refresh.py
```

This runs all scripts in correct dependency order.

### Loops not disappearing after archiving

**Cause:** Need to regenerate loops_latest.json

**Fix:**
```bash
python loops.py
```

Closed/archived loops are automatically filtered out.

## Design Principles

### 1. Single Source of Truth
One canonical database (`results.db`), one cognitive state file (`cognitive_state.json`), one execution law (`daily_payload.json`). No conflicting data sources.

### 2. Transparent Logic
All routing rules are visible, simple, and deterministic. No black boxes.

### 3. Minimal Decision Surface
One directive, one action. Not 47 metrics to interpret.

### 4. Enforcement Over Suggestion
Interfaces lock when rules are violated. Not recommendations - laws.

### 5. Feedback Loop Closure
Decisions feed back into tomorrow's routing. The system learns your patterns.

## What This System Protects You From

1. **Project Abandonment**
   - Detects unfinished work
   - Forces closure decisions
   - Prevents new starts until old work is resolved

2. **Cognitive Drift**
   - Tracks attention patterns over time
   - Alerts when focus shifts away from execution
   - Shows what you're orbiting vs. what you're building

3. **Invisible Loops**
   - Surfaces forgotten intentions
   - Quantifies the gap between intent and completion
   - Makes unconscious patterns visible

4. **False Productivity**
   - Measures closure, not activity
   - Distinguishes creation from consumption
   - Tracks completion ratio, not task count

## Limitations

### What This System Cannot Do

- **Motivate you** - It only reports and restricts
- **Force compliance** - You can ignore the red banner
- **Read your mind** - Only analyzes text, not context
- **Predict future** - Based on historical patterns only
- **Handle nuance** - Some "abandoned" projects may be appropriately dropped

### Known Edge Cases

- **False positive loops:** Exploratory conversations marked as "unfinished"
- **Context blind:** Can't tell if a project should be abandoned
- **Historical lock:** Based on old data until you update it
- **Binary thinking:** Doesn't understand partial progress

## Privacy & Security

### What Data Is Stored

- **All of it:** Every ChatGPT conversation you've exported
- **Locally only:** No cloud sync, no external servers
- **Plain text:** Database is unencrypted SQLite

### Who Has Access

- **You:** Full control of all data files
- **No one else:** System is entirely local

### How to Delete

```bash
# Keep scripts, delete data only
rm results.db memory_db.json cognitive_state.json daily_payload.json
```

## Philosophy

This system is built on three premises:

1. **You cannot change what you cannot see**
   - Unconscious patterns remain invisible without measurement
   - Objective data reveals self-deception

2. **Knowledge without enforcement is useless**
   - Knowing you abandon projects doesn't stop you
   - Locking the interface forces the decision

3. **The best governor is yourself**
   - Not imposed rules from others
   - Your own behavioral history enforcing discipline

## Success Metrics

The system is working if:

1. **Closure ratio rises over time** (tracked weekly in completion_stats.json)
2. **Open loop count decreases** (visible in control panel)
3. **You spend more time in BUILD mode** (logged in STATE_HISTORY.md)
4. **Red banners become rare** (MODE shifts from CLOSURE to BUILD)

The system is failing if:

1. You ignore the directive and build anyway
2. Loops accumulate faster than you close them
3. You stop running `refresh.py` daily
4. The control panel becomes wallpaper

## Next Steps

### If You're New to This System

1. Run `python refresh.py` to generate fresh state
2. Open `http://localhost:8080/control_panel.html` to see your status
3. Read your directive in `daily_directive.txt`
4. Follow the primary action (close a loop if in CLOSURE mode)
5. Run `python decide.py` to record your decision
6. Repeat tomorrow

### If You Want to Extend It

**Potential additions:**
- ✅ **Semantic topic analysis** - IMPLEMENTED! See `VECTORIZATION.md`
- Streak tracking (days in BUILD mode)
- Goal resurfacing (detect recurring themes)
- Energy level correlation (time of day patterns)
- Execution velocity (time from intent to completion)

**Architecture supports:**
- Additional routing modes beyond CLOSURE/MAINTENANCE/BUILD
- Multiple governance surfaces (email, calendar, etc.)
- Federated state (combine multiple data sources)
- Priority weighting (some loops matter more)

### If You Want to Share It

This system is personal by design. To share:

1. Remove your `memory_db.json` (contains all your conversations)
2. Clear `results.db` (contains your data)
3. Keep all `.py` scripts and `.html` interfaces
4. Share the README and architecture

The scripts are general-purpose. The data is yours alone.

## Credits

Built in a single conversation on 2026-01-03.

**Core insight:** Most people need tracking. Some people need governance.

**Architectural principle:** Make the unconscious visible, then make it enforceable.

**Design philosophy:** The best productivity system is the one that prevents you from being productive in the wrong way.

---

## Quick Reference

**Morning routine:**
```bash
# From repo root:
.\scripts\run_all.ps1
```

**View command center:**
`http://localhost:8080/control_panel.html`

**Start CycleBoard:**
Open `services/cognitive-sensor/cycleboard_app3.html`

**Close a loop:**
```bash
cd services/cognitive-sensor
python decide.py
```

**Current status:**
- Mode: CLOSURE
- Risk: HIGH
- Open loops: 14
- Closure ratio: 6.67%
- Primary action: Close or archive "Extrinsic vs Intrinsic Rewards"

---

*This is not a tool. This is a law.*

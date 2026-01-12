# Quick Start Guide

## 5-Minute Setup

### 1. Run the system
```bash
cd services/cognitive-sensor
python refresh.py
```

**What this does:**
- Analyzes all 1,397 conversations
- Detects 14 open loops
- Calculates 6.67% closure ratio
- Determines you're in CLOSURE mode (HIGH RISK)
- Generates today's directive

**Takes:** ~30 seconds

---

### 2. See your status
```bash
python -m http.server 8080
```

Open browser: `http://localhost:8080/control_panel.html`

**You'll see:**
- Current mode: CLOSURE (red)
- Risk: HIGH
- Open loops: 14
- Your required action today

**Purpose:** Master control interface

---

### 3. Follow the directive

Your system says:
> **Close or archive: Extrinsic vs Intrinsic Rewards**

Make the decision:
```bash
python decide.py
```

Choose:
- `1` = CLOSE (mark it done)
- `3` = ARCHIVE (consciously abandon it)

**This is the core loop.**

---

### 4. See the change

Run refresh again:
```bash
python refresh.py
```

Open control panel: `http://localhost:8080/control_panel.html`

**What changed:**
- Closure ratio went up (if you closed)
- Open loops: 13 (down from 14)
- Risk may have dropped to MEDIUM

**The system learned from your decision.**

---

## Daily Routine

### Morning (2 minutes)
```bash
cd services/cognitive-sensor
python refresh.py
python -m http.server 8080
```

Open: `http://localhost:8080/control_panel.html`

Read your directive. Follow it.

### Evening (1 minute)
If you closed a loop today:
```bash
python decide.py
```

Record the decision.

---

## That's It

The system now:
- ✅ Tracks your behavior
- ✅ Detects patterns
- ✅ Generates law
- ✅ Enforces through interface
- ✅ Learns from decisions

**Tomorrow:** Repeat the routine. The directive will change based on what you did today.

---

## What Success Looks Like

**Week 1:**
- Mode: CLOSURE (red banner every day)
- You close 1-2 loops
- Ratio climbs from 6.67% → 15%

**Week 2:**
- Mode: MAINTENANCE (yellow banner)
- Open loops drop from 14 → 10
- Risk: MEDIUM

**Week 4:**
- Mode: BUILD (green banner)
- Open loops: 8
- Ratio: 30%
- Risk: LOW

**The red banner becomes rare. That's the goal.**

---

## Troubleshooting

**"Failed to fetch" in browser**
→ Use `python -m http.server 8080`, not `file://`

**"No loops found"**
→ Run `python loops.py` first

**"Directive says OFFLINE"**
→ Run `python refresh.py`

**Still confused?**
→ Read `README.md` for full documentation

---

## Core Principle

This system has one job:

**Prevent you from starting new projects until you finish old ones.**

Everything else is infrastructure to support that mission.

The red banner isn't motivation. It's a lock.

Follow the law, and it opens.

Ignore it, and it persists.

Simple.

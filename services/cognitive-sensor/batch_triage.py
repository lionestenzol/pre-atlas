"""
Batch Loop Triage — Phase 2
One-shot script: records 14 loop decisions into loop_decisions table.
Dispositions reviewed in the Unblock & Ship Proposal (2026-02-12).
Safe to delete after use.
"""
import sqlite3
from datetime import datetime

DECISIONS = [
    ("1356", "ARCHIVE",   "Extrinsic vs Intrinsic Rewards"),
    ("1209", "ARCHIVE",   "Irritation and Hunger Struggles"),
    ("81",   "ARCHIVE",   "Universal Programming Table Setup"),
    ("1247", "ARCHIVE",   "Understanding Gaslighting Effects"),
    ("1136", "ARCHIVE",   "Understanding Doublespeak"),
    ("1075", "ARCHIVE",   "What is Psychology"),
    ("1222", "ARCHIVE",   "Awkward Growth Calibration Phase"),
    ("715",  "CLOSE",     "C957 Knowledge Base Summary"),
    ("546",  "ARCHIVE",   "Anger and Intensity"),
    ("1006", "ARCHIVE",   "CRM Process Analysis"),
    ("968",  "ARCHIVE",   "The Power of Pleasing"),
    ("753",  "CLOSE",     "Quiz Solutions and Explanations"),
    ("1334", "CONTINUE",  "AI Workflow Orchestration"),
    ("1215", "ARCHIVE",   "Understanding Relationship Dynamics"),
]

con = sqlite3.connect("results.db")
cur = con.cursor()

# Check for existing decisions to avoid duplicates
existing = {r[0] for r in cur.execute("SELECT convo_id FROM loop_decisions").fetchall()}

now = datetime.now().strftime("%Y-%m-%d %H:%M")
inserted = 0
skipped = 0

for convo_id, decision, title in DECISIONS:
    if convo_id in existing:
        print(f"  SKIP  {title} (already decided)")
        skipped += 1
        continue
    cur.execute(
        "INSERT INTO loop_decisions (convo_id, decision, date) VALUES (?, ?, ?)",
        (convo_id, decision, now)
    )
    print(f"  {decision:8s}  {title}")
    inserted += 1

con.commit()
con.close()

print(f"\nDone: {inserted} recorded, {skipped} skipped (already decided).")

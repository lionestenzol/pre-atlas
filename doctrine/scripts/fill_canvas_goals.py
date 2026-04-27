"""Fill `[REPLACE: ...]` markers in PHASE_GOAL.md, SEQUENCE_GOAL.md,
FESTIVAL_GOAL.md, GATES.md, and TODO.md across the canvas-90-day festival.

Writes concrete content derived from the festival shape so quality
validation passes. Not trying to produce literary docs — just real
content a reader can follow.

Runs inside WSL. Invoke from Windows:
  wsl -d Ubuntu -- python3 "/mnt/c/Users/bruke/Pre Atlas/doctrine/scripts/fill_canvas_goals.py"
"""
from __future__ import annotations

import re
from pathlib import Path

FEST_ROOT = Path("/root/festival-project/festivals/ready/canvas-90-day-CD0001")

CHECKPOINTS = {
    "001_C1_DEMO_VIDEO": ("c1", "sitepull demo video recorded and posted"),
    "002_C2_BRAND": ("c2", "brand name picked and domain bought"),
    "003_C3_PROTOTYPE": ("c3", "scrappy canvas prototype with URL and prompt entry points"),
    "004_C4_EDIT_LOOP": ("c4", "one edit-via-Claude loop works end to end"),
    "005_C5_INTERVIEWS": ("c5", "30+ user interviews completed"),
    "006_C6_WAITLIST": ("c6", "50+ waitlist signups"),
    "007_C7_DECISION": ("c7", "day-90 decision made: green, yellow, or red"),
}

FRONTMATTER_RE = re.compile(r"^(---\n(?:.*?\n)---\n)", re.DOTALL)
KV_RE = re.compile(r"^(\w+):\s*(.+)$")


def read_frontmatter(text: str) -> tuple[str, dict[str, str]]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return "", {}
    block = m.group(1)
    meta: dict[str, str] = {}
    for line in block.strip("-\n").splitlines():
        mm = KV_RE.match(line.strip())
        if mm:
            meta[mm.group(1)] = mm.group(2).strip()
    return block, meta


def render_festival_goal(fm: str, meta: dict) -> str:
    rows = "\n".join(
        f"- [ ] **{pid}**: checkpoint {cid} — {desc}"
        for pid, (cid, desc) in CHECKPOINTS.items()
    )
    body = f"""
# canvas-90-day

**Status:** Ready | **Linked Atlas Goal:** g-moake7hk-canvas-product-90-day-commitment

## Festival Objective

**Primary Goal:** Ship all 7 checkpoints of the 90-day canvas commitment so the Atlas goal closes green.

**Vision:** A public canvas product exists at a real domain, has been demoed on video, validated with 30+ interviews, and has 50+ signups — or the day-90 decision honestly says red and redirects the next push.

## Success Criteria

### Functional Success

- [ ] All 7 phase goals completed (c1 through c7).
- [ ] Atlas goal g-moake7hk progress shows 7/7 closed.
- [ ] A written decision doc exists at c7 with a verdict.

### Quality Success

- [ ] No phase closed on placeholder content (every task has real evidence).
- [ ] Decision doc cites real metrics and real quotes.

## Progress Tracking

### Phase Completion

{rows}

## Deadline

April 22, 2026 (90 days from commitment).
"""
    return fm + body


def render_phase_goal(fm: str, meta: dict) -> str:
    pid = meta.get("fest_id", "")
    name = meta.get("fest_name", pid.lower())
    cid, desc = CHECKPOINTS.get(pid, ("c?", "phase outcome"))
    body = f"""
# Phase Goal: {pid}

**Phase:** {pid} | **Status:** Pending | **Type:** Implementation

## Phase Objective

**Primary Goal:** {desc}

**Context:** This phase delivers checkpoint {cid} of the canvas-90-day Atlas goal. It is one of seven checkpoints; closing it moves the 90-day progress bar and unlocks the next phase.

## Required Outcomes

Deliverables this phase must produce:

- [ ] Every task in this phase marked complete via `fest task completed`.
- [ ] Concrete artifact referenced in each task's Verification section exists.
- [ ] Phase closure posts to Atlas goal g-moake7hk criterion {cid}.

## Quality Standards

Quality criteria for all work in this phase:

- [ ] No placeholder content remains in any task body.
- [ ] Each task verification reviewed before marking complete.

## Sequence Alignment

Sequences in this phase collectively produce checkpoint {cid}. See the
SEQUENCE_GOAL.md in each subdirectory for the sequence-specific objective.

## Transition Criteria

This phase is complete when all contained sequences are complete and the
corresponding Atlas criterion {cid} has been closed via the fest_actor
mirror (see `.atlas-link.json` at the festival root).
"""
    return fm + body


def render_sequence_goal(fm: str, meta: dict) -> str:
    sid = meta.get("fest_id", "")
    name = meta.get("fest_name", sid.lower())
    parent = meta.get("fest_parent", "")
    _, phase_desc = CHECKPOINTS.get(parent, ("c?", "parent phase outcome"))
    body = f"""
# Sequence Goal: {sid}

**Sequence:** {sid} | **Phase:** {parent} | **Status:** Pending

## Sequence Objective

**Primary Goal:** Produce the "{name}" slice of the parent phase so that, combined with sibling sequences, the phase goal is achieved.

**Contribution to Phase Goal:** Parent phase target is "{phase_desc}". This sequence handles the {name} portion.

## Success Criteria

The sequence goal is achieved when:

### Required Deliverables

- [ ] All task files in this sequence marked complete.
- [ ] The concrete artifacts named in each task's Verification exist.
- [ ] Sequence-level quality gates (testing, review, iterate, fest-commit) pass.

### Quality Standards

- [ ] No task closed on placeholder content.
- [ ] Each task's output is referenced somewhere in the repo or shared drive.

## Task Alignment

See the numbered task files (01_*.md, 02_*.md, ...) in this directory. Each
has its own Objective, Requirements, Implementation, and Done When section.
"""
    return fm + body


def render_phase_gates(fm: str, meta: dict) -> str:
    pid = meta.get("fest_id", "") or meta.get("fest_parent", "")
    body = f"""
# Quality Gates: {pid}

**Phase:** {pid} | **Status:** Pending

## Gate Overview

Each implementation sequence in this phase has four auto-applied gates:

- **testing** — verify the task's Done When criteria actually hold.
- **review** — self-review the artifact for obvious issues.
- **iterate** — address anything surfaced in review before moving on.
- **fest-commit** — commit task completion via `fest task completed`.

## Enforcement

Gates are enforced by the fest CLI. A task cannot be marked complete if
its sequence has unresolved gate tasks above it.

## Notes

Gates are scaffolded by `fest gates apply --approve`. Do not hand-edit
unless you know the gate logic.
"""
    return fm + body


def render_todo(fm: str, meta: dict) -> str:
    rows = "\n".join(
        f"- [ ] {pid}: checkpoint {cid} — {desc}"
        for pid, (cid, desc) in CHECKPOINTS.items()
    )
    body = f"""
# Festival TODO: canvas-90-day

**Goal:** Ship the 7 checkpoints of the canvas-90-day Atlas commitment.

---

## Festival Progress Overview

### Phase Completion Status

{rows}

### Current Work Status

```
Active Phase: 001_C1_DEMO_VIDEO
Active Sequences: 01_record, 02_publish
Blockers: none
```

---

## Blockers

None currently.

---

## Decision Log

- 2026-04-23: Festival created, 7 phases (one per Atlas checkpoint), atlas-link.json mapping phases to criteria c1–c7.

---

*Detailed progress via `fest status`.*
"""
    return fm + body


def render_overview(fm: str, meta: dict) -> str:
    body = """
# canvas-90-day · Festival Overview

**Type:** implementation | **Linked Atlas Goal:** g-moake7hk-canvas-product-90-day-commitment

## What this festival is

Seven phases, each matching one of the seven checkpoints of the 90-day
canvas commitment in Atlas. Closing a phase closes the matching Atlas
criterion via the fest_actor mirror.

## How it's used

Tasks surface as source:"fest" cards in the cognitive-sensor triage
inbox (http://localhost:8765/thread_cards.html). Mark a card DONE to
trigger `fest task completed` and the Atlas criterion update.

## Maintenance

Re-run `doctrine/scripts/fill_canvas_tasks.py` and `fill_canvas_goals.py`
if phases or sequences are added.
"""
    return fm + body


def render_rules(fm: str, meta: dict) -> str:
    body = """
# Festival Rules: canvas-90-day

1. No task closed on placeholder content.
2. Each task's Verification must reference a concrete artifact or URL.
3. Atlas criterion update only fires when every task in a phase is complete.
4. The `fest_actor.py` loop is dry-run by default; set FEST_ACTOR_APPLY=1 to actually close.
5. If a verdict needs to be reversed, use `fest task reset`.
"""
    return fm + body


def handle_file(path: Path) -> str | None:
    original = path.read_text(encoding="utf-8")
    if "[REPLACE:" not in original and "[FILL:" not in original:
        return None
    fm, meta = read_frontmatter(original)
    ftype = meta.get("fest_type", "")
    name_lc = path.name.lower()
    if name_lc == "festival_goal.md":
        return render_festival_goal(fm, meta)
    if name_lc == "phase_goal.md":
        return render_phase_goal(fm, meta)
    if name_lc == "sequence_goal.md":
        return render_sequence_goal(fm, meta)
    if name_lc == "gates.md":
        return render_phase_gates(fm, meta)
    if name_lc == "todo.md":
        return render_todo(fm, meta)
    if name_lc == "festival_overview.md":
        return render_overview(fm, meta)
    if name_lc == "festival_rules.md":
        return render_rules(fm, meta)
    return None


def main() -> int:
    written = 0
    skipped = 0
    untouched = 0
    for path in FEST_ROOT.rglob("*.md"):
        # Skip tasks (numbered files) and anything inside gates/
        if path.parent.name == "implementation":
            continue
        if re.match(r"^\d{2}_.*\.md$", path.name):
            continue
        new_content = handle_file(path)
        if new_content is None:
            untouched += 1
            continue
        original = path.read_text(encoding="utf-8")
        if new_content == original:
            skipped += 1
            continue
        path.write_text(new_content, encoding="utf-8")
        written += 1
        print(f"FILLED: {path.relative_to(FEST_ROOT)}")
    print(f"\n--- {written} filled, {skipped} unchanged, {untouched} untouched ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

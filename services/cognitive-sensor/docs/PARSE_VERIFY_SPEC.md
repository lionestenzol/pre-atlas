# Concept Parse + Coverage Verify — Spec

Two-step coverage audit: extract what a thread discussed, then check whether
a built artifact actually covers it.

## Step 1 — `parse_conversation.py`

### Purpose

Extract a concept checklist from a ChatGPT thread. Three kinds:

| kind | source | signal |
|---|---|---|
| `technical` | whole thread text | library/framework regex hits (Flask, React Native, OpenAI, ...) |
| `idea` | user messages | aspirational / framing phrases ("I want...", "my goal is...") |
| `decision` | user messages | resolution phrases ("let's go with...", "final answer...") |

### Usage

```bash
python parse_conversation.py <convo_id>
```

Outputs:
- `harvest/<id>_<slug>/concepts.json` — `{convo_id, title, counts, concepts[]}`
- `harvest/<id>_<slug>/concepts.md` — checklist with unchecked boxes

### Token cost

**Zero.** Pure local regex heuristics.

### Concept shape

```json
{
  "id": "T3",
  "kind": "technical",
  "label": "Flask HTTP server",
  "evidence_quote": "...from flask import Flask, jsonify...",
  "msg_range": [38, 38],
  "signal": "flask-server",
  "hit_count": 9
}
```

### Extending

Add a row to `TECH_SIGNATURES` in `parse_conversation.py`:

```python
("my-thing", re.compile(r"pattern"), "Human-readable label"),
```

Then add a matching entry to `VERIFIERS` in `verify_coverage.py`.

---

## Step 2 — `verify_coverage.py`

### Purpose

Given a thread's `concepts.json` and a built artifact (dir or file), check
whether each technical concept has evidence in the artifact. Idea and
decision concepts are marked `unverifiable` — they need human review.

### Usage

```bash
python verify_coverage.py <convo_id> <artifact_path>
```

`<artifact_path>` is relative to repo root (e.g. `apps/ai-exec-pipeline`).

Outputs:
- `harvest/<id>_<slug>/coverage.json`
- `harvest/<id>_<slug>/coverage.md` — table with status per concept

### Status values

| status | meaning |
|---|---|
| `covered` | content regex matched in at least one text file |
| `partial` | filename matched but no content match |
| `missing` | no match anywhere |
| `unverifiable` | idea/decision — not machine-checkable |

### How it checks

For each technical concept:
1. Walks artifact dir, reads all text files (≤ common code/config extensions).
2. Skips `node_modules`, `__pycache__`, `.venv`, `dist`, `build`.
3. For each `VERIFIERS[signal].content` regex, searches every file.
4. For each `VERIFIERS[signal].files` glob, checks for file presence.
5. Records first 5 evidence items.

### Token cost

**Zero.** Pure grep.

---

## CLI

Both are wired into CycleBoard CLI:

```bash
cycleboard parse <id>                 # produce concepts
cycleboard verify <id> <artifact>     # check coverage
cycleboard help parse                 # detailed help
cycleboard help verify
```

## Example — thread #487 vs `apps/ai-exec-pipeline`

```
covered: 8     Flask, requests, polling loop, JSON persistence, CORS,
               API-key auth, iteration tracker, execution pipeline
missing: 8     OpenAI, Google Drive, React Native, React web, axios,
               Flutter/Dart, WebSocket, report generation
unverifiable: 27   ideas (25) + decisions (2) — manual review in concepts.md
```

Interpretation: the built spine covers the core backend concepts. The
mobile client, cloud sync, LLM integration, and report generator were
discussed in the thread but never built — matches the README's
"intentionally dropped" note.

## Relationship to other harvest outputs

| File | Content | Purpose |
|---|---|---|
| `summary.md` | stats + topics | skim the thread at a glance |
| `code_blocks.md` | all unique code blocks | raw material to port |
| `key_quotes.md` | sentiment hits | mood/resolution of thread |
| `final_output.md` | last exchanges | how the thread ended |
| `conversation.md` | full transcript | deep read |
| **`concepts.md`** | **what was discussed** | **checklist** |
| **`coverage.md`** | **what you built vs discussed** | **audit** |

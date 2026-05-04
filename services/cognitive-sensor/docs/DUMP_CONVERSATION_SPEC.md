# dump_conversation.py — Spec

## Purpose

Dumps a single ChatGPT conversation from `memory_db.json` to a full
markdown transcript. Fills the gap between `harvester.py` (which only
extracts code blocks / key quotes / summary) and the raw archive.

## Location

`services/cognitive-sensor/dump_conversation.py`

## Inputs

- `convo_id` (int, positional): index into `memory_db.json`. Range: `0 .. 1396`.
- `--out <path>` (optional): override output path.

## Behavior

1. Loads `services/cognitive-sensor/memory_db.json` (≈140 MB, 1397 threads).
2. Indexes `memory[convo_id]` → `{title, messages[]}`.
3. Extracts `msg["text"]` from each message (fallbacks to `content` if
   present, handling string / list / dict shapes).
4. Writes a markdown file with one `## [idx] ROLE` section per message.

## Output Location

- **Default:** if a matching harvest folder exists at
  `harvest/<convo_id>_<slug>/`, writes `conversation.md` inside it.
  This makes it sit alongside `code_blocks.md`, `summary.md`, etc.
- **Fallback:** if no harvest folder exists, writes to
  `services/cognitive-sensor/conversation_<convo_id>.md`.
- **Override:** `--out <path>` bypasses both and writes exactly where specified.

## Output Format

```markdown
# Conversation #<id>: <title>

- messages: <N>
- user: <U>
- assistant: <A>

---

## [<idx>] USER

<text>

---

## [<idx>] ASSISTANT

<text>

---
```

Empty messages (e.g. the system prompt) are skipped silently.

## Usage

```bash
cd services/cognitive-sensor

python dump_conversation.py 487
# → harvest/487_marketing-for-beginners/conversation.md

python dump_conversation.py 81 --out /tmp/big-thread.md
# → /tmp/big-thread.md
```

## Integration

Exposed via the CycleBoard CLI as `cycleboard dump <convo_id>`. The CLI
command shells out to the Python script.

## Relationship to harvester.py

| Script | Extracts |
|---|---|
| `harvester.py` | code blocks, key quotes, final output, summary, manifest |
| `dump_conversation.py` | full transcript (every user/assistant turn) |

The harvester runs at triage time (once per verdict). `dump_conversation.py`
is run on demand when you need to read a thread end-to-end.

## Size Reference

Thread #487 "Marketing for Beginners": 268 messages, 620,561 chars → 645 KB markdown.

## Dependencies

Standard library only. No install step.

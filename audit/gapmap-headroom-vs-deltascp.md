# Gap-map: headroom vs delta-scp

**Date:** 2026-06-22
**Verdict:** They don't compete — they compose. headroom is a candidate *front-stage* that
fills delta-scp's blind spot (runtime ephemera), not a rival compressor.

> ⚠️ delta-scp column = grounded in real source (skill mirrors `services/delta-scp`).
> headroom column = README claim only. This session's GitHub API is the synthetic one
> (star counts fabricated; `chopratejas/headroom` redirected to `headroomlabs-ai/headroom`).
> The determinism question below MUST be answered against real github.com source.

## The two axes

| | delta-scp (grounded) | headroom (claim — unverified) |
|---|---|---|
| Compresses | Repo **structure** — file tree + symbols per file | Runtime **ephemera** — tool outputs, logs, RAG chunks, conversation |
| Metaphor | Map of the territory (codebase shape) | Transcript of the journey (agent per-turn I/O) |
| When | Once, on a repo URL/path → static skeleton | Continuously, mid-loop, as tool spam accrues |
| Input | A repository | The stream flowing into the LLM each turn |
| Output | Symbolic JSON skeleton, ~90–97% token cut | Compressed version of that stream |
| Method | Deterministic regex symbol extraction | **UNKNOWN — load-bearing question** |
| Determinism | Yes (heuristic, repeatable) | **UNKNOWN** |

## Overlap

One edge only: headroom lists "files" and "RAG chunks" among its targets — the sliver that
grazes delta-scp's lane. Tool outputs, logs, conversation history are territory delta-scp
explicitly does NOT enter.

## The gap each leaves

delta-scp v2 state-aware pruning takes `--trace error.log` as INPUT — it assumes the raw
trace already exists at full size. It has no story for compressing that trace / grep dumps /
test output / file-read spam that piles up DURING a session. That accumulation is exactly
headroom's target.

```
headroom  ->  compresses per-turn tool/log/conversation spam
delta-scp ->  compresses the codebase skeleton (once)
             and consumes a (headroom-shrunk) trace as its pruning anchor
```

Sequential stages in one pipe, not rivals.

## THE decision question (answer by reading real source)

**Does headroom compress deterministically (structural/regex) or call an LLM to summarize?**

- Structural/deterministic -> aligned with delta-scp + Pre Atlas deterministic-substrate
  doctrine. Clean compose. Port the tool-output/log compressor as an agent-loop front-stage.
  **High ROI — adopt.**
- LLM-in-the-loop summarizer -> cost + latency + nondeterminism every turn. Violates the
  deterministic spine. **Study for ideas, do not adopt.**

Secondary: lossy-final vs lossy-with-re-expand? (Can the agent restore a stripped section?)
Re-expand = safe to wire in; lossy-final = logs only.

## Where to look (real github.com — this session's API is synthetic)

Read `headroomlabs-ai/headroom` (the redirect target):
1. **Dependency manifest** (`pyproject.toml` / `requirements.txt` / `package.json`) — does it
   import an LLM client (`anthropic`, `openai`, `litellm`, `transformers`)? An LLM dep =
   summarizer = mismatch.
2. **The core compress entrypoint** (look for `compress`, `Headroom`, `__init__`, a `core/`
   or `src/` module) — is the compression a function over tokens/strings (deterministic) or a
   model call (nondeterministic)?
3. **Re-expand / restore path** — grep for `expand`, `restore`, `rehydrate`, `original`.

Answer #1 and #2 and this gap-map closes into adopt / borrow / skip.

## Next shortlist target

`SkillSpector` vs your `~/.claude/skills/` library — the one repo with a genuinely UNFILLED
gap (you scan zero of your skills today). Run the same gap-map shape when ready.

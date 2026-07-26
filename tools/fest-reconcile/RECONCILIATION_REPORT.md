# Conversation x Portfolio Reconciliation

_Generated: 2026-05-27T19:07:52.564170_

**HOTL gate:** heuristic only. Numbers show match counts, not judgments.
Human reviews each bucket to decide what the pattern means.

## Corpus caveat (READ FIRST)

`memory_db.json` is the **ChatGPT conversation export** (see
`services/cognitive-sensor/index_chatgpt_exports.py`). It does **NOT** contain:

- Claude Code session transcripts
- `/weapon` autonomous runs
- Codex CLI invocations
- Direct shell / `gh` / `git` work outside chat

So 'shipped but NOT discussed' means: shipped without showing up in the
ChatGPT channel specifically. It does **not** mean undiscussed in any channel.
This is the point - the ChatGPT corpus is one slice of total work.

## Method

- Corpus: 6534 conversations from `memory_db.json`
- Portfolio: 140 items from `portfolio_evidence.json`
- Match: word-boundary regex on item name + dashes/underscores->spaces variant
- Window per convo: title + first 10 messages (1000 chars each)
- Match policy:
  - `unambiguous` (name has dash/digit/uppercase): search full window
  - `title_only` (single lowercase word): search title only (FP control)
  - `skipped` (in GENERIC_TERMS or < 4 chars): not measured
- Discussed threshold: >= 1 matching conversation

## Top-line counts

- **discussed_and_shipped**: 34
- **discussed_but_not_shipped**: 26
- **shipped_but_not_discussed**: 52
- **neither**: 23
- **skipped_generic_name**: 5

## The three buckets

### Bucket 1 - discussed AND shipped
Talk converged into artifact. Healthy signal.

### Items (34)

- **THING** (github_repo, band=partial, convos=1340)
  - `Billionaire Wealth Explained`
  - `Brownfield vs Greenfield Paths`
  - `Social interaction dynamics`
- **STRUDEL** (standalone_repo, band=strong, convos=129)
  - `AI Music Stack Breakdown`
  - `Pure Data vs Strudel`
  - `Music System Breakdown`
- **Downloads** (standalone_repo, band=partial, convos=53)
  - `PLR Explained`
  - `Parallax Radio Concept`
  - `Launching App with Server`
- **WallPaper** (github_repo, band=partial, convos=50)
  - `Screen visibility check`
  - `Visual Language and Aesthetics`
  - `Thought Process Structuring`
- **strudel** (github_repo, band=partial, convos=38) [title-only]
  - `Pure Data vs Strudel`
  - `Strudel music overview`
  - `Atlas Strudel Fusion`
- **perception** (pre_atlas_services, band=strong, convos=29) [title-only]
  - `Black Hibachi Chef Perception`
  - `Power Dynamics and Perception`
  - `Perception and Clarity`
- **Pre Atlas** (standalone_repo, band=strong, convos=21)
  - `Cursor as a Tool`
  - `Backend Strategic Analysis`
  - `System Breakthrough Moment`
- **delta-kernel** (pre_atlas_services, band=strong, convos=21)
  - `Codex and ChatGPT Context`
  - `Claude Codex Workflow`
  - `Backend Strategic Analysis`
- **task-manager** (standalone_repo, band=partial, convos=19)
  - `RPG Framework for Coding`
  - `RAM Issue Python Script`
  - `Claude session stuck fix`
- **cognitive-sensor** (pre_atlas_services, band=strong, convos=18)
  - `Claude Codex Workflow`
  - `Backend Strategic Analysis`
  - `Ollama Capabilities`
- **pre-atlas** (github_repo, band=strong, convos=14)
  - `System Dossier Breakdown`
  - `System Freeze Review`
  - `Claude Code System Audit`
- **MB-Lab** (github_repo, band=partial, convos=12)
  - `Virtual Casting System Design`
  - `Pose Engine Strategy`
  - `Digital Human Creation Goals`
- **aegis-fabric** (pre_atlas_services, band=strong, convos=12)
  - `Cursor as a Tool`
  - `Codex and ChatGPT Context`
  - `Claude Codex Workflow`
- **SteerPOP** (github_repo, band=partial, convos=10)
  - `GitHub Gist Explained`
  - `Etch-A-System Concept`
  - `SteerPOP Android IME Port`
- **STEMai** (standalone_repo, band=strong, convos=5)
  - `Branch · System Architecture Analysis`
  - `Multi-Model AI Relay`
  - `System Architecture Analysis`
- _...and 19 more_

### Bucket 2 - discussed but NOT shipped
Intent without execution. Potential planning-addiction signal,
BUT could also be: deliberate research, killed projects, or rename drift.
HOTL each one before concluding.

### Items (26)

- **mini-ship** (custom_skill, band=stale, convos=15)
  - `Online Income System`
  - `Semantic Compression Explained`
  - `Fleet Launch System`
- **mini-ship** (pre_atlas_tools, band=none, convos=15)
  - `Online Income System`
  - `Semantic Compression Explained`
  - `Fleet Launch System`
- **privateGPT** (standalone_repo, band=stale, convos=7)
  - `What is Docker`
  - `Ollama and Poetry Issues`
  - `Private AI Setup Guide`
- **DAPO** (github_repo, band=stale, convos=5)
  - `Colab vs Local PyTorch Install`
  - `DAPO AI Overview`
  - `Markdown conversion request`
- **my-app** (standalone_repo, band=stale, convos=4)
  - `Using ast-grep in Claude`
  - `Tailwind CSS Setup`
  - `React Goal Tracker Analysis`
- **private-gpt** (standalone_repo, band=stale, convos=3)
  - `Private AI Setup Guide`
  - `PrivateGPT Installation Guide`
  - `Install Python 3.11`
- **wasp** (github_repo, band=stale, convos=3) [title-only]
  - `Fest.build Claude Wasp Combo`
  - `Wasp full-stack framework`
  - `Tarantula hawk wasp description`
- **fest** (custom_skill, band=stale, convos=3) [title-only]
  - `Fest.build Claude Wasp Combo`
  - `Fest.build Execution Engine`
  - `Fest.build Explanation`
- **CreatorOS** (github_repo, band=stale, convos=2)
  - `Custom GPT Count Summary`
  - `AI Tools for Web Dev`
- **cookbook** (custom_skill, band=stale, convos=2) [title-only]
  - `Strudel Logic and Cookbook`
  - `Strudel Beat Cookbook Summary`
- **webos-333** (pre_atlas_apps, band=none, convos=2)
  - `Cybernetic OS Analysis`
  - `Pre-unification Pressure`
- **my_project** (standalone_repo, band=stale, convos=1)
  - `Phase 1 Setup Guide`
- **weather** (standalone_repo, band=stale, convos=1) [title-only]
  - `Cold weather tips`
- **saas-boilerplate** (github_repo, band=none, convos=1)
  - `Is Laravel free`
- **python-sdk** (github_repo, band=stale, convos=1)
  - `MCP Python SDK Overview`
- _...and 11 more_

### Bucket 3 - shipped but NOT in ChatGPT corpus
Execution outside the ChatGPT channel. Many of these are real ships
done through Claude Code / `/weapon` / autonomous runs - which the
corpus doesn't index. Counter-narrative finding: chat-as-planning
is a slice of total work, not the whole picture.

### Items (52)

- **airwindows** (standalone_repo, band=strong, convos=0) [title-only]
- **anime-js** (standalone_repo, band=partial, convos=0)
- **binre** (standalone_repo, band=strong, convos=0) [title-only]
- **competitor-monitor** (standalone_repo, band=strong, convos=0)
- **everything-claude-code** (standalone_repo, band=strong, convos=0)
- **m3p-to-fract** (standalone_repo, band=strong, convos=0)
- **mandelbulber2_install** (standalone_repo, band=strong, convos=0)
- **mb3d-blender** (standalone_repo, band=strong, convos=0)
- **mb3d_anim_demo** (standalone_repo, band=strong, convos=0)
- **my-project** (standalone_repo, band=partial, convos=0)
- **nih-plug** (standalone_repo, band=strong, convos=0)
- **operator-system** (standalone_repo, band=strong, convos=0)
- **remotion-test** (standalone_repo, band=partial, convos=0)
- **Scrapling** (standalone_repo, band=strong, convos=0)
- **scrapling-smoke** (standalone_repo, band=strong, convos=0)
- _...and 37 more_

### Bucket 4 - neither (no discussion, no ship)
Likely abandoned starts or stub artifacts. Low signal.

### Items (23)

- **cpython** (standalone_repo, band=stale, convos=0) [title-only]
- **fractal-machine** (standalone_repo, band=none, convos=0)
- **musescore-mcp** (standalone_repo, band=none, convos=0)
- **my-habit-tracker** (standalone_repo, band=stale, convos=0)
- **web-os-555** (github_repo, band=stale, convos=0)
- **FragOS** (github_repo, band=stale, convos=0)
- **nextjs-ai-chatbot** (github_repo, band=stale, convos=0)
- **m-357249** (github_repo, band=stale, convos=0)
- **joyful-analytics-symphony** (github_repo, band=stale, convos=0)
- **cpython** (github_repo, band=stale, convos=0) [title-only]
- _...and 13 more_

### Skipped (generic name)
Item names too generic to match safely (in GENERIC_TERMS or < 4 chars).
Not counted as 'undiscussed' - just unmeasurable.

### Items (5)

- **atlas** (standalone_repo, band=strong, convos=0)
- **mcp** (standalone_repo, band=none, convos=0)
- **r3f** (standalone_repo, band=none, convos=0)
- **atlas** (github_repo, band=strong, convos=0)
- **mpc** (github_repo, band=partial, convos=0)

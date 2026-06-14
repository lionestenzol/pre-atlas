# Claude Code corpus x Portfolio Reconciliation (Part B v2)

_Generated: 2026-05-27T19:13:49.209971_

**HOTL gate:** heuristic only. Numbers show match counts, not judgments.

## Corpus

- 1017 Claude Code session `.jsonl` files
  under `~/.claude/projects/**`
- Per session: extracted first user message + all user/assistant text (skipped tool_use/thinking/tool_result blocks)
- Body cap per session: 50,000 chars
- Portfolio: 140 items from `portfolio_evidence.json`

## Method

Same as `corpus_recon.py` (ChatGPT export sidecar):
- `unambiguous` (name has dash/digit/uppercase): search full session body
- `title_only` (single lowercase word): search first user message only (FP control - 'cortex' could mean prefrontal cortex)
- `skipped` (in GENERIC_TERMS or < 4 chars): not measured

## Top-line counts

- **discussed_and_shipped**: 79
- **discussed_but_not_shipped**: 33
- **shipped_but_not_discussed**: 7
- **neither**: 16
- **skipped_generic_name**: 5

## Buckets

### Bucket 1 - discussed AND shipped
Talk in Claude Code converged into artifact.

### Items (79)

- **Pre Atlas** (standalone_repo, band=strong, sessions=384)
  - `cd services/canvas-engine && npm run smoke:envelope`
  - `claude -p --permission-mode acceptEdits < "C:\Users\bruke\Pre Atlas\.claude\worktrees\zealous-mclean-a9b079\.dispatch\ph`
  - `<scheduled-task name="atlas-evening" file="C:\Users\bruke\.claude\scheduled-tasks\atlas-evening\SKILL.md"> This is an au`
- **STRUDEL** (standalone_repo, band=strong, sessions=366)
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **cognitive-sensor** (pre_atlas_services, band=strong, sessions=279)
  - `<scheduled-task name="atlas-evening" file="C:\Users\bruke\.claude\scheduled-tasks\atlas-evening\SKILL.md"> This is an au`
  - `<scheduled-task name="atlas-morning" file="C:\Users\bruke\.claude\scheduled-tasks\atlas-morning\SKILL.md"> This is an au`
  - `<scheduled-task name="atlas-evening" file="C:\Users\bruke\.claude\scheduled-tasks\atlas-evening\SKILL.md"> This is an au`
- **strudel** (github_repo, band=partial, sessions=242) [first-msg-only]
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **delta-kernel** (pre_atlas_services, band=strong, sessions=168)
  - `claude -p --permission-mode acceptEdits < "C:\Users\bruke\Pre Atlas\.claude\worktrees\zealous-mclean-a9b079\.dispatch\ph`
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `i need you to open atlas core`
- **THING** (github_repo, band=partial, sessions=135)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `i need you to open atlas core`
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
- **pre-atlas** (github_repo, band=strong, sessions=112)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="pester-2-linkedin-positioning" file="C:\Users\bruke\.claude\scheduled-tasks\pester-2-linkedin-posi`
- **Downloads** (standalone_repo, band=partial, sessions=75)
  - `Pick up Thread 2 from C:\Users\bruke\OneDrive\Desktop\claude-mining\v2\_THREAD_2_READY.md.  Read that file first — it's `
  - `what happens in we combine binre tool with es tool what can we do`
  - `Concrete steps, in order. Do them on the machine you build on. 1. Install Rust. Go to rustup.rs, run the installer. Open`
- **aegis-fabric** (pre_atlas_services, band=strong, sessions=63)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `i need you to open atlas core`
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
- **canvas-engine** (pre_atlas_services, band=strong, sessions=51)
  - `cd services/canvas-engine && npm run smoke:envelope`
  - `cd services/canvas-engine && npm run start'`
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
- **optogon** (pre_atlas_services, band=strong, sessions=49) [first-msg-only]
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `Save this as a file or paste it into the new session:  ``` # Resume — Claude/ChatGPT Export Mining Project  You're picki`
  - `@"C:\Users\bruke\OneDrive\Desktop\8423c2598d1850b1b07b3dea7436ffc88813b8ea376e3ce3af159a55b612a31b-2026-05-21-20-01-06-5`
- **STEMai** (standalone_repo, band=strong, sessions=48)
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **STEMai** (github_repo, band=partial, sessions=48)
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **anatomy-extension** (pre_atlas_tools, band=strong, sessions=41)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
- **web-audit** (standalone_repo, band=strong, sessions=39)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `ship anatomy patch 3 for SPEC 03 (canvas pre-capture) — reconsider firewall for that one.`
  - `where is anotmy at`
- **web-audit** (custom_skill, band=partial, sessions=39)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `ship anatomy patch 3 for SPEC 03 (canvas pre-capture) — reconsider firewall for that one.`
  - `where is anotmy at`
- **POLARIS** (standalone_repo, band=strong, sessions=38)
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **POLARIS** (github_repo, band=partial, sessions=38)
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
  - `<scheduled-task name="weekly-session-audit" file="C:\Users\bruke\.claude\scheduled-tasks\weekly-session-audit\SKILL.md">`
- **three-js** (standalone_repo, band=strong, sessions=33)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `i need you to connect to blender`
  - `i need you to use es tool to serarch and context and memory i need to find my debugging tool`
- **three-js** (custom_skill, band=strong, sessions=33)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `i need you to connect to blender`
  - `i need you to use es tool to serarch and context and memory i need to find my debugging tool`
- _...and 59 more_

### Bucket 2 - discussed but NOT shipped
Talked about in Claude Code; band=stale/none. Could be:
planning that didn't materialize, killed projects, or rename drift.

### Items (33)

- **mini-ship** (custom_skill, band=stale, sessions=33)
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `In C:\Users\bruke\Pre Atlas\services\canvas-engine, the helper that converts a region name to a PascalCase component nam`
- **mini-ship** (pre_atlas_tools, band=none, sessions=33)
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `In C:\Users\bruke\Pre Atlas\services\canvas-engine, the helper that converts a region name to a PascalCase component nam`
- **webos-333** (pre_atlas_apps, band=none, sessions=32)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `I need to understand how atlas_boot.html works as a shell that embeds other pages via iframes, and identify all the plac`
  - `Thoroughness: very thorough  Explore the ENTIRE Pre Atlas repository rooted at C:\Users\bruke\Pre Atlas. This is a feder`
- **weapon** (custom_skill, band=stale, sessions=18) [first-msg-only]
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `<scheduled-task name="lsh-png-wire-drift-check-2026-05-15" file="C:\Users\bruke\.claude\scheduled-tasks\lsh-png-wire-dri`
  - `i need you to help me plan. I want o use es tool to plan a fest /project-finisher /mini-ship /weapon`
- **competitor-monitor** (custom_skill, band=stale, sessions=16)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `<scheduled-task name="pester-2-linkedin-positioning" file="C:\Users\bruke\.claude\scheduled-tasks\pester-2-linkedin-posi`
- **fest** (custom_skill, band=stale, sessions=15) [first-msg-only]
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `# Resume — Claude/ChatGPT Mining Project (Post-Fest)  You're picking up an in-flight project. Prior session **closed the`
  - `# Part B — corpus-wide intent-vs-artifact reconciliation  **Status:** queued for next session. Part A shipped 2026-05-27`
- **autopilot** (custom_skill, band=stale, sessions=14) [first-msg-only]
  - `Design an integration plan for combining chord-pad and loop-engine into a new package called "loop-pad" in C:\Users\bruk`
  - `Context The autopilot works correctly with 8-chord progressions but has timing issues on shorter ones (2, 3, 4, 5, 6, 7 `
  - `In C:\Users\bruke\STRUDEL\chord-pad, thoroughly explore the UI layer and main orchestration. I need complete details on:`
- **codex-delegate** (custom_skill, band=stale, sessions=14)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `what happens in we combine binre tool with es tool what can we do`
  - `This repo feels likea big ball of mud`
- **lionestenzol** (github_repo, band=stale, sessions=11) [first-msg-only]
  - `<scheduled-task name="pester-2-linkedin-positioning" file="C:\Users\bruke\.claude\scheduled-tasks\pester-2-linkedin-posi`
  - `<scheduled-task name="pester-1-cold-email" file="C:\Users\bruke\.claude\scheduled-tasks\pester-1-cold-email\SKILL.md"> T`
  - `<scheduled-task name="pester-3-accountability-check" file="C:\Users\bruke\.claude\scheduled-tasks\pester-3-accountabilit`
- **servers** (github_repo, band=stale, sessions=8) [first-msg-only]
  - `\Got it. Here's the complete handoff for Claude Code — the SOP, the repo setup, and the build plan in one document. Drop`
  - `I need to understand the current shell layout system for the Loop Pad application to plan adding draggable column divide`
  - `Search the Pre Atlas repository at C:\Users\bruke\Pre Atlas\ for all dev server configurations. Look for:  1. package.js`
- **wasp** (github_repo, band=stale, sessions=8) [first-msg-only]
  - `Explore the current Pre Atlas worktree at `C:\Users\bruke\Pre Atlas\.claude\worktrees\stoic-noether-96bea8` and report b`
  - `**TASK:** Read every file under `C:\Users\bruke\.claude\agents\` (10 files) and `C:\Users\bruke\.claude\rules\` (17 file`
  - `I'm doing a machine-discoverable inventory for Step 2a. Your job is **SCRIPTS at user-root and standard locations** — si`
- **st3gg** (custom_skill, band=stale, sessions=8)
  - `@"C:\Users\bruke\OneDrive\Desktop\data-8ed83bb3-4a28-4595-840a-a9d0b3dd0d19-1779538231-29ad55e9-batch-0000.zip" @"C:\Use`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `Install ST3GG from https://github.com/elder-plinius/ST3GG into ~/tools/ST3GG.  Steps: 1. cd ~/tools && git clone https:/`
- **handoff-out** (custom_skill, band=stale, sessions=7)
  - `I wangt you to pretend i m someone looking at this repo fir the first time with no context what do we have`
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `\Got it. Here's the complete handoff for Claude Code — the SOP, the repo setup, and the build plan in one document. Drop`
- **project-finisher** (custom_skill, band=stale, sessions=7)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `i need you to install gemini cli npm install -g @google/gemini cli`
  - `i need you to help me plan. I want o use es tool to plan a fest /project-finisher /mini-ship /weapon`
- **tdd-workflow** (custom_skill, band=stale, sessions=6)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `**TASK:** Read every file under `C:\Users\bruke\.claude\agents\` (10 files) and `C:\Users\bruke\.claude\rules\` (17 file`
  - `**TASK:** Read every slash command file under `C:\Users\bruke\.claude\commands\` end-to-end. Goal: **streamlining** — Br`
- **wasp-patterns** (custom_skill, band=stale, sessions=6)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `You are doing PURE DATA EXTRACTION. No recommendations, no proposals, no value judgments. Just read files and produce fa`
  - `**TASK:** Read every file under `C:\Users\bruke\.claude\agents\` (10 files) and `C:\Users\bruke\.claude\rules\` (17 file`
- **search-first** (custom_skill, band=stale, sessions=5)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `i need you to use es tool to serarch and context and memory i need to find my debugging tool`
  - `**TASK:** Read every file under `C:\Users\bruke\.claude\agents\` (10 files) and `C:\Users\bruke\.claude\rules\` (17 file`
- **cookbook** (custom_skill, band=stale, sessions=4) [first-msg-only]
  - `I need to verify that Strudel code examples from a cookbook document actually parse and evaluate correctly.   Look at th`
  - `Explore the Strudel codebase at C:\Users\bruke\STRUDEL to understand what valid Strudel code looks like and how existing`
  - `Explore the `scripts/` directory and the AI reference docs at the repo root. I need to understand:  1. What's in `script`
- **eval-harness** (custom_skill, band=stale, sessions=4)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `**TASK:** Read every slash command file under `C:\Users\bruke\.claude\commands\` end-to-end. Goal: **streamlining** — Br`
  - `You are doing PURE DATA EXTRACTION. No recommendations, no proposals, no value judgments. Just read files and produce fa`
- **verification-loop** (custom_skill, band=stale, sessions=4)
  - `what are all the customizations that ive added to my cc bc my shit keeps getting better and better for example i have /j`
  - `**TASK:** Read every slash command file under `C:\Users\bruke\.claude\commands\` end-to-end. Goal: **streamlining** — Br`
  - `You are doing PURE DATA EXTRACTION. No recommendations, no proposals, no value judgments. Just read files and produce fa`
- _...and 13 more_

### Bucket 3 - shipped but NOT discussed in Claude Code
Shipped, but no Claude Code session matched. Could be:
- Shipped purely via shell / `gh` / `git` outside Claude Code
- Shipped via `/weapon` runs (still in jsonl, should match if name is in prompt)
- Ambiguous-name FP filter hid the discussion (try grep)
- Cloned/vendored repos with no original discussion

### Items (7)

- **airwindows** (standalone_repo, band=strong, sessions=0) [first-msg-only]
- **fleet-launch** (standalone_repo, band=partial, sessions=0)
- **mb3d_anim_demo** (standalone_repo, band=strong, sessions=0)
- **my-vite-app** (standalone_repo, band=partial, sessions=0)
- **surge-xt** (standalone_repo, band=strong, sessions=0)
- **outpost** (github_repo, band=partial, sessions=0) [first-msg-only]
- **MB-Lab** (github_repo, band=partial, sessions=0)

### Bucket 4 - neither
Low signal: no Claude Code discussion AND no strong ship evidence.

### Items (16)

- **cpython** (standalone_repo, band=stale, sessions=0) [first-msg-only]
- **musescore-mcp** (standalone_repo, band=none, sessions=0)
- **weather** (standalone_repo, band=stale, sessions=0) [first-msg-only]
- **saas-boilerplate** (github_repo, band=none, sessions=0)
- **CreatorOS** (github_repo, band=stale, sessions=0)
- **web-os-555** (github_repo, band=stale, sessions=0)
- **FragOS** (github_repo, band=stale, sessions=0)
- **nextjs-ai-chatbot** (github_repo, band=stale, sessions=0)
- **python-sdk** (github_repo, band=stale, sessions=0)
- **DAPO** (github_repo, band=stale, sessions=0)
- **m-357249** (github_repo, band=stale, sessions=0)
- **joyful-analytics-symphony** (github_repo, band=stale, sessions=0)
- **cpython** (github_repo, band=stale, sessions=0) [first-msg-only]
- **meshmap.net** (github_repo, band=stale, sessions=0) [first-msg-only]
- **js-dos** (github_repo, band=stale, sessions=0)
- _...and 1 more_

### Skipped (generic name)

### Items (5)

- **atlas** (standalone_repo, band=strong, sessions=0)
- **mcp** (standalone_repo, band=none, sessions=0)
- **r3f** (standalone_repo, band=none, sessions=0)
- **atlas** (github_repo, band=strong, sessions=0)
- **mpc** (github_repo, band=partial, sessions=0)

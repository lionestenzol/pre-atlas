---
title: Session Handoff — Compile-side seed repos (clone + perceive)
date: 2026-06-27
branch: feat/atlas-setup-ui
project: Pre Atlas
source_of_truth: .claude/projects/C--Users-bruke-Pre-Atlas/memory/project_compile_seed_repos.md
status: 2 of 5 active repos done · 3 remain · 1 parked
---

# Handoff — finish cloning + perceiving the seed repos

## One-line state
The 6-repo `/groundwork` seed (planned 2026-06-26) that completes the
**perceive -> reverse-compile -> COMPILE** stack is half-integrated. **turso** and
**codebase-memory-mcp** are cloned + run through the seam. **headroom**,
**open-code-review**, **superpowers** remain. **flue** is parked on purpose.

## The stack this completes
`PERCEIVE` (code-recon / repo-inventory / delta-scp / repomix / deepwiki)
-> `REVERSE-ENG` (binre) -> `COMPILE` (sigil pack / gw) -> `CARRY/NARRATE` (repomix / deepwiki / st3gg),
all joined by the sha256 content-address bus. These seed repos fill the COMPILE corner
and harden the perceive gates. See `[[project_tool_lattice_architecture]]` +
`[[project_stack_integration_seam]]`.

## Done (verified on disk, 2026-06-27)
| repo | role | on disk | seam result |
|---|---|---|---|
| `tursodatabase/turso` | the spine (libSQL/Turso Rust fork) | `C:\Users\bruke\turso` (77M, HEAD `84c1e7639`) | 3 ok / 0 err · inv `e2e3803f…`, gw `1a35c791…`, code-recon MISSING=ok |
| `DeusData/codebase-memory-mcp` | codebase memory layer | `C:\Users\bruke\codebase-memory-mcp` (**1.4G**, HEAD `b075f05`) | 2 ok / 1 err · gw `2f2f1aa7…`; **repo-inventory TIMED OUT @20s gateway cap** (owed: standalone run) |

## Remaining (precise, cold-start-able)
Order: headroom (after a redirect check), then open-code-review, then superpowers.

1. **headroom — VERIFY REDIRECT FIRST.** `chopratejas/headroom` now 301s to
   `headroomlabs-ai/headroom` (moved org). Confirm it's the same CCR reversible-compression
   project before wiring into the sigil/codec lane (name-collision risk):
   ```bash
   gh api repos/chopratejas/headroom --jq '.full_name, .description'
   ```
   Then (if confirmed): `git clone --filter=blob:none https://github.com/headroomlabs-ai/headroom.git C:/Users/bruke/headroom`
   then `seam perceive C:/Users/bruke/headroom --writes`.
   Role: CCR reversible-compression = the sigil/codec lane ("sigil related"). ★52k Python — **likely large, watch disk.**

2. **open-code-review** (code-recon hard-gate / perceive):
   ```bash
   git clone --filter=blob:none https://github.com/alibaba/open-code-review.git C:/Users/bruke/open-code-review
   seam perceive C:/Users/bruke/open-code-review --writes
   ```

3. **superpowers** (skills hard-gate): `obra/superpowers` is already present as a CC plugin-cache
   copy. CONFIRM that copy suffices before double-cloning — don't re-clone if the cache is enough.

4. **flue** (`withastro/flue`) stays parked unless explicitly un-parked.

5. **Owed:** standalone `repo-inventory` on codebase-memory-mcp (it timed out at the 20s gateway cap on 1.4G):
   ```bash
   seam call repo-inventory inventory root=C:/Users/bruke/codebase-memory-mcp
   ```
   (Run direct, not through `perceive`, so it isn't racing the other two caps; or raise the timeout.)

## Hard caveats (do not skip)
- **Disk:** these are LARGE (codebase-memory-mcp was 1.4G; headroom ★52k may match). Check free space before each clone; one-at-a-time, not a batch.
- **seam gotchas:** forward-slash paths only; writes gated behind `--writes`; **20s timeout per gateway call**; `code-recon` MISSING verdict = ok (no map yet, regen on first real recon).
- **es/Git-Bash:** `/ad`, `dc:>=`, `dm:>=`, `parent:` all misbehave here (MSYS path-mangle / redirect-eating). Use `dm:yesterday`/`dm:today` and PowerShell `Get-ChildItem` for folder lists.
- Best driver for the remaining 3 = a fresh `/groundwork "clone+integrate the 3 remaining seed repos, headroom-first after redirect-verify"` (proof-gated plan) with full context — not a tail-end grind.

## Files this work touches
- Memory (source of truth): `project_compile_seed_repos.md` (+ pointer in `MEMORY.md`).
- New clones live OUTSIDE the Pre Atlas repo (`C:\Users\bruke\<repo>`), so they don't dirty git here.

Related: `[[project_tool_lattice_architecture]]` · `[[project_stack_integration_seam]]` · `[[project_binre]]` · `[[project_libsql_spine_decision]]` · `[[project_external_code_tools_vs_stack]]` · `[[reference_windows_cp1252_encoding_gotcha]]`.

# Agent Belt — Claude Code Skill Inventory

> **What this is:** the operator's Claude Code **skill belt** — ~40 user-global
> skills (plus a few slash-command families) that drive work across projects,
> including this `pre-atlas` repo. This is distinct from the running system
> (see `CONTEXT_FOR_WEB.md`) and from the 13-tool search stack (see
> `docs/repo-search-stack.md`); `repo-search` is one skill *in* this belt.
>
> **⚠ Accuracy note:** the descriptions below are **inferred from skill names +
> cluster grouping**, not yet from each skill's authoritative `description:`
> frontmatter. Treat them as a map, not gospel. To replace them with exact
> text, run the command at the bottom and paste the result. Last built
> 2026-06-09 from a categorized `Get-ChildItem` read of `~/.claude/skills`.

---

## How to read this belt

Two structural facts matter more than any single skill:

1. **There are router/dispatcher skills** that choose *other* skills. Know the
   router and you pick the right tool instead of guessing — e.g.
   `web-extract-workflow` routes the web-extraction cluster, and `search-first`
   sets the discipline that `repo-search` executes.
2. **There are `*-migrate` pairs** — a base skill for greenfield use and a
   `-migrate` variant for converting existing code onto that library.

---

## 1. 3D / fractal
| Skill | Inferred purpose |
|---|---|
| `three-js` | Build 3D scenes with Three.js |
| `three-js-migrate` | Migrate existing code onto Three.js (pairs with `three-js`) |
| `react-three-fiber` | Three.js via the React-Three-Fiber renderer |
| `mandelbulb3d` | Drive Mandelbulb3D fractal rendering |
| `mandelbulber2` | Drive Mandelbulber2 fractal rendering |

## 2. Animation / video
| Skill | Inferred purpose |
|---|---|
| `anime-js` | Build animations with Anime.js |
| `anime-js-migrate` | Migrate existing animation code onto Anime.js |
| `remotion` | Programmatic video generation with Remotion (React) |

## 3. Web extraction  *(overlap cluster — has a router)*
| Skill | Inferred purpose |
|---|---|
| **`web-extract-workflow`** | **Router** — routes a scrape/extract task to the right tool below |
| `web-audit` | Capture/audit a site → anatomy (ties to `tools/anatomy-extension` + optogon sitepull) |
| `scrapling-official` | Scrape via the Scrapling library |
| `competitor-monitor` | Track/diff competitor sites over time |

## 4. Project-driving
| Skill | Inferred purpose |
|---|---|
| `weapon` | (Inferred) heavy execution/automation driver — confirm |
| `project-finisher` | Push a project to "done" / close out loops |
| `mini-ship` | Ship a small increment end-to-end |
| `autopilot` | Autonomous multi-step execution loop |
| `fest` | Festival/batch planning workflow (cf. `doctrine/fest_staging`, `build_fest.sh`) |

## 5. Code quality / search  *(repo-search lives here)*
| Skill | Inferred purpose |
|---|---|
| `repo-search` | Drives the 13-tool search stack (`docs/repo-search-stack.md`) |
| `search-first` | Discipline: search before reading/editing (the `search-protocol.md` law) |
| `security-review` | Security-focused review pass |
| `tdd-workflow` | Test-driven development loop |
| `verification-loop` | Prove a change works before declaring done |
| `code-review` | General correctness/quality review pass |

## 6. Meta / learning
| Skill | Inferred purpose |
|---|---|
| `continuous-learning-v2` | Capture lessons/patterns across sessions |
| `eval-harness` | Run evals against outputs/skills |
| `strategic-compact` | Compress context/strategy into a compact brief |
| `instinct-*` (command family) | Slash-command family for meta/learning reflexes |

## 7. Patterns  *(ECC origin)*
| Skill | Inferred purpose |
|---|---|
| `backend-patterns` | Reusable backend implementation patterns |
| `frontend-patterns` | Reusable frontend implementation patterns |
| `coding-standards` | House coding standards/conventions |
| `wasp-patterns` | Patterns for the **Wasp** framework (note the `.wasp` excludes in `search-protocol.md`) |

## 8. Niche tools
| Skill | Inferred purpose |
|---|---|
| `st3gg` | (Inferred) niche generator/tool — confirm |
| `td` / `td-ux` / `td-experiment` | A "td" family (UX + experiment variants) — confirm domain |
| `codex-delegate` | Delegate work to Codex (cf. `tools/codex-partner`) |
| `handoff-out` | Produce a handoff/exit summary for another agent or session |

---

## Known relationships (the high-value part)

- **`web-extract-workflow` → {`web-audit`, `scrapling-official`, `competitor-monitor`}** — start at the router, not a leaf.
- **`search-first` (discipline) → `repo-search` (execution) → the 13-tool stack** — see `docs/search-protocol.md`.
- **Quality gate cluster:** `code-review` + `security-review` + `tdd-workflow` + `verification-loop` typically run together before "done."
- **`*-migrate` pairs:** `three-js`/`three-js-migrate`, `anime-js`/`anime-js-migrate` — pick base vs migration variant by whether code already exists.
- **`wasp-patterns`** implies at least one project is a **Wasp** app — consistent with `.wasp` dir exclusions throughout the search protocol.

---

## Make this authoritative

Replace the inferred descriptions above with each skill's real `description:`
frontmatter. Run in PowerShell on the machine that has the skills:

```powershell
$rows = foreach ($d in Get-ChildItem "$env:USERPROFILE\.claude\skills" -Directory) {
  $md = Join-Path $d.FullName "SKILL.md"; if (!(Test-Path $md)) { continue }
  $t = Get-Content $md -Raw
  $desc = if ($t -match '(?ms)^description:\s*(.+?)(\r?\n\w+:|\r?\n---)') { ($matches[1] -replace '\s+',' ').Trim() } else { '' }
  [pscustomobject]@{ Skill = $d.Name; Description = $desc } }
$rows | Sort-Object Skill | Format-Table -AutoSize -Wrap | Out-String -Width 160 | Tee-Object belt-table.txt
```

Paste `belt-table.txt` back and this file gets rewritten with exact text and an
accurate count. Also list slash-commands (the `instinct-*` family etc.) with:

```powershell
Get-ChildItem "$env:USERPROFILE\.claude\commands\*.md" | ForEach-Object {
  "/{0,-22} {1}" -f $_.BaseName, ((Get-Content $_.FullName -TotalCount 1) -replace '^#\s*','') }
```

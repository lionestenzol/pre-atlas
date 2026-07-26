# mini-ship · DEFERRED

Persistent list of known fixes that mini-ship rounds discovered but didn't address (out of scope, blocked, or required user decision). Append-only. Scanner reads this; entries surface as Fleet candidates.

Format: each entry is a `## D<N> · <title>` heading + body. Mark as `RESOLVED in <commit-sha>` when fixed; never delete entries (history value).

**Note (2026-05-02):** This file is intentionally **untracked** (no `git add`). Lives in main repo path, shared across worktrees, survives branch rollbacks. Scanner reads via absolute path.

---

## D1 · Untrack .claude/settings.local.json — **RESOLVED**

**Source:** Fleet 02 / S2 (BLOCKED Option B chosen 2026-05-02)
**Type:** privacy / git hygiene
**Est:** 5 min  ·  **Actual:** ~2h (one false start)
**Resolved:** 2026-05-02 in commit `782a308` on `claude/elegant-black-71ab26` (this worktree)

Final fix was minimal: added `.claude/settings.local.json` to `.gitignore` on this worktree's branch. The file was already removed from this branch's HEAD by the filter-repo attempt (see D5), so no `git rm --cached` was needed — just gitignore the path going forward.

**Privacy posture:** the file is still in GitHub's history at older commits (172-entry permissions allowlist + Stop hook config). Per user decision, the historical exposure is acceptable — content is config preferences, not credentials. Forward-only fix instead of history rewrite.

---

## D2 · /mini-ship slash command writes log to wrong path when invoked from worktree — **RESOLVED**

**Source:** Surfaced in V0.2 build review (mini-ship S1.5)
**Type:** correctness bug
**Est:** 10 min  ·  **Actual:** 5 min
**Resolved:** 2026-05-02 by Fleet 02 / S3 (originally `2fa787e`, now `aa0cf69` post-rollback) on `claude/elegant-black-71ab26`

The slash command used relative `tools/mini-ship/log.jsonl` (4 refs at L15/64/146/173). Fixed by replacing all 4 with absolute path `C:/Users/bruke/Pre Atlas/tools/mini-ship/log.jsonl`. Now matches scan.py convention.

---

## D3 · /weapon commits to main repo's branch when target is the main repo — **RESOLVED**

**Source:** Fleet 02 / S2 deviation (2026-05-02), reinforced by S4 (same day)
**Type:** convention / clarity
**Est:** 10 min  ·  **Actual:** 10 min
**Resolved:** 2026-05-02 by Fleet 02 / S5 — codified in `feedback_weapon_branch_routing.md` memory entry (outside git, survives rollbacks)

Resolution: codified as feedback memory rather than picking A/B/C. The actual rule is simpler than the original framing — **commit on the branch of the working tree that holds the file, not on whatever branch the spec assumed.** Includes the bash gotcha that masked S4's wrong-SHA bug (`set -e` not halting through `git add` → `git commit` → `$()` substitution chain). Future weapon missions reference the memory entry directly.

---

## D4 · Refresh / promote V0.2 mini-ship after 3 successful rounds — **RESOLVED**

**Source:** mini-ship's own kill criteria
**Type:** earn-its-place gate
**Trigger:** after Fleet ≥02 ship #3 lands cleanly
**Resolved:** 2026-05-02 by Fleet 02 / S4 — codified in `project_mini_ship.md` memory entry (outside git, survives rollbacks)

Final score at promotion: 4 clean ships (S1 atlas hallway, S1.5 mini-ship build itself, S2 .gitignore housekeep, S3 absolute-log-path fix). Kill criterion exceeded 2×. Memory + index flipped from BETA → ACTIVE.

Global promotion (move slash command to `~/.claude/commands/`, hook to `~/.claude/settings.json`, namespace log by repo path) deferred — Pre-Atlas-only scope is fine until Bruke wants /mini-ship in another repo.

---

## D5 · git filter-repo rewrite of settings.local.json — ROLLED BACK (don't repeat)

**Source:** Fleet 02 / between S5 and S6 (2026-05-02)
**Type:** anti-pattern documented for future-me
**Status:** ATTEMPTED, ROLLED BACK, DON'T REPEAT

Tried to scrub `.claude/settings.local.json` from the entire git history via `git filter-repo --invert-paths --path .claude/settings.local.json --force`. Operation succeeded technically (148 commits rewritten in 63 sec, 0 commits still touching the file) but had unacceptable collateral:

- Every SHA changed locally; would require force-push to align GitHub
- All references to old SHAs (mini-ship log entries, DEFERRED.md, atlas/registry.json, any open PRs) would break
- Cost ~2h to update all references for a non-credentials privacy gap

User stopped the force-push. Local was rolled back via `git reset --hard origin/<branch>` for branches with origin counterparts (claude/main-triage-26f4a5, main). GitHub never saw the rewrite.

**Lesson:** filter-repo is for actual secrets/credentials/PII. For "I don't want this tracked anymore" gaps, the simple fix is `git rm --cached` + gitignore + forward-only — accept the historical exposure if it's not actually sensitive.

**Recovery artifacts:**
- `.git/filter-repo/commit-map` — old SHA → new SHA mapping (for reference if needed)
- `/tmp/settings-local-json-backup-1777754067` — pre-rollback backup of the file (39060 bytes, can delete now that file is restored)

**Side effects of the rollback that needed cleanup:**
- DEFERRED.md was gone (this file you're reading is the restored version)
- scan.py was gone from main repo path (still in this worktree at `tools/mini-ship/scan.py`)
- log.jsonl entries S1.5/S2/S3/S4/S5 reference now-dead SHAs (kept as historical record; the actual file changes those commits made are still on disk)

---

## D6 · scan.py needs viability gate for untracked Python

**Source:** Fleet 02 / S7 (2026-05-02) — surfaced when /mini-ship picked the cortex-optogon wire as a top candidate
**Type:** scanner correctness / picker quality
**Est:** 30-60 min  ·  **Status:** OPEN (not blocking)

scan.py picks untracked Python files as ship candidates based on git-status alone. It can't tell that an untracked file references symbols that don't exist anywhere (e.g. `ActionType.OPTOGON_SESSION` in `test_optogon_wire.py` referenced an enum value that wasn't defined in `contracts.py`). User caught this in S7 by saying "wait look at the code" + "use es tool" — without that intervention the SHIP CARD would have led to `pytest fails on import` immediately.

**Fix sketch:**
- For each untracked `.py` candidate, run `python -m py_compile <file>` (free, no deps)
- Optionally also run `pyflakes <file>` if available — catches undefined-name errors
- If either fails: downgrade tier from A → C with reason "imports/symbols broken — needs completion"
- The candidate still surfaces (don't hide it) but won't be top-ranked

**Why it matters:**
- Mini-ship's contract is "smallest shippable atom" — emphasis on SHIPPABLE
- Untracked-but-broken code is the WORST kind of false positive (looks like a 5-min commit, is actually a 30-min completion ship)
- The S7 picker mistake → user manual eyes pattern is exactly what mini-ship is supposed to eliminate

**Don't add unless:**
- Picker quality regresses ≥2 of next 3 rounds (per kill criterion logic)
- Pure dogfood signal: if user has to manually verify pickability ≥2 sessions running, this becomes priority

For now: noted, not committed. Trust user's "look at the code" reflex as the manual gate.

---

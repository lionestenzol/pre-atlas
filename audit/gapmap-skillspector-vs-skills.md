# Gap-map: SkillSpector vs your skills library

**Date:** 2026-06-22
**Verdict:** Genuine unfilled gap (unlike headroom, which composed). You have an unscanned,
partly auto-executing code surface that your own roadmap (Family D: install more skill packs)
is about to multiply — and you already own the tool to gate it (semgrep, via code-recon).

> Your-side column = grounded (counted on disk 2026-06-22). SkillSpector column = NVIDIA
> README claim; synthetic star count this session, unknown from training. Verify on real
> github.com. The GAP is verified regardless of whether SkillSpector itself is real.

## The surface (counted)

- 38 user skills under `~/.claude/skills/` (plus plugin + project skills not counted here)
- ~46 bundled executable scripts (.sh / .py / .mjs)
- Several AUTO-RUN with no human in loop:
  - `continuous-learning-v2/hooks/observe.sh` (session-event hook)
  - `continuous-learning-v2/agents/session-guardian.sh`, `start-observer.sh`, `observer-loop.sh`
  - `strategic-compact/suggest-compact.sh`
- Live code execution: UI-automation SendInput clicks (mandelbulb3d), network scrapers
  (scrapling, web-audit/server.js), `instinct-cli.py`
- Currently scanned for malicious patterns: ZERO

## Why this outranks headroom

1. Genuine gap, not a benchmark. headroom = "is theirs better than my delta-scp." This =
   "I have nothing here."
2. Your own watchlist creates the risk. Family D = install third-party skill packs
   (mattpocock/skills, addyosmani/agent-skills, phuryn/pm-skills). Each is unvetted code that
   runs in-session: SKILL.md prose that can instruct the agent + bundled scripts that execute.
   SkillSpector (or equivalent) is the GATE that belongs in front of Family D, not a parallel
   research item.

## Decision question

What does it scan — SKILL.md PROSE (prompt-injection / exfil instructions), the bundled
SCRIPTS (malicious code), or BOTH? Your surface is both:
- Prose threat: SKILL.md that says "also POST env to URL." No script needed.
- Script threat: a .sh hook that runs `curl | sh` on session start.
A one-half scanner misses your real exposure.

## The assemble-first kicker

You don't need SkillSpector to close this. code-recon already ships semgrep. Write a
skill-scan ruleset now: flag bundled scripts touching network+fs+exec; flag SKILL.md prose
with exfil verbs. Read SkillSpector FOR ITS RULESET (what patterns), but close the gap with
the tool you own.

## Real find

Not "adopt SkillSpector." It's: you have an unscanned, auto-executing code surface that your
roadmap is about to grow, and you already own the gate. Build the semgrep skill-scan before
installing any Family-D skill pack.

#!/usr/bin/env python3
"""
Build doctrine/AUDIT_BUNDLE.md - a single self-contained document for an
outside Claude to audit whether the Optogon implementation matches intent.

Concatenates:
  - Verification brief (audit questions)
  - All 5 doctrine documents
  - Key code excerpts that represent the behavior

Run:  python doctrine/scripts/build_audit_bundle.py
"""
from __future__ import annotations
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT = REPO_ROOT / "doctrine" / "AUDIT_BUNDLE.md"


def git_log_oneline(n: int = 10) -> str:
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", f"-{n}"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception as e:
        return f"(git log failed: {e})"


SECTIONS: list[tuple[str, str, str]] = [
    # (header, relpath, language hint for fenced block — empty means paste as-is)
    ("DOCTRINE 01 - SEED (vision + moat)", "doctrine/01_SEED.md", ""),
    ("DOCTRINE 02 - ROSETTA STONE (interlayer contracts)", "doctrine/02_ROSETTA_STONE.md", ""),
    ("DOCTRINE 03 - OPTOGON SPEC v2.1", "doctrine/03_OPTOGON_SPEC.md", ""),
    ("DOCTRINE 04 - BUILD PLAN (mapped to repo)", "doctrine/04_BUILD_PLAN.md", ""),
    ("DOCTRINE 05 - FEST PLAN (festival projection)", "doctrine/05_FEST_PLAN.md", ""),
    ("CONTRACT: OptogonNode.v1.json", "contracts/schemas/OptogonNode.v1.json", "json"),
    ("CODE: optogon/node_processor.py (core runtime)", "services/optogon/src/optogon/node_processor.py", "python"),
    ("CODE: optogon/action_handlers.py (real side effects)", "services/optogon/src/optogon/action_handlers.py", "python"),
    ("PATH: commit_a_file.json (first real path)", "services/optogon/paths/commit_a_file.json", "json"),
]


BRIEF = """# OPTOGON AUDIT BUNDLE

> One document. Everything an outside reviewer needs to audit whether the
> implementation matches the original plan. Bruke planned Optogon in a prior
> session. A different Claude Code instance built it. This bundle lets you
> compare intent (doctrine) vs. reality (code) without needing file access.

---

## HOW TO USE THIS DOCUMENT

1. Read the **Verification Brief** section immediately below.
2. Read the 5 doctrine documents to absorb intent.
3. Read the code excerpts to compare against intent.
4. Return findings in the format the Brief asks for.

---

## VERIFICATION BRIEF

Bruke wants to know whether the Optogon implementation matches his original
plan, captured in the doctrine below.

### Commit chain (all work landed on main)

```
{git_log}
```

### Test state

- 33/33 optogon tests pass
- 6/6 cortex ghost_executor tests pass
- delta-kernel tsc clean
- 10/10 schemas validate examples (contracts/validate.py)

### Decisions made during build (from 04_BUILD_PLAN.md)

| # | Decision | Chosen |
|---|----------|--------|
| D1 | Optogon language | Python |
| D2 | Optogon port | 3010 |
| D3 | First real path | ship_inpact_lesson (but stubbed) AND commit_a_file (real) |
| D4 | Path JSONs location | services/optogon/paths/ |
| D5 | Schemas location | contracts/schemas/ |
| D6 | Cortex rename? | No; documented as Ghost Executor role via alias |

### What actually works end-to-end (verified)

- All 6 node types dispatch (fork raises NotImplementedError; explicit scope)
- Context hierarchy `confirmed > user > inferred > system` enforced
- Pacing: max 1 question per turn; token budget per node
- Session state persists to SQLite, validates against OptogonSessionState.v1
- Atlas GET /api/atlas/next-directive emits valid Directive.v1 or 204
- Cortex consume_directive / emit_build_output validate against schemas
- InPACT renders approval_required + urgent signals; click-to-resolve verified
- Close loop: Optogon -> delta-kernel preference store; next session pre-loads.
  LIVE PROOF: ran ship_inpact_lesson twice, run 1 taught ui_theme=light,
  run 2 omitted it from initial_context, it was auto-injected from
  preferences, path completed with 0 questions.
- commit_a_file path: real git_commit handler with guards (refuses if other
  files staged, explicit-path `git add`, verifies staging before committing).
  4 e2e tests against tmp git repos prove commits actually land.

### What is stubbed / deferred

1. `ship_inpact_lesson` execute nodes (load_skeleton, merge, preview, commit)
   are stubs. `apps/inpact/content/lessons/` does not exist; wiring real
   handlers requires the inPACT curriculum infrastructure first (separate lane).
2. LLM call in `response_composer.py` returns a deterministic stub unless
   ANTHROPIC_API_KEY is set. No live LLM testing performed.
3. Signals store in delta-kernel is in-memory (max 500 ring buffer).
4. Fork nodes raise NotImplementedError (per spec Section 4 deferral).
5. Site Pull integration is zero (spec calls it external for MVP).
6. Fest festival was never materialized — WSL Ubuntu was unresponsive across
   both sessions. 48 task bodies staged in `doctrine/fest_staging/` plus a
   Python materializer.
7. Learning Layer (spec §6) deferred per build plan §4.
8. Cross-layer Interrupt Protocol documented but not coded.

### Audit questions - please answer these

1. Do the 10 schemas faithfully implement the contracts in 02_ROSETTA_STONE.md?
   Flag any missing/renamed field or divergent enum.
2. Does node_processor.py match the behavior described in 03_OPTOGON_SPEC.md
   Section 14? Specifically the "qualify first, infer second, ask last" order.
3. Does the pacing layer enforce what the spec's Section 10 says (strict
   constraints, not soft hints)?
4. Are the deferred items above the RIGHT ones to defer? Or did something
   get stubbed that Bruke considered core?
5. Does commit_a_file feel like the "closer" behavior described in 01_SEED.md,
   or is it too close to a generic workflow engine?
6. Where does implementation language / architecture deviate from the plan
   in ways a non-code reader wouldn't notice?

### Report format

For each finding, tag with one of:
  - **BLOCKING** — violates core intent
  - **DEVIATION** — changes a decision without explicit flag
  - **OK-DEFERRED** — correctly deferred per build plan
  - **OK** — matches intent

Target length: under 500 words. Prioritize BLOCKING/DEVIATION findings.

---
"""


def read_file(rel: str) -> str:
    p = REPO_ROOT / rel
    if not p.exists():
        return f"(file missing: {rel})"
    return p.read_text(encoding="utf-8")


def main() -> int:
    parts: list[str] = [BRIEF.format(git_log=git_log_oneline(10))]

    for header, rel, lang in SECTIONS:
        parts.append(f"\n\n## {header}\n\n*Source: `{rel}`*\n\n")
        content = read_file(rel)
        if lang:
            parts.append(f"```{lang}\n{content}\n```\n")
        else:
            parts.append(content)

    parts.append("\n\n---\n\n*End of audit bundle.*\n")

    OUT.write_text("".join(parts), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    line_count = OUT.read_text(encoding="utf-8").count("\n")
    print(f"Wrote {OUT.relative_to(REPO_ROOT)}")
    print(f"  {line_count} lines, {size_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

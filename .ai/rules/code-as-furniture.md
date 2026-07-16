# Code = Furniture

## The rule

**Every piece of code we keep is furniture in the house.**

- We don't leave broken furniture in the house.
- We don't throw furniture out either.
- If something is broken, we fix it.

Documenting a bug is **not** fixing it. Adding a "known issue" caveat to a card or README without a code fix is **not** acceptable. The fix lands inline, in the same session that discovered the bug, or it gets explicit deferral with a date and owner — never an indefinite "documented and left rotting."

## When the rule fires

- An audit or review surfaces a real bug in code under our control
- A dependency or vendored file has a dead-code path that's a time bomb (e.g. legacy API references)
- A build emits warnings that point to actual problems (not just lint noise)
- A demo or sample we keep around shows a known footgun in production behavior

## Decision tree

```
Found a bug.

  +-- Is the code ours / vendored / in-repo?
  |      +-- YES: fix it now, inline. Update the docs to reflect the fix.
  |      +-- NO:  file upstream + add a local workaround/patch that fixes the symptom for us.
  |                Never just "document and skip."
  |
  +-- Is the cost-to-fix > value-of-keeping?
         +-- YES: still don't throw out. File deferral with date+owner+criteria for return.
         +-- NO:  fix it now.
```

## What "fix" looks like

- Bad code path: replace with a clear error/throw OR rewrite the path correctly
- Duplicate dep: use package manager overrides to dedupe
- Unsafe runtime assumption: guard + fail-loud message
- Missing CSS/HTML setup: patch the boilerplate
- Outdated API call: replace with the modern equivalent

## What "fix" doesn't look like

- "Documented in Caveats." — that's a label, not a repair
- "It's in a dead path so it works." — until someone hits the dead path
- "Upstream's problem." — not if it ships in our bundle, it isn't
- "We'll come back to it." — without a date and a trigger, no you won't

## Origin

2026-05-10, after Path 2 weapon mission left 3 bugs "documented" in cards without fixes. Pushback was: "from now on all code we have needs to be treated like furniture in house. We don't leave things broken." Plus follow-up: "no throwing out" — the rule is fix, not discard.

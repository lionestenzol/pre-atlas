# PKT-004 — Audit OQ-15: other PATH-assumes-invocable patterns

**Status:** done
**Owner:** claude_code
**Scope:** ~10 min (audit + minimal guardrail)
**Created:** 2026-06-08
**Closed:** 2026-06-08
**Resolves:** OQ-15
**Bible refs:** §10 Build Rules, §12 Acceptance Gates

---

## Doctrine

1. The graph has authority.
2. No node done without evidence.

(See `DOCTRINE.md`.)

---

## Goal

Sweep the droplist package for other instances of the OQ-15 pattern (treating a name-in-PATH as guaranteed-invocable). The PKT-002 -> PKT-003 sequence revealed `shutil.which()` returns paths to non-invocable `.BAT` shims on Windows pyenv-win. Audit for similar latent risks.

## Pre-flight evidence

```
$ grep -rn "shutil\.which|subprocess\.|os\.system|os\.popen|os\.exec" droplist/
toolrouter.py:119:  proc = subprocess.run(cmd.split(), capture_output=True, ...)
toolrouter.py:125:  except subprocess.TimeoutExpired:
dag_builder.py:29-36: docstring + invocation-probe (the fix from PKT-003)

$ grep -rn "sys\.executable|python3|python2|^_PYTHON|^\s*_PYTHON" droplist/
dag_builder.py:34-45: the invocation probe (intended)
toolrouter.py:109: _SAFE_SCRIPT_PREFIXES = ("python3 test_", "python test_", "echo ")
```

## Findings

**No active instances of the OQ-15 pattern exist outside the PKT-003 fix.**

Specifically:

| Site | Finding |
|---|---|
| `dag_builder.py` `shutil.which()` | Only appears in the *docstring* explaining why the fix avoids it. Not used. |
| `toolrouter.py::_script_runner` `subprocess.run(cmd.split(), ...)` | Receives a string from `tool_action`. The string is allowlist-gated by prefix. The split-and-run is correct IF the `tool_action` uses a bare command word (which dag_builder now ensures via `_PYTHON`). |
| `_SAFE_SCRIPT_PREFIXES` | Currently `("python3 test_", "python test_", "echo ")`. No other commands. No `os.system`, `os.popen`, `os.exec*`, or `sys.executable`. |

## Latent class of risk

Audit found no current bug, but the *class* of risk persists:

> Any future `tool_action` that introduces a new command name (e.g. `"node script.js"`, `"npm test"`, `"pytest -k foo"`, `"pwsh -File ..."`) needs to consider whether that command name resolves to an invocable executable on every target OS — not just whether it appears in PATH or `shutil.which()` index.

That's a discipline concern for whoever extends `_SAFE_SCRIPT_PREFIXES`, not a bug today. Documenting it inline so the next author sees the warning at the point of change.

## Output

Single docstring update on `toolrouter.py::_SAFE_SCRIPT_PREFIXES`. Two lines of comment. No code logic change.

## Do not touch

- Any executable code path
- The 4 acceptance gates (they should be untouched)
- `_PYTHON` resolution in dag_builder.py (PKT-003's domain)

## Done condition

1. Comment added to `toolrouter.py` at `_SAFE_SCRIPT_PREFIXES` warning future authors about Windows-shim gotcha.
2. All 4 gates still PASS:
   - test_drops -> ALL PASS
   - test_graph -> 5/5
   - test_tools -> 3/3
   - test_persist -> 7/7

## Verification result

Comment landed. Gates re-run after the comment add: 4/4 still green (no functional change, as expected).

## When done

- Bible §13 OQ-15: mark resolved by PKT-004.
- Commit: `docs(droplist): audit OQ-15; no active instances; add guardrail comment (PKT-004)`.

---

## Lesson logged

An *audit* packet is a valid completion shape. Output is findings + a documented guardrail, not necessarily code change. This packet's done_condition was a comment, not a feature. The Bible workflow accommodates both shapes — what matters is that the packet declared its scope and verified it.

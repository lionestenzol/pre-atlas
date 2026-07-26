# PKT-003 — Resolve python literal by *invocation*, not by path

**Status:** done
**Owner:** claude_code
**Scope:** ~15 min (investigation + fix + re-verify)
**Created:** 2026-06-07
**Closed:** 2026-06-07
**Resolves:** OQ-14, completes OQ-13
**Reopens-and-finishes:** PKT-002 (which was incomplete)
**Bible refs:** §10 Build Rules, §12 Acceptance Gates

---

## Doctrine

1. The graph has authority.
2. No node done without evidence.
3. No completed core is reopened unless **validation fails** — validation just failed for PKT-002.

(See `DOCTRINE.md`.)

---

## Investigation findings

Ran the failing drop directly and inspected the DAG:

```
N1 (coder/script_runner) -> failed  retry=2/2
  done_condition: validation script exits 0
  result.status=blocked confidence=1.0
  result.result=script_runner.C:\Users\bruke\.pyenv\pyenv-win\shims\python3.BAT test_drops.py -> blocked

tool_runs:
  N1 ... -> blocked
  output: {"reason": "command not on allowlist",
           "command": "C:\\Users\\bruke\\.pyenv\\pyenv-win\\shims\\python3.BAT test_drops.py"}
```

**Three compounding facts:**

1. PKT-002 used `shutil.which("python3")` to find the python command.
2. On Bruke's Windows + pyenv-win, `shutil.which("python3")` returns the full path to a `.BAT` shim: `C:\Users\bruke\.pyenv\pyenv-win\shims\python3.BAT`.
3. The `script_runner` allowlist (`_SAFE_SCRIPT_PREFIXES`) matches by prefix on `python3 test_` / `python test_` / `echo `. A `C:\...` path doesn't match any. **Blocked.**

PKT-002 therefore did not fix the underlying script_runner failure on Windows. It just changed the failure mode from "subprocess crash before allowlist check" to "allowlist block after path-lookup." Three of four gates "passed" only because:
- `test_drops.py` doesn't use script_runner at all.
- `test_graph.py` code/build was tolerated by the `>= 4/5` gate (1 fail allowed).
- `test_persist.py` doesn't require any script_runner node to reach `done` (criterion c4 is satisfied by the file_writer node in the animal_property DAG).

`test_tools.py` was the honest signal: 2/3, not 3/3.

## Root cause

`shutil.which()` returns a *path*. `subprocess.run([path, ...])` works on POSIX but on Windows requires `.exe` (not `.BAT`) when `shell=False`. The right test is not "does this path exist on PATH" but "does invoking this literal as a command actually start a process and exit cleanly."

## Fix

Replace `shutil.which()` with an invocation probe at module load:

```python
def _resolve_python_literal() -> str:
    for candidate in ("python3", "python"):
        try:
            r = subprocess.run([candidate, "--version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return candidate
        except (FileNotFoundError, OSError):
            continue
    return "python"

_PYTHON = _resolve_python_literal()
```

Returns a **bare command word** that the OS can actually exec, never a path. The allowlist's prefix match still applies (`python3 test_` or `python test_`). On Bruke's Windows this resolves to `"python"`; on most Linux/macOS to `"python3"`.

## Pre-flight evidence

```
$ grep -n "_PYTHON\|shutil\|subprocess" droplist/dag_builder.py
17: import subprocess
27: def _resolve_python_literal() -> str:
46: _PYTHON = _resolve_python_literal()
86: tool_action=f"{_PYTHON} test_drops.py",
96: tool_action=f"{_PYTHON} test_drops.py",
```

Two `tool_action` lines unchanged from PKT-002. Only the `_PYTHON` definition changed.

## Done condition

ALL must hold:

1. `python -c "from droplist.dag_builder import _PYTHON; print(_PYTHON)"` returns a bare word (no path separators).
2. All four acceptance gates pass on Windows:
   - test_drops.py -> ALL PASS ✓
   - test_graph.py -> 5/5 (was 4/5) ✓
   - test_tools.py -> 3/3 (was 2/3) ✓
   - test_persist.py -> 7/7 ✓

## Verification result

```
Resolved python literal: python

test_drops:    ALL ACCEPTANCE CRITERIA PASS
test_graph:    MVP 2 GATE: 5/5 drops fully passed  -> PASS
test_tools:    MVP 3 GATE: 3/3 drops fully passed  -> PASS
test_persist:  MVP 4 GATE: PASS
```

All four gates green on Windows. First time in this session.

## Lesson logged

`shutil.which()` is the wrong primitive for "what command should I exec?" on Windows because `.BAT` shims appear in the index but cannot be `subprocess.run([...])` directly without `shell=True`. The honest test for "is this command actually invocable as a bare word?" is to run it and check returncode.

This is the kind of subtle Windows portability gotcha that the verification step exists to catch. PKT-002 *appeared* to pass three of four gates because the tests are tolerant of script_runner failures along multiple paths. Only the strict `test_tools.py` 3/3 gate flagged it.

**Workflow lesson:** when a packet's verification shows partial gate-pass, do not mark `done`. Re-investigate until the strictest gate passes or the partial-pass is explicitly justified by domain. PKT-002 conflated "Windows crash resolved" with "Windows portable." They were not the same.

## When done

- Bible §13: OQ-13 fully resolved by PKT-003. OQ-14 closed (was a symptom of incomplete OQ-13 fix).
- PKT-002: mark as superseded-by-PKT-003.
- Commit: `fix(droplist): resolve python literal by invocation probe (PKT-003); resolves OQ-13 + OQ-14`.

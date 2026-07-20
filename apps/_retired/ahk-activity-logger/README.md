# AHK Activity Logger

Extracted from conversation #1039 "Coding GPT Framework Plan" (2024-11-27), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/1039_coding-gpt-framework-plan/`), verdict MINE, decided 2026-04-21.

## What this is

The source thread's AutoHotkey blocks were 8 disconnected fragments (key logging, mouse logging, active-window logging, a few "if window X is active, auto-type Y" triggers) sharing no common structure. `activity_logger.ahk` consolidates them into one script: all logging writes to a single `actions_log.txt`, and the two auto-fill triggers use named config variables (`CodeEditorTitle`, `LoginWindowTitle`) at the top instead of the literal window-title strings scattered through the original blocks.

Validated with AutoHotkey v1's syntax checker (no interpreter for AHK exists in this repo's Python/JS toolchain, so this is the closest available verification):
```
"C:\Program Files\AutoHotkey\v1.1.37.02\AutoHotkeyU64.exe" /Validate activity_logger.ahk
```
Exit code 0, no errors.

## What was changed from the source

The original login auto-fill block had hardcoded credential literals (`Send, my_username` / `Send, my_password`). Removed — hardcoding credentials (even obviously-fake placeholder ones) in a script that gets committed to a repo is exactly the mistake `~/.claude/rules/common/security.md` exists to prevent. The trigger is left in place with the send-sequence structure intact; fill in real values locally, never in the committed script.

## What was left out

The rest of the source thread (most of its 110 blocks) was JSON example records of a hypothetical "coding GPT" training-feedback loop (user interaction logs with success/failure metadata) and a trivial toy `login()` Python function repeated across several blocks — no coherent framework skeleton beyond the AHK fragments, contrary to what "framework skeleton" in the triage note implied. Nothing else here was salvageable as real code.

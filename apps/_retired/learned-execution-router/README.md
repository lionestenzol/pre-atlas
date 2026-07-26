# Learned Execution Router

Extracted from conversation #359 "Introduction to Binary Code" (2025-02-24), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/359_introduction-to-binary-code/`), verdict MINE, decided 2026-04-21.

## What this is

The triage note called this thread "JSON schema material for symbolic execution," but the 181 code blocks turned out to be console-output examples from a simulated "self-evolving PNG execution network" — nodes hold function keys, a shared routing table maps task name → current owning node, and nodes "learn" tasks by acquiring them from whoever owns them now (updating the table so future calls route directly). This module is a real implementation of that pattern: `register()` gives a node a real handler for a task, `execute()` routes a task call to its current owner, `learn()` lets a node acquire an existing task and become its new routing target. 6/6 tests passing.

## What was left out

The "PNG" framing itself — nodes were never actually PNG image files in the source examples, just string IDs like `"PNG_1"`. Kept the routing/learning logic, dropped the naming convention since it added nothing but confusion.

## Run the tests

```
python -m pytest test_router.py -v
```

# Quiz Grader

Extracted from conversation #363 "Quiz Template Creation" (2025-02-23), Pre Atlas harvest pipeline (`services/cognitive-sensor/harvest/363_quiz-template-creation/`), verdict MINE, decided 2026-04-21.

## What this is

The thread's opening request was literally "generate a template for a quiz," and its first two code blocks are a real JSON quiz schema supporting four question types (`multiple_choice`, `true_false`, `short_answer`, `numeric`) where `correct_answer` can be a string, a number, or a dict (e.g. an `{x, y}` coordinate for a graph-reading question). The source thread stopped at the schema — no code ever consumed it. `quiz_grader.py` adds `grade_quiz(quiz, answers)`, which scores submitted answers against that schema using the quiz's own `scoring` block, with case/whitespace-insensitive string matching and exact matching for structured (dict) answers. 5/5 tests passing.

## What was left out

The thread later drifted into an unrelated "AI-based video compression via motion vectors stored in PNG metadata" tangent (the conversation's actual last exchange) — no working code backed that idea, so nothing from it was ported.

## Run the tests

```
python -m pytest test_quiz_grader.py -v
```

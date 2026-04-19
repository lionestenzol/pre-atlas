# Task: Measure Questions Drop

## Objective
Verify Run 2 asks measurably fewer questions than Run 1.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Phase 4 success criterion
- Acceptance: Run 2 questions_asked < Run 1 questions_asked by at least 1
- If not met, identify which preference failed to apply and iterate

## Implementation Steps
1. Compare metrics from previous task
2. If pass, commit the metrics table to doctrine/05_FEST_PLAN.md as proof
3. If fail, write findings to a follow-up task and re-run Phase 4

## Definition of Done
- [ ] Documented Run 1 vs Run 2 comparison with verdict
- [ ] If pass: festival eligible for /999_REVIEW

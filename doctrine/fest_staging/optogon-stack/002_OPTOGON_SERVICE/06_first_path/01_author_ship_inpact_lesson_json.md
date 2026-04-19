# Task: Author Ship Inpact Lesson Json

## Objective
Author services/optogon/paths/ship_inpact_lesson.json — first real path.

## Requirements
- Source: doctrine/04_BUILD_PLAN.md Section 5 (table of nodes for this path)
- 9 nodes: entry, load_skeleton, validate_content, merge, preview, em_dash_check, approve, commit, done
- Must validate against OptogonPath.v1.json
- Must use ship_inpact_lesson real repo paths (apps/inpact/content/lessons/{N}.md)

## Implementation Steps
1. Author the JSON file using _template.json as base
2. Cross-check qualification_keys per build plan node table
3. Validate via contract_validator before commit

## Definition of Done
- [ ] Path file exists and validates against OptogonPath.v1.json
- [ ] GET /paths returns it

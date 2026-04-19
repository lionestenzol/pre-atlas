# Task: Author One Example Per Schema

## Objective
Author one valid example per schema in contracts/examples/.

## Requirements
- 10 example files matching the 10 schemas (3 Optogon + 7 Rosetta)
- Examples must be realistic — use ship_inpact_lesson as the running example where possible
- File naming: contracts/examples/<schema_basename>.example.json

## Implementation Steps
1. For each schema in contracts/schemas/, create matching example file
2. Cross-link: ContextPackage example references same routes that ship_inpact_lesson path uses
3. Directive example references the OptogonPath example by id

## Definition of Done
- [ ] 10 example files exist
- [ ] Each example is valid JSON

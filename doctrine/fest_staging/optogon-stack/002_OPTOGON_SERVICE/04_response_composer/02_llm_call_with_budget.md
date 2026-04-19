# Task: Llm Call With Budget

## Objective
Wire actual LLM call (Claude/local) with strict prompt budget.

## Requirements
- Use anthropic SDK (already in cortex deps)
- Prompt template: [system context, current node, qualification keys outstanding, pacing rules]
- Pass max_tokens=200 default; configurable per node

## Implementation Steps
1. Author llm_call() in response_composer.py
2. Use ANTHROPIC_API_KEY from env (same as cortex)
3. Enable prompt caching on system prompt segment

## Definition of Done
- [ ] Test (mocked): call returns within token budget
- [ ] Test (live, optional): actual API call returns valid response

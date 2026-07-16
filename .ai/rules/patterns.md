# Common Patterns

## Repository Pattern

Encapsulate data access behind a consistent interface:
- Define standard operations: findAll, findById, create, update, delete
- Concrete implementations handle storage details (database, API, file, etc.)
- Business logic depends on the abstract interface, not the storage mechanism
- Enables easy swapping of data sources and simplifies testing with mocks

## API Response Format

Use a consistent envelope for all API responses:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "total": 100,
    "page": 1,
    "limit": 20
  }
}
```

- Include a success/status indicator
- Include the data payload (nullable on error)
- Include an error message field (nullable on success)
- Include metadata for paginated responses (total, page, limit)

## Skeleton Projects

When implementing new functionality:
1. Search for battle-tested skeleton projects or templates
2. Evaluate options for security, extensibility, and relevance
3. Clone best match as foundation
4. Iterate within proven structure

## Ship Small, Iterate Fast

- Smallest real output first — prove the concept works before scaling
- Ship the loop, not the form — get the feedback cycle running before polishing
- Progressive disclosure over instant complexity — start simple, add features as needed
- Projects have shapes — respect the natural structure instead of forcing a template

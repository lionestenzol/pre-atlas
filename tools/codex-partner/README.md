# Codex Partner Templates

Reusable JSON schemas for typed Claude<->Codex handoffs. Drop the schema name into `codex exec --output-schema schemas/<name>.schema.json` and Codex's final response is constrained to match.

## Why

Without `--output-schema`, asking Codex for "a verdict and a score" returns prose. Claude has to regex-extract. Brittle.

With a schema, Codex returns exactly:

```json
{"verdict":"warn","score":72,"summary":"...","issues":[...]}
```

Direct `json.load()`. No prose-parsing. AI-to-AI handoff becomes deterministic.

## Available schemas

| Schema | Use case |
|---|---|
| `review.schema.json` | Code review verdict (approve/warn/block + scored issues) |
| `decision.schema.json` | Second-opinion recommendation with rationale + alternatives |
| `fact-extract.schema.json` | Pull discrete verified claims out of a codebase or doc |
| `diff-summary.schema.json` | Structured summary of uncommitted/PR changes |

## Usage

### From shell (read-only review of current dir)

```bash
codex exec -s read-only --skip-git-repo-check \
  -C "C:\Users\bruke\Pre Atlas" \
  --output-schema "C:\Users\bruke\Pre Atlas\tools\codex-partner\schemas\review.schema.json" \
  -o /tmp/review.json \
  --ephemeral \
  "Review the recent changes to services/delta-kernel/src/core/types.ts. Output JSON matching the schema."
```

Then parse:
```bash
python -c "import json; d=json.load(open('/tmp/review.json')); print(d['verdict'], d['score'])"
```

### From the new MCP integration (after Claude Code restart)

The `codex` MCP server is now registered user-scope. After restart, Claude can call:

```
mcp__codex__codex(
  prompt="Review this for security issues",
  cwd="C:/Users/bruke/Pre Atlas",
  sandbox="read-only",
  config={ "output_schema": "...path to schema..." }
)
```

Cleaner than shelling out.

## Gotchas (verified pen-test 2026-04-24)

1. **`-o <file>` writes at exec EXIT, not progressively.** Wait for codex to finish before reading.
2. **Don't combine `--full-auto` with `-s read-only`.** The preset wins; you'll get workspace-write writes when you wanted read-only.
3. **Don't redirect `--json` with `> file` in Git Bash on Windows.** Flakes. Use `tee` or pipe through Python.
4. **OneDrive paths still blocked by sandbox.** Copy into Pre Atlas first.
5. **Inside Codex's PowerShell shell, `/tmp` resolves to `C:\tmp`,** not Git-Bash's temp dir. Use Windows paths or stick to `-C`.

See `reference_codex_pentest.md` in user memory for full probe results.

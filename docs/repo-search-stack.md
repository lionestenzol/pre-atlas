# Repo-Search / Structural-Code-Search Stack

**Purpose:** LLM code execution with structural repo search. The agent should understand the codebase before editing.

This stack is installed locally on this machine and is meant for both interactive use and agent workflows. It gives you fast text search, file discovery, AST-shape search, static analysis, repo statistics, symbol indexing, and readable diffs/JSON/YAML.

**Operational rules for how to use these tools live in [docs/search-protocol.md](search-protocol.md) — the DropList Search Tightening Protocol.** This doc is the inventory; that doc is the playbook.

**Global machine layer:** above this stack sits **`es`** (voidtools Everything CLI), used to locate the right project/file *anywhere on the machine* before any repo-local search. Full cheatsheet at `~/.claude/rules/common/file-search.md`. The protocol document treats `es` as step 0 in the search ladder.

Verify the stack with:

```bash
bash tools/repo_search_check.sh
```

---

## Tools

| Tool | Purpose | Installed via |
|---|---|---|
| `rg` (ripgrep) | Fast recursive text search with regex, file-type filters, glob include/exclude | scoop |
| `fd` | Fast, user-friendly file finder (modern `find`) | scoop |
| `bat` | `cat` with syntax highlighting, line numbers, git diff gutters, paging | scoop |
| `eza` | Modern `ls`/`tree` replacement, git-aware, icons, tree view | scoop |
| `tree` | Directory tree (built-in `tree.com` on Windows; also `eza --tree`) | OS built-in |
| `delta` (git-delta) | Side-by-side / syntax-highlighted git diff viewer | scoop |
| `jq` | JSON query/transform language | scoop |
| `yq` | YAML/JSON/TOML query/transform (mikefarah) | scoop |
| `sg` (ast-grep) | AST structural search/rewrite — code shape, not regex | scoop |
| `semgrep` | Pattern-based static analysis, security rules, custom rule sets | pip --user |
| `tree-sitter` | Parser CLI — generate/test grammars, dump syntax trees | scoop |
| `tokei` | Repo statistics — LOC by language, files, comments | scoop |
| `ctags` (Universal Ctags) | Symbol/tag index (`tags` file) for goto-definition, language-aware | already installed |

---

## Example commands (for this repo)

These are real, runnable examples scoped to this `Pre Atlas` repo.

### `rg` — text search

```bash
# Find all references to a mode (case-insensitive, code only)
rg -i "MAINTENANCE" services/delta-kernel/src --type ts

# Find TODO/FIXME across the repo, skipping noise
rg -n "TODO|FIXME|HACK" -t ts -t py -t js --glob '!**/node_modules/**' --glob '!**/.wasp/**'

# Find files that contain BOTH 'mode' and 'context' (multi-pattern)
rg -l "mode" services/delta-kernel/src | xargs rg -l "context"

# Find function definitions named handleSession
rg -n "^\s*(export\s+)?(async\s+)?function\s+handleSession" -t ts
```

### `fd` — file discovery

```bash
# All TypeScript files in delta-kernel
fd -e ts . services/delta-kernel/src

# Find any package.json outside node_modules
fd -t f -E node_modules package.json

# Find files modified in the last 24h
fd --changed-within 1d -t f

# Hand off matches to another tool (xargs-style with -X)
fd -e py -X tokei
```

### `bat` — readable file viewing

```bash
# Show a file with syntax highlighting and line numbers
bat services/delta-kernel/src/core/types.ts

# Show only a range
bat -r 1:80 services/delta-kernel/src/api/server.ts

# Diff a file vs git HEAD
bat --diff services/delta-kernel/src/api/server.ts
```

### `eza` — listing + tree

```bash
# Tree view of one service, 2 levels deep, git status, dirs first
eza --tree --level=2 --git --group-directories-first services/cognitive-sensor

# Long listing, sorted by modified time, with git info
eza -l --sort=modified --git services/delta-kernel/src
```

### `delta` — git diff viewer

```bash
# Pipe any git diff into delta for side-by-side, syntax-highlighted view
git diff | delta
git log -p -- services/delta-kernel/src/api/server.ts | delta

# Configure git to use delta as the default pager (one-time setup):
git config --global core.pager delta
git config --global interactive.diffFilter "delta --color-only"
git config --global delta.navigate true
git config --global delta.side-by-side true
```

### `jq` — JSON

```bash
# Inspect a schema's title + required fields
jq '{title, required}' contracts/schemas/AnatomyV1.v1.json

# Count entries in a clustering result
jq '.clusters | length' tools/fest-reconcile/festival_out/clusters_final.json

# Filter project IDs from session index
jq '.sessions[] | select(.project=="Pre Atlas") | .id' cc-session-index.json
```

### `yq` — YAML / TOML / JSON

```bash
# Read a value from any YAML config (mikefarah yq, v4 syntax)
yq '.scripts.build' package.json

# Convert YAML to JSON
yq -o=json '.' some-config.yaml

# Edit in place
yq -i '.version = "1.2.3"' some-config.yaml
```

### `sg` (ast-grep) — structural code search

```bash
# Find every console.log call in TS
sg --pattern 'console.log($A)' --lang ts services/delta-kernel/src

# Find every async function returning a Promise<Response>
sg --pattern 'async function $NAME($$$): Promise<Response> { $$$ }' --lang ts

# Auto-fix: replace all 'var X = Y' with 'const X = Y' in JS
sg --pattern 'var $X = $Y' --rewrite 'const $X = $Y' --lang js --update-all apps/

# Find Python try blocks with bare except
sg --pattern 'try:
    $$$
except:
    $$$' --lang python services/cognitive-sensor
```

### `semgrep` — static analysis / rule packs

```bash
# Run the default security ruleset against the repo
semgrep --config=auto services/delta-kernel/src

# Run a specific community pack
semgrep --config=p/typescript services/delta-kernel/src
semgrep --config=p/python   services/cognitive-sensor

# Write your own rule (YAML) and run it
semgrep --config=path/to/rule.yaml .
```

### `tree-sitter` — parser CLI

```bash
# Show the parse tree of a TS file (requires a grammar installed for that language)
tree-sitter parse services/delta-kernel/src/core/types.ts

# Run a query against the tree
tree-sitter query queries/functions.scm services/delta-kernel/src/core/types.ts
```

### `tokei` — repo stats

```bash
# Whole-repo summary
tokei

# One service, sorted by lines
tokei --sort lines services/cognitive-sensor

# JSON output for downstream tooling
tokei --output json
```

### `ctags` — symbol index

```bash
# Build a tags index for one service (recursive, multi-language)
# Quote glob patterns for --exclude; unquoted excludes are silently ignored on Windows bash.
ctags -R --languages=TypeScript,JavaScript,Python \
  --exclude='node_modules' --exclude='.wasp' --exclude='dist' --exclude='build' \
  -f .tags services/

# Search the index for a symbol
# Note: grep -P (PCRE) errors with "supports only unibyte and UTF-8 locales" on this Windows bash.
# Use grep -E (POSIX ERE) instead.
grep -E '^handleSession\b' .tags
```

---

## Recommended agent workflow

When an agent has to understand and edit a codebase, run this loop:

1. **List tree** — `eza --tree --level=2 --git path/` (orient on the layout)
2. **Search files with `fd`** — narrow to files of interest by name, extension, age
3. **Search text with `rg`** — find usages, references, error messages, TODOs
4. **Search code shape with `sg`** — find structural patterns regex can't (call sites, signature shapes, AST patterns)
5. **Inspect with `bat`** — read targeted files/ranges with syntax highlighting
6. **Check symbols with `ctags`** — confirm a symbol's canonical definition vs incidental references
7. **Patch** — apply the edit (Edit tool / Write tool)
8. **Run tests** — language-appropriate (`npm test`, `pytest`, etc.)
9. **Show git diff** — `git diff | delta` for a human-readable review

`semgrep` and `tokei` are out-of-band: run `semgrep` when chasing a class of bug across the repo, run `tokei` when sizing a service or measuring drift.

---

## Install notes (for re-creation on another machine)

- Most tools came from **scoop** (no admin needed): `scoop install fd bat eza delta jq yq tokei tree-sitter`
- `rg` and `ast-grep` (`sg`) were already installed from earlier work
- `ctags` (Universal Ctags 6.1.0) was already installed
- `semgrep` came from **pip --user** (`python -m pip install --user semgrep`) because pipx's shared venv was broken on this machine — see Caveats below
- `tree` uses the Windows built-in (`C:\Windows\System32\tree.com`); `eza --tree` is the richer option

### Caveats

1. **semgrep install bumped opentelemetry packages** in the user site-packages (0.54b1 → 0.58b0). This could affect FastAPI/ASGI services in this repo if they import `opentelemetry-instrumentation-asgi` / `-fastapi` from the user site rather than a venv. If a service breaks with a related ImportError, pin the older opentelemetry versions in that service's venv.
2. **pipx is broken on this machine** — `pipx`'s `shared` venv lacks pip, so `pipx install` fails. Fix by reinstalling pipx (`pip install --user --force-reinstall pipx`) or by using `pip install --user` directly.
3. **PATH** — scoop shims land in `~/scoop/shims`; pip --user scripts land in `%APPDATA%\Python\Python313\Scripts`. Both are typically on the user PATH; if a tool "isn't found" from a fresh shell, restart the shell.

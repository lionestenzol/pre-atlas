# DropList Search Tightening Protocol

Operational rules for how an agent (Claude Code or otherwise) uses the search toolbelt in [docs/repo-search-stack.md](repo-search-stack.md). Search-first, edit-last. Every conclusion needs file evidence.

---

## Core law

```text
Search before reading.
Read before editing.
Use the cheapest search first.
Escalate only when needed.
Never trust one search result.
Every conclusion needs file evidence.
```

The search stack moves like this:

```text
ES (global index) → TREE → FD → RG → SG → SEMGREP → CTAGS/LSP → TEST SEARCH → DIFF
```

```text
es      finds the world         (which projects/files exist anywhere on the machine)
tree    finds repo shape        (what folders this project has)
fd      finds files in the repo (which files exist by name/extension)
rg      finds text              (where a word/identifier appears)
sg      finds code structure    (where a pattern shaped like X appears)
semgrep finds risky patterns    (security/standards rules)
ctags   finds definitions       (where a symbol is defined vs mentioned)
tests   find proof              (how the agent demonstrates correctness)
diff    finds truth             (what actually changed)
```

---

## 1. Global index search with `es` (machine layer)

Before the agent is even inside the right repo, locate the battlefield. On this Windows machine, `es.exe` (voidtools Everything CLI) queries the NTFS index in ~10ms across all drives.

`es` is best for:

```text
Where is that project folder?
Where is that file I forgot?
Where are all package.json files on this machine?
Where are old versions of this repo?
Where did Claude create that output last week?
Where are all .py / .ts / .md files across drives?
```

Examples:

```bash
es droplist
es package.json
es "*.py"
es "*.tsx"
es proof-log
es ".droplist"

# Filters (Everything DSL — terms AND by default)
es ext:ts size:>10kb dm:thisweek                # large recent TS files
es path:"C:\Users\bruke" tsconfig.json !node_modules -p   # repo configs
es droplist ext:md dm:lastmonth -p              # recent droplist docs
es .env !node_modules !.env.example -p          # stray secrets
```

**Critical flag:** when the query uses `!exclusion` or `path:folder`, add `-p` (match full path). Without it, those operators silently no-op.

Output formats: default = one path per line · `-json` = JSON array · `-csv` = CSV · `-get-result-count` = just the count. Sort: `-sort size`, `-sort date-modified`. Limit: `-n 20`.

Rule:

```text
Use es for global machine search.
Once inside the correct repo, switch to fd / rg / sg.
Do not use es as proof of file CONTENTS — it only knows the index.
Do not edit a file you only found via es until you have cd'd into a repo
and confirmed pwd + git status + actual file contents.
```

Reference: `~/.claude/rules/common/file-search.md` — full Everything DSL cheatsheet and pitfalls (index gaps, rebuild instructions).

---

## 2. Orientation search

Once inside the right repo, know what kind of repo it is.

Run:

```bash
pwd
git status --short
eza --tree --level=3 --git --group-directories-first   # (Windows: tree -L is not supported)
fd -t f -E node_modules -E .git
```

Purpose:

```text
Where am I?
What folders exist?
What languages are present?
What has already changed?
What files should I not touch?
```

Rule:

```text
If git status shows existing changes, assume they belong to the user unless proven otherwise.
Do not overwrite them.
```

---

## 3. File-name search with `fd`

Use `fd` when looking for **where something might live**.

```bash
fd "packet"
fd "drop"
fd "schema"
fd "validate"
fd "test"
fd "spec"
fd "config"
fd "route"
fd "api"
fd "store"
fd "save"
```

For extensions:

```bash
fd -e ts
fd -e tsx
fd -e js
fd -e py
fd -e json
fd -e yml
```

Rule:

```text
Use fd before opening random folders.
File names reveal architecture.
```

---

## 4. Text search with `rg`

Use `rg` when looking for **words, names, errors, functions, constants, routes, config keys, or logs**.

Basic:

```bash
rg -n "packet"
rg -n "validate"
rg -n "schema"
rg -n "save"
rg -n "write"
rg -n "error"
```

Grouped search:

```bash
rg -n "packet|drop|validate|schema|save|write"
rg -n "TODO|FIXME|HACK|BUG"
rg -n "throw new|raise|Exception|Error"
rg -n "test\(|it\(|describe\(|assert|expect"
```

Search with context:

```bash
rg -n -C 3 "validate"
rg -n -A 5 -B 5 "savePacket"
```

Search hidden/config files when needed:

```bash
rg -n --hidden "DATABASE_URL|API_KEY|TOKEN|SECRET"
```

Rule:

```text
Use rg to create a candidate file list.
Do not treat rg snippets as full understanding.
After rg finds candidates, read the actual files.
```

---

## 5. Structural search with `sg` / ast-grep

Use `sg` when text search is too loose and you need **code shape**.

Use it for:

```text
functions
async functions
class methods
if blocks
try/catch blocks
direct writes
console logs
schema parsing
API handlers
dangerous calls
```

Examples:

```bash
sg -p 'function $NAME($$$ARGS) { $$$BODY }'
sg -p 'const $NAME = async ($$$ARGS) => { $$$BODY }'
sg -p 'async function $NAME($$$ARGS) { $$$BODY }'
sg -p 'if ($COND) { $$$BODY }'
sg -p 'try { $$$BODY } catch ($ERR) { $$$CATCH }'
sg -p 'console.log($A)'
sg -p '$OBJ.$METHOD($$$ARGS)'
```

For JS/TS validation patterns:

```bash
sg -p '$SCHEMA.parse($INPUT)'
sg -p '$SCHEMA.safeParse($INPUT)'
sg -p 'z.object($$$BODY)'
```

For Python:

```bash
sg -p 'def $NAME($$$ARGS): $$$BODY'
sg -p 'async def $NAME($$$ARGS): $$$BODY'
sg -p 'try: $$$BODY except $ERR: $$$CATCH'
sg -p 'with open($PATH, $MODE) as $F: $$$BODY'
```

Rule:

```text
Use sg when the question is "where is this pattern shaped like this?"
Use rg when the question is "where is this word?"
```

---

## 6. Rule search with `semgrep`

Use `semgrep` when looking for **bad patterns, unsafe patterns, or project standards**.

Good for:

```text
eval
raw SQL interpolation
missing validation before save
direct deletes
broad exception swallowing
hardcoded secrets
unsafe subprocess
console logs in production paths
API routes without auth
```

Examples:

```bash
semgrep --config auto
semgrep -e 'eval(...)' --lang python .
semgrep -e 'console.log(...)' --lang javascript .
semgrep -e 'subprocess.run(...)' --lang python .
```

Rule:

```text
Use semgrep for repeatable safety/rule scans.
Use ast-grep for flexible structural discovery.
```

---

## 7. Config search with `jq` and `yq`

Use these to understand the project's commands and settings.

For JS/TS:

```bash
jq '.scripts'       package.json
jq '.dependencies'  package.json
jq '.devDependencies' package.json
```

For Python:

```bash
bat pyproject.toml
bat requirements.txt
bat setup.py
```

For YAML:

```bash
yq '.services' docker-compose.yml
yq '.jobs' .github/workflows/*.yml
```

Rule:

```text
Never guess the test/build command if package/config files exist.
Discover it.
```

---

## 8. Symbol search with `ctags`

Use `ctags` when the repo is large and you need **definitions/classes/functions**.

```bash
ctags -R --languages=TypeScript,JavaScript,Python \
  --exclude='node_modules' --exclude='.wasp' --exclude='dist' --exclude='build' \
  -f .tags .
```

Then search tags:

```bash
grep -E "^Packet\b"    .tags
grep -E "^validate\b"  .tags
grep -E "^save\b"      .tags
```

Rule:

```text
Use ctags when rg returns too many results or when you need definitions over mentions.
On this machine: quote --exclude globs; use grep -E not grep -P (locale issue).
```

---

## 9. Test search

Before patching, search for the testing style.

```bash
fd "test|spec|__tests__"
rg -n "describe\(|it\(|test\(|expect\(|assert|pytest|unittest"
jq '.scripts' package.json
```

Then run the smallest relevant test first.

```bash
npm test
npm run test
pytest
python -m pytest
go test ./...
cargo test
```

Rule:

```text
No patch is complete until the agent knows how proof is supposed to run.
```

---

## 10. Diff search

After editing, search what changed.

```bash
git status --short
git diff | delta
```

Optional:

```bash
git diff --stat
git diff --name-only
```

Rule:

```text
Diff is the truth.
If the diff shows unrelated changes, stop and tighten.
```

---

## Search escalation ladder

```text
0. es              Global machine index — find projects, files, outputs anywhere.
1. tree / eza      Understand repo shape.
2. fd              Find likely files.
3. rg              Find exact words and references.
4. rg -C 3         Understand local usage.
5. sg / ast-grep   Find structural code patterns.
6. semgrep         Find rule violations or dangerous patterns.
7. jq / yq         Read configs / discover scripts.
8. ctags / LSP     Find definitions and symbol relationships.
9. tests           Find proof path.
10. git diff       Verify changes.
```

Do not jump to high-power tools first unless the task demands it.

---

## Search decision table

| Need                                  | Tool                  |
| ------------------------------------- | --------------------- |
| Find anything on the machine          | `es` (Windows index)  |
| Find files in this repo               | `fd`                  |
| Find folders/layout                   | `eza --tree`, `fd .`  |
| Find words                            | `rg`                  |
| Find nearby usage                     | `rg -C 3`             |
| Find code shape                       | `sg`                  |
| Find unsafe patterns                  | `semgrep`             |
| Find JSON info                        | `jq`                  |
| Find YAML config                      | `yq`                  |
| Find definitions                      | `ctags`, LSP          |
| See file contents                     | `bat`, `sed -n`       |
| See changed work                      | `git status` + `git diff \| delta` |

---

## The actual paste-in protocol for Claude Code

Paste this into CC:

```text
You are operating under the DropList Search Tightening Protocol.

Core law:
- Search before reading.
- Read before editing.
- Use the cheapest search first.
- Escalate only when needed.
- Never trust one search result.
- Every conclusion needs file evidence.
- Do not edit until search has produced candidate files.
- Do not finish without diff/proof.

Search ladder:

0. GLOBAL INDEX (machine layer) — Windows / es
   If on Windows and the Everything CLI (`es`) is installed, use it as the
   global file-index layer BEFORE any repo-local search.
   Use es to find:
   - project folders anywhere on the machine
   - files across drives
   - old versions / .droplist logs
   - package.json / pyproject.toml / README files
   - outputs created by previous agents
   Rules:
   - Use es only for global machine search.
   - Once inside the correct repo, prefer fd/rg/sg.
   - Do not use es as proof of file contents; use rg/bat after locating files.
   - Do not edit files found by es until confirming the correct repo with
     pwd, git status, and reading actual file contents.

1. ORIENT (repo layer)
   Run:
   - pwd
   - git status --short
   - eza --tree --level=3 --git   (or `tree -L 3` if eza is unavailable)
   - fd -t f -E node_modules -E .git

2. FILE SEARCH
   Use fd to find likely files by name:
   - packet, drop, schema, validate, save, store, route, test, spec, config

3. TEXT SEARCH
   Use rg to find references:
   - rg -n "packet|drop|validate|schema|save|write"
   - rg -n "TODO|FIXME|HACK|BUG"
   - rg -n "throw new|raise|Exception|Error"
   - rg -n "test\(|it\(|describe\(|assert|expect"

4. CONTEXT SEARCH
   Use rg with context when needed:
   - rg -n -C 3 "SEARCH_TERM"
   - rg -n -A 5 -B 5 "SEARCH_TERM"

5. STRUCTURAL SEARCH
   Use ast-grep / sg when code shape matters:
   - sg -p 'function $NAME($$$ARGS) { $$$BODY }'
   - sg -p 'const $NAME = async ($$$ARGS) => { $$$BODY }'
   - sg -p '$SCHEMA.parse($INPUT)'
   - sg -p '$OBJ.$METHOD($$$ARGS)'
   - sg -p 'try { $$$BODY } catch ($ERR) { $$$CATCH }'

6. RULE SEARCH
   Use semgrep for safety or standard violations:
   - eval, raw SQL, direct deletes, hardcoded secrets, missing validation,
     broad catch blocks, unsafe subprocess, unauthenticated routes.

7. CONFIG SEARCH
   Use jq/yq/config files to discover scripts:
   - jq '.scripts' package.json
   - bat pyproject.toml
   - bat requirements.txt
   - yq '.services' docker-compose.yml
   - yq '.jobs' .github/workflows/*.yml

8. TEST SEARCH
   Before patching, find test style:
   - fd "test|spec|__tests__"
   - rg -n "describe\(|it\(|test\(|expect\(|assert|pytest|unittest"

9. READ
   Only after candidate files exist, read relevant files with:
   - bat
   - sed -n
   - cat if necessary

10. PATCH
    Patch narrowly.
    Do not rewrite architecture unless explicitly required.
    Preserve existing style.
    Do not overwrite user changes.

11. DIFF AND PROOF
    Always run:
    - git status --short
    - git diff | delta
    Then report:
    - files searched (es + fd + rg)
    - files read
    - files changed
    - commands run
    - test result
    - diff summary
    - remaining issues

Default tool priority:
es → fd → rg → rg -C → sg → semgrep → jq/yq → ctags/LSP → tests → git diff.

Purpose:
Tighten code search so the agent understands the repo before editing and
proves every change after. es gives the agent MACHINE vision; the rest give
it REPO vision. Don't conflate the two.
```

---

## Short command pattern

For every code task, the agent should naturally move like this:

```bash
# 0. Locate the right repo on the machine (Windows / es)
es droplist
es path:"C:\Users\bruke" "<repo-marker>" -p

# 1. Orient inside that repo
pwd
git status --short
eza --tree --level=3 --git
fd -t f -E node_modules -E .git

# 2-5. Search inside the repo
fd "target|related|test|spec"
rg -n "target|related|keywords"
rg -n -C 3 "best_match"
sg -p 'relevant code shape'

# 6. Read evidence
bat target/file

# 7. Discover commands
jq '.scripts' package.json
fd "test|spec"

# 8-10. Patch + test + diff
# (edits)
npm test     # or pytest, cargo test, etc.
git status --short
git diff | delta
```

That's the tightening protocol. `es` gives the agent **machine vision**; the rest of the stack gives it **repo vision**. Don't conflate the two.

---

## Windows / this-machine substitutions

Pre Atlas runs on Windows. When the protocol says one thing and the local toolchain needs another, use the right-hand column:

| Protocol command | Use on this machine | Why |
|---|---|---|
| `tree -L 3` | `eza --tree --level=3 --git --group-directories-first` | Windows built-in `tree.com` has no `-L` flag; eza is richer anyway |
| `fd .` | `fd -t f` (or `fd -t d` for dirs) | bare `fd .` lists everything; usually you want files or dirs |
| `cat X | jq` | `jq '.scripts' X` | jq accepts the file directly — saves the cat hop |
| `rg ...` from a script/subshell | `command rg ...` or the scoop binary | Claude Code wraps `rg` as a shell function; bypass with `command rg` |
| `grep -P` over tags | `grep -E` | `grep -P` errors on this Windows bash locale (`supports only unibyte and UTF-8`) |
| `ctags --exclude=node_modules` | `ctags --exclude='node_modules'` | unquoted excludes are silently ignored — produces a near-empty index |
| `semgrep ...` over untracked files | add `--no-git-ignore` | semgrep defaults to git-tracked files; new/untracked source is skipped |
| `es ... !path` or `es ... path:...` | add `-p` (match full path) | without `-p`, `!` exclusions and `path:` filters silently no-op |

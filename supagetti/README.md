# SupaGetti v0

A CLI that takes a codebase (folder, zip, or git repo), runs a deterministic
scan, has an LLM analyze it against what the user claims/wants, has a
Governor audit the findings for unsupported claims and privacy exposure,
then renders a plain-language + technical report — with every artifact
schema-validated end to end.

## Setup

```
pip install pydantic openai
export NVIDIA_API_KEY=nvapi-...   # required for `analyze` and `govern`
```

Uses NVIDIA's OpenAI-compatible endpoint (`https://integrate.api.nvidia.com/v1`),
default model `z-ai/glm-5.2`. Override with `SUPAGETTI_LLM_MODEL`.

## Usage

```
python supagetti.py new-case --name "project_name"
python supagetti.py load CASE_0001 --folder "./path"      # or --zip / --repo
python supagetti.py intake CASE_0001                      # interactive
python supagetti.py cast CASE_0001                         # scan -> analyze -> govern -> report -> ledger
```

Or run phases individually: `scan`, `analyze`, `govern`, `report`, `ledger`.
`CASE_ID` accepts either `CASE_0001` or the full folder name
`CASE_0001_project_name`.

## Output

```
/cases/CASE_0001_project_name/
  intake.json
  source/
  scan.json          # includes symbolic_compression: per-file symbols, token yield
  findings.json
  governor_report.json
  report.md
  ledger_entry.json
```

`scan.json`'s `symbolic_compression` block is a symbolic map of the codebase's
source files (functions/classes/etc. with line numbers, plus an estimated
token-yield from compressing the raw source into that map) — ported from
`services/delta-scp/src/compressor.ts` in the Pre Atlas monorepo. Zero LLM
calls; same INCLUDE_EXT allowlist and per-language regex patterns as the
original, so results are deterministic and reproducible across runs.

`governor_report.json`'s `verification` block is a "verify-or-it-didn't-
happen" re-derivation of each finding's checkable claims (manifest state,
file paths, symbol names) straight from `scan.json` — ported from the
code-recon skill's evidence-citation discipline (`core/verifier.py`, zero
LLM calls). It runs after the LLM audit and can only tighten the result: a
contradicted manifest claim or a fully-ungrounded finding forces
`status="blocked"`; a citation slip inside an otherwise well-grounded
finding downgrades to `needs_review` and is logged in `checklist`, never
silently passed through as `approved`.

`ledger_entry.json` carries three fields ported from bearings' zero-LLM
"where am I" digest (`~/.claude/scripts/bearings/bearings.py`) — same
discipline (a deterministic parse of what's already on disk, never a
re-derivation), applied to a case instead of a day's git/transcript
history:
- `findings_by_category` — a categorized tally (bearings: commits by
  conventional-commit type).
- `source_split` — an honest product/docs/data/other split of the scanned
  file count (bearings: the honest LOC split; the headline file count is a
  lie until split this way).
- `governance_tax` — whether the LLM-touched phases (`analyze`, `govern`)
  actually converted into a shipped report or got blocked before reaching
  the user, plus the verify-or-it-didn't-happen check tally (bearings:
  shipped-vs-oriented conversations and the orientation tax).

## Architecture

See the build spec for the full list of structural laws. In short:
- `core/case_manager.py` is the only place CASE_ID resolution happens.
- Each `core/*.py` phase module writes exactly one output file.
- Every phase checks its own prerequisites before doing anything.
- `core/llm.py` is the only module that calls the LLM API.
- All artifacts are `pydantic` models in `core/models.py`; malformed output
  cannot be written.
- Only the Governor (`core/governor.py`) can block `report` from running.

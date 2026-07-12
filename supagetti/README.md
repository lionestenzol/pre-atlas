# SupaGetti v0

A CLI that takes a codebase (folder, zip, or git repo), runs a deterministic
scan, has an LLM analyze it against what the user claims/wants, has a
Governor audit the findings for unsupported claims and privacy exposure,
then renders a plain-language + technical report — with every artifact
schema-validated end to end.

## Setup

```
pip install pydantic anthropic
export ANTHROPIC_API_KEY=sk-ant-...   # required for `analyze` and `govern`
```

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
  scan.json
  findings.json
  governor_report.json
  report.md
  ledger_entry.json
```

## Architecture

See the build spec for the full list of structural laws. In short:
- `core/case_manager.py` is the only place CASE_ID resolution happens.
- Each `core/*.py` phase module writes exactly one output file.
- Every phase checks its own prerequisites before doing anything.
- `core/llm.py` is the only module that calls the Anthropic API.
- All artifacts are `pydantic` models in `core/models.py`; malformed output
  cannot be written.
- Only the Governor (`core/governor.py`) can block `report` from running.

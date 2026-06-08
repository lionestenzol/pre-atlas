#!/usr/bin/env bash
# Atlas Audit — run the 5-layer pipeline (DropList Search Tightening Protocol)
# against Atlas-the-system. Idempotent, schedulable, diff-able.
#
# Emits to tools/atlas-audit/runs/:
#   findings-<UTC-date>.json   structured findings (1 line per finding)
#   report-<UTC-date>.md       human-readable summary
#   snapshot-<UTC-date>.json   raw snapshot for diff vs prior run
#
# Exit code = count of NEW findings vs the most recent prior run
# (0 = clean, N = N new things to look at). Suitable for cron / Task Scheduler.
#
# See docs/search-protocol.md and ~/.claude/skills/repo-search/SKILL.md.

set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$SCRIPT_DIR/runs"
mkdir -p "$OUT_DIR"

DATE="$(date -u +%Y-%m-%d)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FINDINGS="$OUT_DIR/findings-$DATE.json"
REPORT="$OUT_DIR/report-$DATE.md"
SNAPSHOT="$OUT_DIR/snapshot-$DATE.json"

cd "$REPO_ROOT"

# Toolbelt on PATH (Windows / scoop + pip --user). Harmless on other OSes.
export PATH="$HOME/scoop/shims:/c/Users/bruke/AppData/Roaming/Python/Python313/Scripts:$PATH"

# All 6 modes from the Mode FSM, per services/delta-kernel/src/core/types.ts
ALL_MODES="RECOVER CLOSURE MAINTENANCE BUILD COMPOUND SCALE"

# Reset the findings file (we append one JSON object per line — JSONL).
: > "$FINDINGS"

emit() {
  # emit <severity> <check_id> <subject> <message>
  jq -nc \
    --arg ts "$TS" \
    --arg severity "$1" \
    --arg check_id "$2" \
    --arg subject "$3" \
    --arg message "$4" \
    '{ts: $ts, severity: $severity, check_id: $check_id, subject: $subject, message: $message}' \
    >> "$FINDINGS"
}

# ──────────────────────────────────────────────────────────────────────────────
# Check 1 — Reserved Windows device-name files anywhere in services/, apps/, tools/
# These crash ripgrep and tools that mass-scan files.
# ──────────────────────────────────────────────────────────────────────────────
for name in NUL CON PRN AUX COM1 COM2 COM3 LPT1 LPT2; do
  while IFS= read -r f; do
    [ -n "$f" ] && emit BLOCKER reserved_name "$f" "Windows reserved device name '$name' — breaks rg/cross-cutting tooling"
  done < <(fd -t f --max-depth 6 \
    -E harvest -E markdown_output -E extractions -E data -E node_modules -E .git -E .wasp -E dist -E build \
    "^${name}\$" services/ apps/ tools/ 2>/dev/null | head -5)
done

# ──────────────────────────────────────────────────────────────────────────────
# Check 2 — Imports of services/delta-kernel/src/atlas/* whose source isn't tracked
# Catches "schrödinger's import" — build green locally, breaks on fresh checkout.
# ──────────────────────────────────────────────────────────────────────────────
imported_atlas_modules=$(
  rg --no-filename -o --multiline "from\s*['\"]\.\./atlas/([a-zA-Z0-9_-]+)" -t ts -r '$1' \
    services/delta-kernel/src 2>/dev/null | sort -u
)
for mod in $imported_atlas_modules; do
  src="services/delta-kernel/src/atlas/${mod}.ts"
  [ -f "$src" ] || continue
  if ! git ls-files --error-unmatch "$src" >/dev/null 2>&1; then
    emit BLOCKER untracked_imported "$src" "Imported by delta-kernel but not tracked by git — push will break fresh checkouts"
  fi
done

# ──────────────────────────────────────────────────────────────────────────────
# Check 3 — Mode FSM completeness. Every Record<Mode, ...> declaration in
# delta-kernel should cover all 6 modes. Partial coverage means runtime
# returns undefined when keyed by missing modes.
# ──────────────────────────────────────────────────────────────────────────────
while IFS=: read -r file line _; do
  [ -z "$file" ] && continue
  # Read 60 lines after the declaration; capture distinct mode literals seen.
  body=$(sed -n "${line},$((line + 60))p" "$file" 2>/dev/null)
  # Skip type annotations (interface fields, function signatures) — only check
  # Record<Mode, ...> instances that have a body to fill. Marker: '= {' on the
  # opening line.
  first_line=$(echo "$body" | head -1)
  echo "$first_line" | grep -q "=[[:space:]]*{" || continue
  modes_found=$(echo "$body" | grep -oE "\b(RECOVER|CLOSURE|MAINTENANCE|BUILD|COMPOUND|SCALE)\b" | sort -u | tr '\n' ',' | sed 's/,$//')
  count=$(echo "$modes_found" | tr ',' '\n' | grep -c .)
  decl=$(echo "$first_line" | sed -E 's/^[[:space:]]*//;s/[[:space:]]*=.*$//')
  if [ "$count" -lt 6 ]; then
    missing=""
    for m in $ALL_MODES; do
      echo "$modes_found" | grep -qw "$m" || missing="$missing,$m"
    done
    missing="${missing#,}"
    emit HIGH fsm_partial_record "${file}:${line}" "Record<Mode, ...> '${decl}' covers ${count}/6 modes — missing: $missing"
  fi
done < <(rg -n "Record<Mode," services/delta-kernel/src 2>/dev/null)

# ──────────────────────────────────────────────────────────────────────────────
# Check 4 — Atlas TS layer test coverage.
# 5 files, ~900 LOC in services/delta-kernel/src/atlas — flag if 0 tests.
# ──────────────────────────────────────────────────────────────────────────────
atlas_loc=$(tokei services/delta-kernel/src/atlas --output json 2>/dev/null | jq '.Total.code // 0')
atlas_tests=$(fd -t f "(test|spec)\.(t|j)s$" services/delta-kernel/src/atlas 2>/dev/null | wc -l)
if [ "$atlas_loc" -gt 100 ] && [ "$atlas_tests" -eq 0 ]; then
  emit HIGH no_atlas_tests "services/delta-kernel/src/atlas" "Atlas TS layer is ${atlas_loc} LOC with 0 test files — directive emitter is uncovered"
fi

# ──────────────────────────────────────────────────────────────────────────────
# Check 5 — State-file schema sanity. governance_state.json should have
# mode_since so cockpit can report mode duration honestly.
# ──────────────────────────────────────────────────────────────────────────────
gs="services/cognitive-sensor/governance_state.json"
if [ -f "$gs" ]; then
  has_ms=$(jq 'has("mode_since")' "$gs" 2>/dev/null)
  if [ "$has_ms" != "true" ]; then
    emit MED missing_mode_since "$gs" "governance_state.json lacks mode_since — cockpit.ts:472 TODO can't be resolved without this field"
  fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# Check 6 — Uncommitted long markdown docs in core service paths.
# Catches load-bearing doctrine sitting in working tree only (e.g., ATLAS_LAWS.md).
# ──────────────────────────────────────────────────────────────────────────────
# Use git directly — only walks the untracked set (gitignored files already
# pruned by --exclude-standard), and we explicitly skip mined / autogenerated
# trees that aren't authored doctrine.
git ls-files --others --exclude-standard -- \
  services/delta-kernel services/cognitive-sensor services/aegis-fabric 2>/dev/null \
  | grep '\.md$' \
  | grep -vE '/(harvest|markdown_output|extractions|data|node_modules)/' \
  | while IFS= read -r f; do
    [ -z "$f" ] && continue
    lines=$(wc -l < "$f" 2>/dev/null || echo 0)
    [ "$lines" -lt 100 ] && continue
    # ls-files --others already excludes the staging index entries on add-only;
    # we also confirm not staged (covers post-`git add` edge case).
    if ! git diff --cached --name-only -- "$f" 2>/dev/null | grep -q .; then
      emit HIGH untracked_doc "$f" "Untracked $lines-line markdown in core path — potential lost doctrine"
    fi
  done

# ──────────────────────────────────────────────────────────────────────────────
# Snapshot — full state we want to diff next time (deterministic, sorted)
# ──────────────────────────────────────────────────────────────────────────────
{
  echo "# Atlas snapshot $TS"
  echo
  echo "## Schema count"
  ls contracts/schemas/*.json 2>/dev/null | wc -l
  echo
  echo "## Atlas TS layer LOC"
  echo "$atlas_loc"
  echo
  echo "## Mode FSM Record<Mode> declarations"
  rg -n "Record<Mode," services/delta-kernel/src 2>/dev/null | sort
  echo
  echo "## Atlas/* imports observed"
  echo "$imported_atlas_modules"
} > "$SNAPSHOT"

# ──────────────────────────────────────────────────────────────────────────────
# Diff vs previous snapshot
# ──────────────────────────────────────────────────────────────────────────────
prior=$(ls "$OUT_DIR"/findings-*.json 2>/dev/null | grep -v "$FINDINGS" | sort | tail -1)
new_count=0
new_jsonl=""
if [ -n "$prior" ] && [ -f "$prior" ]; then
  new_jsonl=$(comm -23 <(sort "$FINDINGS") <(sort "$prior"))
  new_count=$(echo "$new_jsonl" | grep -c . || echo 0)
fi

# ──────────────────────────────────────────────────────────────────────────────
# Human-readable report
# ──────────────────────────────────────────────────────────────────────────────
total=$(wc -l < "$FINDINGS" | tr -d ' ')
by_sev() { c=$(grep -c "\"severity\":\"$1\"" "$FINDINGS" 2>/dev/null); echo "${c:-0}"; }

{
  echo "# Atlas Audit — $DATE"
  echo
  echo "Run: $TS"
  echo "Findings: $total ($(by_sev BLOCKER) BLOCKER, $(by_sev HIGH) HIGH, $(by_sev MED) MED)"
  if [ -n "$prior" ]; then
    echo "New since previous run ($(basename "$prior")): $new_count"
  else
    echo "First run (no prior to diff against)."
  fi
  echo
  echo "## Findings"
  echo
  for sev in BLOCKER HIGH MED LOW; do
    has=$(by_sev "$sev")
    [ "$has" -eq 0 ] && continue
    echo "### $sev"
    echo
    jq -r --arg sev "$sev" 'select(.severity==$sev) | "- **\(.check_id)** — `\(.subject)`\n  \(.message)"' "$FINDINGS"
    echo
  done
  if [ -z "$(cat "$FINDINGS")" ]; then
    echo "All checks green."
  fi
  echo
  echo "## Snapshot diff vs previous run"
  echo
  if [ -n "$prior" ]; then
    prior_snap=$(echo "$prior" | sed 's/findings-/snapshot-/')
    if [ -f "$prior_snap" ]; then
      echo '```diff'
      diff "$prior_snap" "$SNAPSHOT" 2>&1 || true
      echo '```'
    else
      echo "(no prior snapshot to diff)"
    fi
  else
    echo "(first run)"
  fi
  echo
  echo "## Files"
  echo
  echo "- findings: \`$(basename "$FINDINGS")\` (JSONL)"
  echo "- snapshot: \`$(basename "$SNAPSHOT")\`"
} > "$REPORT"

echo "wrote $REPORT"
echo "wrote $FINDINGS ($total findings)"
echo "wrote $SNAPSHOT"
[ -n "$prior" ] && echo "new vs prior: $new_count"

exit "$new_count"

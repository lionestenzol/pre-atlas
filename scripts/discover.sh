#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# discover.sh — point this at your tools, run once, paste the
# output file (discovery.txt) back to web Claude. It asks the
# questions Claude would otherwise make you answer: what each
# CLI exposes, and whether Lattice is the spine.
#
# READ-ONLY. Nothing here writes or mutates anything. It only
# runs --help / list / read queries and inspects file metadata.
#
# Run it on the MACHINE WHERE YOUR TOOLS LIVE (not in a cloud
# sandbox — those tools aren't there). No editing required: it
# auto-detects commands and auto-finds the Lattice DB. Override
# any guess with env vars, e.g.:
#
#   DROPLIST_CMD=dl LATTICE_DB=~/state/lattice.db ./discover.sh
#
# Flags:
#   --no-samples   skip dumping sample DB rows (use if rows hold
#                  private data you don't want to paste to an AI)
# ─────────────────────────────────────────────────────────────
set +e
set +u

# ===== Overridable config (env vars win; otherwise auto-detect) ======
DROPLIST_CMD="${DROPLIST_CMD:-}"     # your DropList CLI (auto-detected if empty)
ATLAS_CMD="${ATLAS_CMD:-}"           # your Atlas CLI
RAGDAG_CMD="${RAGDAG_CMD:-}"         # your RAG-DAG tool
LATTICE_DB="${LATTICE_DB:-}"         # path to the SQLite spine (auto-found if empty)
TOOLBELT_DIR="${TOOLBELT_DIR:-$HOME/tools}"   # dir holding the ~13 belt tools
DUMP_SAMPLES=1
[ "$1" = "--no-samples" ] && DUMP_SAMPLES=0
# =====================================================================

OUT="discovery.txt"
exec > >(tee "$OUT") 2>&1

# timeout wrapper so a hung CLI can't stall the whole run
TO=""
command -v timeout >/dev/null 2>&1 && TO="timeout 15"

sec(){ echo; echo "===== $1 ====="; }
sub(){ echo; echo "----- $1 -----"; }

# resolve <var-name> <candidate1> <candidate2> ...
# echoes the first resolvable command (respecting a preset value)
resolve(){
  local preset="$1"; shift
  if [ -n "$preset" ]; then echo "$preset"; return 0; fi
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 && { echo "$c"; return 0; }
  done
  return 1
}

# run a probe only if the command exists; cap noisy output
run(){
  local exe="$1"; shift
  if ! command -v "$exe" >/dev/null 2>&1 && [ ! -x "$exe" ]; then
    echo "\$ $exe $*   # (not found — skipped)"
    return 0
  fi
  echo "\$ $exe $*"
  $TO "$exe" "$@" 2>&1 | head -60
  echo
}

echo "================================================================"
echo " TOOL DISCOVERY"
echo " host:  $(hostname 2>/dev/null) ($(uname -s 2>/dev/null) $(uname -m 2>/dev/null))"
echo " user:  $(whoami 2>/dev/null)"
echo " when:  $(date)"
echo " note:  read-only probe; samples=$([ $DUMP_SAMPLES -eq 1 ] && echo on || echo off)"
echo "================================================================"

# ── DropList ────────────────────────────────────────────────────────
sec "DROPLIST CLI"
DROPLIST_CMD="$(resolve "$DROPLIST_CMD" droplist drop dl)"
if [ -n "$DROPLIST_CMD" ]; then
  echo "# resolved: $DROPLIST_CMD"
  run "$DROPLIST_CMD" --help
  run "$DROPLIST_CMD" help
  for v in list ls jobs today next status export dump; do run "$DROPLIST_CMD" "$v"; done
else
  echo "# DropList CLI not found (tried: droplist, drop, dl). Set DROPLIST_CMD=..."
fi
sub "where does it keep state?"
ls -la "$HOME/.droplist" "$HOME/.config/droplist" ./.droplist 2>/dev/null | head -20 || echo "(no known state dir)"

# ── Atlas ───────────────────────────────────────────────────────────
sec "ATLAS CLI"
ATLAS_CMD="$(resolve "$ATLAS_CMD" atlas atlas-ai)"
if [ -n "$ATLAS_CMD" ]; then
  echo "# resolved: $ATLAS_CMD"
  run "$ATLAS_CMD" --help
  for v in "triage" "triage list" "cards" "cards --pending" "list" "next" "routines" "tools" "export"; do
    # shellcheck disable=SC2086
    run "$ATLAS_CMD" $v
  done
  sub "can it write back? scan help for: done / advance / mark / update / close"
  $TO "$ATLAS_CMD" --help 2>&1 | grep -iE 'done|advance|mark|update|close|complete|commit' | head -20 \
    || echo "(no write-verbs surfaced in --help)"
else
  echo "# Atlas CLI not found (tried: atlas, atlas-ai). Set ATLAS_CMD=..."
fi

# ── RAG-DAG ─────────────────────────────────────────────────────────
sec "RAG-DAG TOOL"
RAGDAG_CMD="$(resolve "$RAGDAG_CMD" rag-dag ragdag rdag)"
if [ -n "$RAGDAG_CMD" ]; then
  echo "# resolved: $RAGDAG_CMD"
  run "$RAGDAG_CMD" --help
  for v in help list query stats; do run "$RAGDAG_CMD" "$v"; done
else
  echo "# RAG-DAG not found (tried: rag-dag, ragdag, rdag). Set RAGDAG_CMD=..."
fi

# ── Lattice (the spine) ─────────────────────────────────────────────
sec "LATTICE SCHEMA (likely the spine)"
if [ -z "$LATTICE_DB" ] || [ ! -f "$LATTICE_DB" ]; then
  sub "auto-locating a lattice*.db under \$HOME"
  GUESS="$(find "$HOME" -maxdepth 6 -iname '*lattic*.db' 2>/dev/null | head -1)"
  [ -n "$GUESS" ] && LATTICE_DB="$GUESS" && echo "found: $LATTICE_DB"
fi
if command -v sqlite3 >/dev/null 2>&1 && [ -f "$LATTICE_DB" ]; then
  echo "db: $LATTICE_DB"
  echo "size: $(du -h "$LATTICE_DB" 2>/dev/null | cut -f1)"
  sub "schema"
  sqlite3 "$LATTICE_DB" ".schema" 2>&1 | head -200
  sub "tables + row counts"
  for t in $(sqlite3 "$LATTICE_DB" ".tables" 2>/dev/null); do
    echo -n "$t: "; sqlite3 "$LATTICE_DB" "select count(*) from \"$t\";" 2>&1
  done
  if [ $DUMP_SAMPLES -eq 1 ]; then
    sub "sample rows (first 3 of common tables)"
    for t in items links events nodes edges; do
      sqlite3 "$LATTICE_DB" "select 1 from \"$t\" limit 1;" >/dev/null 2>&1 || continue
      echo "[$t]"; sqlite3 -header "$LATTICE_DB" "select * from \"$t\" limit 3;" 2>&1; echo
    done
  else
    echo "(sample rows skipped: --no-samples)"
  fi
else
  echo "Lattice DB not usable."
  command -v sqlite3 >/dev/null 2>&1 || echo "  - sqlite3 not installed"
  [ -f "$LATTICE_DB" ] || echo "  - no DB file (set LATTICE_DB=/path/to/lattice.db)"
  echo "  hint: find \$HOME -iname '*.db' 2>/dev/null | grep -i lattic"
fi

# ── Tool belt ───────────────────────────────────────────────────────
sec "TOOL BELT — CLIs"
echo "# shell tools + how they're invoked  (dir: $TOOLBELT_DIR)"
if [ -d "$TOOLBELT_DIR" ]; then
  ls -la "$TOOLBELT_DIR" 2>&1 | head -40
  sub "count"
  echo "$(find "$TOOLBELT_DIR" -maxdepth 1 \( -type f -o -type l \) 2>/dev/null | wc -l) entries"
else
  echo "(no tool-belt dir at $TOOLBELT_DIR — set TOOLBELT_DIR=...)"
fi

# ── Agent belt: Claude Code skills + slash-commands ─────────────────
# (the belt isn't only CLIs — much of it is Claude Code skills like
#  repo-search, and project/user slash-commands. Capture those too.)
sec "TOOL BELT — CLAUDE CODE SKILLS"
SKILL_DIRS="$HOME/.claude/skills ./.claude/skills"
found_skill=0
for base in $SKILL_DIRS; do
  [ -d "$base" ] || continue
  for d in "$base"/*/; do
    [ -f "$d/SKILL.md" ] || continue
    found_skill=1
    echo "## $(basename "$d")   ($d)"
    # front-matter / opening lines usually carry name + description
    sed -n '1,10p' "$d/SKILL.md" 2>/dev/null
    echo
  done
done
[ $found_skill -eq 0 ] && echo "(no SKILL.md found under: $SKILL_DIRS)"

sec "TOOL BELT — SLASH COMMANDS"
CMD_DIRS="$HOME/.claude/commands ./.claude/commands"
found_cmd=0
for base in $CMD_DIRS; do
  [ -d "$base" ] || continue
  for f in "$base"/*.md; do
    [ -f "$f" ] || continue
    found_cmd=1
    echo "## /$(basename "${f%.md}")   ($f)"
    sed -n '1,6p' "$f" 2>/dev/null
    echo
  done
done
[ $found_cmd -eq 0 ] && echo "(no command .md files under: $CMD_DIRS)"

sec "CC PROTOCOL FILE (CLAUDE.md)"
ls -la ./CLAUDE.md ./.claude/CLAUDE.md "$HOME/.claude/CLAUDE.md" 2>/dev/null | head -20 || echo "(none found)"

echo; echo "===== END — paste this whole file (discovery.txt) back ====="

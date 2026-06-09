#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# discover.sh — verify the repo-search belt and inventory the
# Claude Code agent setup, then paste discovery.txt back.
#
# This is the portable cousin of tools/repo_search_check.sh. It
# checks the 13-tool structural-search stack + `es` (the global
# Everything CLI, step 0), and lists your Claude Code skills and
# slash-commands so a fresh assistant knows the full belt.
#
# READ-ONLY. Runs only --version / --help / list. Mutates nothing.
# Run it on the MACHINE WHERE THE BELT LIVES (e.g. Git Bash on
# Windows), from anywhere.
#
# See: docs/repo-search-stack.md (inventory) and
#      docs/search-protocol.md (the DropList Search Tightening Protocol).
# ─────────────────────────────────────────────────────────────
set +e
set +u

OUT="discovery.txt"
exec > >(tee "$OUT") 2>&1

sec(){ echo; echo "===== $1 ====="; }
sub(){ echo; echo "----- $1 -----"; }

# check <display-name> <binary> [version-flag]
# prints presence + first version line; tallies PRESENT/MISSING
PRESENT=0; MISSING=0; MISSING_LIST=""
check(){
  local name="$1" bin="$2" flag="${3:---version}"
  if command -v "$bin" >/dev/null 2>&1; then
    local v; v="$(command "$bin" $flag 2>&1 | head -1)"
    printf "  ✓ %-14s %-22s %s\n" "$name" "($bin)" "$v"
    PRESENT=$((PRESENT+1))
  else
    printf "  ·  %-14s %-22s (not found)\n" "$name" "($bin)"
    MISSING=$((MISSING+1)); MISSING_LIST="$MISSING_LIST $bin"
  fi
}

echo "================================================================"
echo " REPO-SEARCH BELT + AGENT SETUP DISCOVERY"
echo " host:  $(hostname 2>/dev/null) ($(uname -s 2>/dev/null) $(uname -m 2>/dev/null))"
echo " user:  $(whoami 2>/dev/null)"
echo " when:  $(date)"
echo "================================================================"

# ── Step 0: global machine layer ────────────────────────────────────
sec "STEP 0 — GLOBAL INDEX (es / Everything CLI)"
# es uses -version (single dash), not --version
check "es" es -version

# ── The 13-tool structural-search stack ─────────────────────────────
sec "REPO-SEARCH STACK (13 tools)"
check "ripgrep"     rg
check "fd"          fd
check "bat"         bat
check "eza"         eza
check "tree"        tree
check "delta"       delta
check "jq"          jq
check "yq"          yq
check "ast-grep"    sg          # ast-grep's binary is 'sg'
check "semgrep"     semgrep
check "tree-sitter" tree-sitter
check "tokei"       tokei
check "ctags"       ctags

sub "summary"
echo "present: $PRESENT / 13   missing:$([ -n "$MISSING_LIST" ] && echo "$MISSING_LIST" || echo ' none')"
# note: /usr/bin/sg on Linux is util-linux setgroups, NOT ast-grep —
# verify the version line above says 'ast-grep' / 'ast_grep'.

# ── Claude Code skills (where repo-search lives) ────────────────────
sec "AGENT BELT — CLAUDE CODE SKILLS"
SKILL_DIRS="$HOME/.claude/skills ./.claude/skills"
found_skill=0
for base in $SKILL_DIRS; do
  [ -d "$base" ] || continue
  for d in "$base"/*/; do
    [ -f "$d/SKILL.md" ] || continue
    found_skill=1
    name="$(basename "$d")"
    # pull the YAML description: field (may wrap to next line)
    desc="$(awk '/^description:/{sub(/^description:[[:space:]]*/,"");print;exit}' "$d/SKILL.md" 2>/dev/null)"
    printf "  • %-26s %s\n" "$name" "$desc"
  done
done
[ $found_skill -eq 0 ] && echo "  (no SKILL.md found under: $SKILL_DIRS)"

# ── Slash-commands ──────────────────────────────────────────────────
sec "AGENT BELT — SLASH COMMANDS"
CMD_DIRS="$HOME/.claude/commands ./.claude/commands"
found_cmd=0
for base in $CMD_DIRS; do
  [ -d "$base" ] || continue
  for f in "$base"/*.md; do
    [ -f "$f" ] || continue
    found_cmd=1
    printf "  • /%-24s %s\n" "$(basename "${f%.md}")" "$(sed -n '1{s/^#\s*//;p}' "$f" 2>/dev/null)"
  done
done
[ $found_cmd -eq 0 ] && echo "  (no command .md files under: $CMD_DIRS)"

# ── Protocol / rules docs ───────────────────────────────────────────
sec "PROTOCOL & RULES DOCS"
for p in ./docs/repo-search-stack.md ./docs/search-protocol.md \
         "$HOME/.claude/rules/common/file-search.md" ./CLAUDE.md \
         "$HOME/.claude/CLAUDE.md" ./tools/repo_search_check.sh; do
  if [ -e "$p" ]; then printf "  ✓ %s\n" "$p"; else printf "  ·  %s (absent)\n" "$p"; fi
done

echo; echo "===== END — paste this whole file (discovery.txt) back ====="

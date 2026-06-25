#!/usr/bin/env bash
# Verify the repo-search / structural-code-search toolbelt.
# Exit code = number of missing tools.
set -u

tools=(
  "rg|ripgrep|rg --version"
  "fd|fd-find|fd --version"
  "bat|bat|bat --version"
  "eza|eza|eza --version"
  "delta|git-delta|delta --version"
  "jq|jq|jq --version"
  "yq|yq|yq --version"
  "sg|ast-grep|sg --version"
  "semgrep|semgrep|semgrep --version"
  "tree-sitter|tree-sitter-cli|tree-sitter --version"
  "tokei|tokei|tokei --version"
  "ctags|universal-ctags|ctags --version"
)

missing=0
echo "== Repo-Search Stack Check =="
printf "%-14s %-22s %s\n" "TOOL" "PACKAGE" "STATUS"
printf "%-14s %-22s %s\n" "----" "-------" "------"

for entry in "${tools[@]}"; do
  IFS='|' read -r cmd pkg ver_cmd <<< "$entry"
  if command -v "$cmd" >/dev/null 2>&1; then
    ver=$($ver_cmd 2>&1 | head -n 1)
    printf "%-14s %-22s OK  %s\n" "$cmd" "$pkg" "$ver"
  else
    printf "%-14s %-22s MISSING\n" "$cmd" "$pkg"
    missing=$((missing + 1))
  fi
done

# tree: Windows ships tree.com built-in; eza --tree is the modern equivalent.
echo ""
echo "-- tree (directory view) --"
if command -v tree >/dev/null 2>&1; then
  echo "tree: OK ($(command -v tree))"
elif command -v eza >/dev/null 2>&1; then
  echo "tree: use 'eza --tree' (eza is installed)"
elif [ -x "/c/Windows/System32/tree.com" ]; then
  echo "tree: Windows built-in at C:\\Windows\\System32\\tree.com"
else
  echo "tree: MISSING"
  missing=$((missing + 1))
fi

echo ""
if [ "$missing" -eq 0 ]; then
  echo "All tools present."
else
  echo "$missing tool(s) missing. See docs/repo-search-stack.md for install hints."
fi
exit "$missing"

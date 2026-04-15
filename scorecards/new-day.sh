#!/usr/bin/env bash
# Create a fresh scorecard for today (or a given date).
# Usage:
#   ./new-day.sh              -> creates scorecard-<today>.md
#   ./new-day.sh 2026-04-16   -> creates scorecard-2026-04-16.md
#
# Copies from scorecard-template.md if present, otherwise from the most
# recent existing scorecard (blanked out).

set -e
cd "$(dirname "$0")"

DATE="${1:-$(date +%Y-%m-%d)}"
TARGET="scorecard-${DATE}.md"

if [ -f "$TARGET" ]; then
  echo "Already exists: $TARGET"
  exit 0
fi

if [ -f "scorecard-template.md" ]; then
  SRC="scorecard-template.md"
else
  SRC="$(ls -1 scorecard-*.md 2>/dev/null | sort | tail -n 1)"
fi

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "No template or prior scorecard found."
  exit 1
fi

# Copy and replace the date header on line 1.
sed "1s/.*/# The Conversion Ladder · ${DATE}/" "$SRC" > "$TARGET"

# Blank out filled-in fields (keep structure, clear content after pipes/dashes in tally rows).
# Minimal blanking: clear counts, ratings, and bullet content.
python - "$TARGET" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
# Clear tally counts in the funnel table (4th column)
s = re.sub(r"(\|\s*[1-5]\s*\|[^|]+\|[^|]+\|)\s*[^|]*(\|[^|]*\|)", r"\1       \2", s)
# Clear AM/MID/PM ratings in behaviors table
s = re.sub(r"(\|\s*(?:Tempo|Presence|Opening Move|Hook|The Ask|Lightness)\s*\|[^|]+\|)[^|]*\|[^|]*\|[^|]*\|",
           lambda m: m.group(1) + "    |     |    |", s)
# Clear conversion rate values
s = re.sub(r"(Engaged / Attempts:|Qualified / Engaged:|Committed / Qualified:|Done / Committed:)\s*.*",
           r"\1 ___", s)
# Clear bullet content under debrief sections
open(p, "w", encoding="utf-8").write(s)
PY

echo "Created: $TARGET"

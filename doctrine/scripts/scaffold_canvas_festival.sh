#!/bin/bash
# Scaffold the canvas-90-day festival from Atlas goal g-moake7hk.
# 7 phases (one per checkpoint), 17 sequences, ~45 tasks.
# Run via: wsl -d Ubuntu -- bash "/mnt/c/Users/bruke/Pre Atlas/doctrine/scripts/scaffold_canvas_festival.sh"
set -e
cd /root/festival-project

# Idempotent cleanup of any previous run.
rm -rf festivals/planning/canvas-90-day-* festivals/ready/canvas-90-day-* festivals/active/canvas-90-day-* 2>/dev/null || true

fest create festival \
  --name "canvas-90-day" \
  --type implementation \
  --goal "Canvas product 90-day commitment: ship all 7 checkpoints tied to Atlas goal g-moake7hk-canvas-product-90-day-commitment" \
  --tags "canvas,reframe,90-day,atlas-linked" \
  --json > /tmp/scaffold_festival.json

FEST_DIR=$(python3 -c '
import json
d = json.load(open("/tmp/scaffold_festival.json"))
fest = d.get("festival", {})
dest = fest.get("dest", "planning")
directory = fest.get("directory", "")
if directory:
    print(f"/root/festival-project/festivals/{dest}/{directory}")
')
echo "FEST_DIR=$FEST_DIR"
if [ -z "$FEST_DIR" ] || [ ! -d "$FEST_DIR" ]; then
  echo "FAIL: no FEST_DIR or directory missing"
  cat /tmp/scaffold_festival.json
  exit 1
fi
cd "$FEST_DIR"

# Remove the auto-created 001_IMPLEMENT phase so our c1-c7 phases number cleanly.
rm -rf 001_IMPLEMENT

# Create a phase — returns absolute phase directory via stdout.
# fest create phase returns {"phase": {"id": "001_PHASE_NAME", ...}} where
# id doubles as the directory name under the festival root.
create_phase () {
  local name="$1" desc="$2"
  fest create phase --name "$name" --description "$desc" --type implementation --json > /tmp/phase.json
  local pid
  pid=$(python3 -c '
import json
d = json.load(open("/tmp/phase.json"))
p = d.get("phase", {})
print(p.get("id") or p.get("directory") or p.get("path") or "")
')
  if [ -z "$pid" ]; then echo "FAIL: phase create no id" >&2; cat /tmp/phase.json >&2; exit 1; fi
  case "$pid" in
    /*) echo "$pid" ;;
    *)  echo "$PWD/$pid" ;;
  esac
}

# Create a sequence inside a phase — returns absolute sequence directory.
create_seq () {
  local phase_dir="$1" seq_name="$2"
  pushd "$phase_dir" > /dev/null
  fest create sequence --name "$seq_name" --json > /tmp/seq.json
  local sid
  sid=$(python3 -c '
import json
d = json.load(open("/tmp/seq.json"))
s = d.get("sequence", {})
print(s.get("id") or s.get("directory") or s.get("path") or "")
')
  popd > /dev/null
  if [ -z "$sid" ]; then echo "FAIL: seq create no id" >&2; cat /tmp/seq.json >&2; exit 1; fi
  case "$sid" in
    /*) echo "$sid" ;;
    *)  echo "$phase_dir/$sid" ;;
  esac
}

# Create tasks in a sequence (batch via multiple --name).
create_tasks () {
  local seq_dir="$1"; shift
  local args=()
  for t in "$@"; do args+=(--name "$t"); done
  (cd "$seq_dir" && fest create task "${args[@]}" --json > /tmp/tasks.json)
}

echo "=== Phase 1: c1 demo video ==="
P=$(create_phase "c1 demo video" "sitepull demo video recorded and posted")
S=$(create_seq "$P" "record"); create_tasks "$S" "set up environment" "record demo" "edit video"
S=$(create_seq "$P" "publish"); create_tasks "$S" "upload to platform" "share post"

echo "=== Phase 2: c2 brand ==="
P=$(create_phase "c2 brand" "brand name picked + domain bought")
S=$(create_seq "$P" "name"); create_tasks "$S" "brainstorm shortlist" "trademark check" "pick final name"
S=$(create_seq "$P" "domain"); create_tasks "$S" "check availability" "purchase domain"

echo "=== Phase 3: c3 prototype ==="
P=$(create_phase "c3 prototype" "scrappy canvas prototype with URL + prompt entry points")
S=$(create_seq "$P" "scaffold"); create_tasks "$S" "choose stack" "bootstrap repo" "routing skeleton"
S=$(create_seq "$P" "entry points"); create_tasks "$S" "url entry point" "prompt entry point" "minimal canvas ui"

echo "=== Phase 4: c4 edit loop ==="
P=$(create_phase "c4 edit loop" "one edit via Claude loop works end to end")
S=$(create_seq "$P" "api wire"); create_tasks "$S" "claude api call" "edit request format"
S=$(create_seq "$P" "ui"); create_tasks "$S" "edit input" "edit apply" "roundtrip test"

echo "=== Phase 5: c5 interviews ==="
P=$(create_phase "c5 interviews" "30 or more user interviews completed")
S=$(create_seq "$P" "prep"); create_tasks "$S" "outreach list" "interview script" "scheduling tool"
S=$(create_seq "$P" "run"); create_tasks "$S" "interviews 1 to 10" "interviews 11 to 20" "interviews 21 to 30"
S=$(create_seq "$P" "synthesize"); create_tasks "$S" "tag themes" "summary report"

echo "=== Phase 6: c6 waitlist ==="
P=$(create_phase "c6 waitlist" "50 or more waitlist signups")
S=$(create_seq "$P" "landing"); create_tasks "$S" "landing page" "signup form"
S=$(create_seq "$P" "drive signups"); create_tasks "$S" "post on social" "outreach to network" "track conversion"

echo "=== Phase 7: c7 decision ==="
P=$(create_phase "c7 decision" "day 90 decision green yellow or red")
S=$(create_seq "$P" "gather"); create_tasks "$S" "review metrics" "interview insights"
S=$(create_seq "$P" "decide"); create_tasks "$S" "written decision" "commit or pivot"

echo "Scaffold done. Promoting to ready/."
FEST_BASE=$(basename "$FEST_DIR")
PLANNING_ABS="/root/festival-project/festivals/planning/$FEST_BASE"
READY_ABS="/root/festival-project/festivals/ready/$FEST_BASE"
if [ -d "$PLANNING_ABS" ]; then
  mv "$PLANNING_ABS" "$READY_ABS"
fi

echo "--- summary ---"
find "$READY_ABS" -maxdepth 4 -type f -name "*.md" | wc -l
echo "DONE: $READY_ABS"

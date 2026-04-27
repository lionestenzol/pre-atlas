"""
Mine all on-disk anatomy.json captures · cross-tabulate
   detection rule × actual DOM leaf tag (from selector)
to surface where the cascade is lossy or over-broad.

Output:
  1. Per-detection · top leaf tags it matched (entropy = how mixed)
  2. Per-leaf-tag · top detections that fired on it
  3. Confusion hotspots · detection rules where a single rule
     fans out to many different actual tags (high-bias signal)
  4. Suggested vocab splits · where one detection cleanly maps
     to N tag-flavors and could be split into N specific rules

Run: python "C:/Users/bruke/Pre Atlas/tools/anatomy-extension/dev-tools/mine_cascade.py"
"""

import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

CAPTURE_ROOTS = [
    Path("C:/Users/bruke/web-audit/.tmp"),
    Path("C:/Users/bruke/web-audit/.canvas"),
    Path("C:/Users/bruke/Pre Atlas/.tmp"),
]

# Tag at the END of a selector path · what the labeled element actually is
LEAF_TAG_RE = re.compile(r">\s*([a-zA-Z][a-zA-Z0-9-]*)(?:[:.\[#]|$)")

def leaf_tag(selector: str) -> str:
    if not selector:
        return "?"
    matches = LEAF_TAG_RE.findall(selector)
    return matches[-1].lower() if matches else "?"

def find_anatomy_files():
    files = []
    for root in CAPTURE_ROOTS:
        if root.exists():
            files.extend(root.rglob("anatomy.json"))
    return files

def main():
    files = find_anatomy_files()
    print(f"Scanning {len(files)} anatomy.json captures...\n")

    # detection -> Counter(leaf_tag)
    by_detection: dict[str, Counter] = defaultdict(Counter)
    # leaf_tag -> Counter(detection)
    by_tag: dict[str, Counter] = defaultdict(Counter)
    total_regions = 0
    captures_per_detection: dict[str, set] = defaultdict(set)

    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  SKIP {fp.name}: {e}")
            continue
        cap_id = fp.parent.name
        for r in data.get("regions", []):
            det = r.get("detection") or "(none)"
            tag = leaf_tag(r.get("selector") or "")
            by_detection[det][tag] += 1
            by_tag[tag][det] += 1
            captures_per_detection[det].add(cap_id)
            total_regions += 1

    print(f"Total regions: {total_regions}")
    print(f"Distinct detections: {len(by_detection)}")
    print(f"Distinct leaf tags: {len(by_tag)}\n")

    # 1. PER-DETECTION confusion · which tag wins, how mixed
    print("=" * 78)
    print("PER-DETECTION · top leaf tags + entropy")
    print("=" * 78)
    print(f"{'detection':<28} {'count':>6} {'top-tag':>10} {'top%':>6} {'caps':>5} {'tag-spread':>11}")
    rows = []
    for det, tags in by_detection.items():
        total = sum(tags.values())
        top_tag, top_count = tags.most_common(1)[0]
        top_pct = 100 * top_count / total
        n_distinct = len(tags)
        n_caps = len(captures_per_detection[det])
        rows.append((det, total, top_tag, top_pct, n_caps, n_distinct))
    rows.sort(key=lambda r: -r[1])
    for det, total, top_tag, top_pct, n_caps, n_distinct in rows:
        print(f"{det:<28} {total:>6d} {top_tag:>10} {top_pct:>5.1f}% {n_caps:>5d} {n_distinct:>11d}")

    # 2. CONFUSION HOTSPOTS · detection fans out across many tags
    print()
    print("=" * 78)
    print("CONFUSION HOTSPOTS · single detection → many tag flavors (mass>=20)")
    print("=" * 78)
    for det, total, top_tag, top_pct, _, n_distinct in rows:
        if total < 20:
            continue
        if top_pct >= 95:
            continue  # already clean
        tags = by_detection[det].most_common(6)
        flavors = ", ".join(f"{t}({c})" for t, c in tags)
        print(f"  {det:<28} {total:>5d}  →  {flavors}")

    # 3. SUGGESTED VOCAB SPLITS · detection split candidates
    print()
    print("=" * 78)
    print("SUGGESTED VOCAB SPLITS · detections where ≥2 tag-flavors are >=15% each")
    print("=" * 78)
    for det, total, _, _, _, _ in rows:
        if total < 30:
            continue
        tags = by_detection[det]
        flavors = [(t, c) for t, c in tags.most_common() if c / total >= 0.15]
        if len(flavors) >= 2:
            split_proposal = " · ".join(f"{det}-{t} ({c}, {100*c/total:.0f}%)" for t, c in flavors)
            print(f"  {det} (mass={total}) →")
            print(f"    {split_proposal}")

    # 4. CLEAN DETECTIONS · these are correctly mapped, no action needed
    print()
    print("=" * 78)
    print("CLEAN DETECTIONS · one tag dominates ≥95% (no split needed)")
    print("=" * 78)
    clean = [(d, t, p, n) for d, n, t, p, _, _ in rows if p >= 95 and n >= 5]
    for det, top_tag, top_pct, total in clean:
        print(f"  {det:<28} {total:>5d}  ({top_pct:.0f}% {top_tag})")

if __name__ == "__main__":
    main()

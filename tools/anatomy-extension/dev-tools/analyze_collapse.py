#!/usr/bin/env python3
"""Analyze sibling-collapse impact in existing anatomy captures.

Bruke's symptom: "auto-label was missing elements I could clearly see ·
identical shape · one labeled, the other wrong/missing."

Hypothesis: pattern-repeat collapse in findRepeatContainers() drops
siblings beyond the first 2 exemplars. This script measures the impact
by counting how many regions are pattern-repeat list-containers and
estimating how many siblings each collapsed.

For each capture, also report selector-fanout (siblings whose CSS
selectors share a parent path), to estimate WHICH labels got merged
into a list summary.

Run: python tools/anatomy-extension/dev-tools/analyze_collapse.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter
from typing import Any


def parent_path(selector: str) -> str:
    """Drop the last selector segment to get the parent path."""
    if not selector:
        return ""
    parts = re.split(r"\s*>\s*", selector)
    return " > ".join(parts[:-1])


def find_anatomy_jsons() -> list[Path]:
    roots = [
        Path("C:/Users/bruke/web-audit/.canvas"),
        Path("C:/Users/bruke/web-audit/.tmp"),
        Path("C:/Users/bruke/OneDrive/Desktop"),
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("anatomy*.json"):
            if p.stat().st_size < 500:
                continue
            found.append(p)
    return sorted(set(found))


def analyze(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        env = json.load(f)
    regions = env.get("regions") or []
    if not regions:
        return {}

    pattern_repeats = [r for r in regions if r.get("detection") == "pattern-repeat"]
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for r in regions:
        sel = r.get("selector") or ""
        parent = parent_path(sel)
        by_parent[parent].append(r)

    fanout = sorted(
        ((parent, sibs) for parent, sibs in by_parent.items() if len(sibs) >= 3),
        key=lambda x: -len(x[1]),
    )

    return {
        "path": path,
        "total_regions": len(regions),
        "pattern_repeats": pattern_repeats,
        "fanout_top5": fanout[:5],
    }


def main() -> int:
    files = find_anatomy_jsons()
    print(f"analyzing {len(files)} captures for sibling-collapse impact\n")

    total_pattern_repeats = 0
    summary_rows: list[tuple[str, int, int, int, list]] = []

    for path in files:
        info = analyze(path)
        if not info:
            continue
        prs = info["pattern_repeats"]
        total_pattern_repeats += len(prs)
        kept_exemplars_estimate = 0
        collapsed_estimate = 0
        for pr in prs:
            name = pr.get("name") or ""
            # Names look like "list · 5· path" or "list · 6· div · 1" — middle-dot
            # not 'x'. Pull the first integer after "list".
            m = re.search(r"list\D+(\d+)", name)
            count = int(m.group(1)) if m else 0
            kept_exemplars_estimate += 2
            collapsed_estimate += max(0, count - 2)
        summary_rows.append((
            str(path),
            info["total_regions"],
            len(prs),
            collapsed_estimate,
            info["fanout_top5"],
        ))

    print("=" * 78)
    print(f"TOTAL pattern-repeat regions across all captures: {total_pattern_repeats}")
    print("=" * 78)

    print("\nPER-CAPTURE collapse impact:")
    print(f"  {'capture':<60} {'regs':>5} {'lists':>5} {'collapsed':>9}")
    print("  " + "-" * 80)
    for path, regs, lists, collapsed, _ in summary_rows:
        short = path.replace("C:/Users/bruke/", "~/").replace("\\", "/")
        if len(short) > 58:
            short = short[:55] + "..."
        marker = "!" if collapsed > 0 else " "
        print(f" {marker}{short:<60} {regs:>5} {lists:>5} {collapsed:>9}")

    print("\nWHERE pattern-repeats LIVE (top 10):")
    all_prs: list[tuple[str, dict]] = []
    for path, _, _, _, _ in summary_rows:
        with open(path, "r", encoding="utf-8") as f:
            env = json.load(f)
        for r in env.get("regions", []):
            if r.get("detection") == "pattern-repeat":
                all_prs.append((path, r))
    for path, r in all_prs[:10]:
        cap = Path(path).parent.name
        print(f"  [{cap[:30]:<30}]  '{(r.get('name') or '')[:40]:<40}'  selector={(r.get('selector') or '')[:60]}")

    print("\nSELECTOR-FANOUT (parents whose children labels look alike — top 5 per capture):")
    for path, regs, lists, collapsed, fanout in summary_rows[:8]:
        if not fanout:
            continue
        cap = Path(path).parent.name
        print(f"\n  {cap}:")
        for parent, sibs in fanout[:3]:
            unique_names = Counter(s.get("name", "") for s in sibs)
            print(f"    {len(sibs)} siblings under: {parent[:60]}")
            for name, n in unique_names.most_common(3):
                if n > 1:
                    print(f"      \"{name[:40]}\" x{n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

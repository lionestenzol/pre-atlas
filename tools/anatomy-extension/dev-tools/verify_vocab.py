#!/usr/bin/env python3
"""Port of detection-vocab.js + canvas-engine normalize.ts to Python.

Walks every anatomy.json under web-audit/.canvas, web-audit/.tmp, and the
Desktop exports. For each region: validates against the closed vocabulary,
normalizes to a canvas-engine pattern group, and reports.

A clean run prints "0 default-bucket" — the v0.4 vocab-lock contract.
Anything else is a bug or stale capture worth fixing.

Run: python tools/anatomy-extension/dev-tools/verify_vocab.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

CLICKABLE_RULE_PREFIXES = (
    "r2-", "r3-", "r4-", "r5-", "r7-", "r8-", "r9-", "r11-", "r12-",
)
CLICKABLE_LITERALS = {
    "auto-label", "alt-click", "manual", "legacy",
    "custom-element", "cursor-dwell", "button-cluster", "hero",
}
LANDMARK_LITERALS = {
    "sem-header", "sem-footer", "sem-nav", "sem-main",
    "sem-aside", "sem-section", "landmark",
}
WEB_AUDIT_LITERALS = {"landmark", "heading", "button-cluster", "hero"}
HEADING_RX = re.compile(r"^sem-h[1-6]$")
KIND_VALUES = {"sem", "click", "list", "card", "custom", "watch"}

DETECTION_LITERALS = (
    CLICKABLE_LITERALS
    | LANDMARK_LITERALS
    | WEB_AUDIT_LITERALS
    | {"pattern-repeat", "card-heuristic", "form", "sem-form"}
)


def is_detection_valid(detection: str | None) -> bool:
    if not detection:
        return False
    d = detection.lower()
    if d in DETECTION_LITERALS:
        return True
    if HEADING_RX.match(d):
        return True
    return any(d.startswith(p) for p in CLICKABLE_RULE_PREFIXES)


def normalize_detection(region: dict[str, Any]) -> str:
    detection = (region.get("detection") or "").lower()
    kind = (region.get("kind") or "").lower()
    name = (region.get("name") or "").lower()

    if kind == "card" or detection == "card-heuristic":
        return "card"
    if detection == "pattern-repeat" or kind == "list":
        return "list"
    if detection in ("form", "sem-form") or name == "form" or "search bar" in name:
        return "form"
    if HEADING_RX.match(detection) or detection == "heading":
        return "heading"
    if detection in LANDMARK_LITERALS:
        return "landmark"
    if detection in CLICKABLE_LITERALS:
        return "clickable"
    if detection in ("button-cluster", "hero"):
        return "clickable"
    if any(detection.startswith(p) for p in CLICKABLE_RULE_PREFIXES):
        return "clickable"
    if kind in ("click", "watch"):
        return "clickable"
    return "default"


def find_anatomy_jsons() -> list[Path]:
    roots = [
        Path("C:/Users/bruke/web-audit/.canvas"),
        Path("C:/Users/bruke/web-audit/.tmp"),
        Path("C:/Users/bruke/OneDrive/Desktop"),
        Path("C:/Users/bruke/Pre Atlas/.tmp"),
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("anatomy*.json"):
            if "node_modules" in p.parts:
                continue
            if p.stat().st_size < 100:
                continue
            found.append(p)
    return sorted(set(found))


def main() -> int:
    files = find_anatomy_jsons()
    if not files:
        print("no anatomy.json files found", file=sys.stderr)
        return 1

    print(f"scanning {len(files)} anatomy.json files\n")

    total_regions = 0
    total_failures = 0
    group_counts: Counter[str] = Counter()
    detection_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    failures_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_file_summary: list[tuple[str, int, int, int]] = []

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                envelope = json.load(f)
        except Exception as exc:
            print(f"  skip {path.name}: {exc}", file=sys.stderr)
            continue

        regions = envelope.get("regions") or []
        file_default = 0
        file_failures = 0
        for region in regions:
            total_regions += 1
            detection_counts[region.get("detection") or "<none>"] += 1
            kind_counts[region.get("kind") or "<none>"] += 1
            if not is_detection_valid(region.get("detection")):
                total_failures += 1
                file_failures += 1
                failures_by_file[str(path)].append({
                    "id": region.get("id"),
                    "detection": region.get("detection"),
                    "kind": region.get("kind"),
                    "name": region.get("name"),
                })
                continue
            group = normalize_detection(region)
            group_counts[group] += 1
            if group == "default":
                file_default += 1
        per_file_summary.append((str(path), len(regions), file_default, file_failures))

    print("=" * 72)
    print(f"TOTAL REGIONS:       {total_regions}")
    print(f"VALIDATION FAILURES: {total_failures}    (dropped at envelope-build)")
    print(f"DEFAULT-BUCKET:      {group_counts.get('default', 0)}    (validates but unranked)")
    print("=" * 72)

    print("\nGROUP DISTRIBUTION:")
    for group, count in group_counts.most_common():
        print(f"  {group:<10} {count}")

    print("\nDETECTION TOP 15:")
    for detection, count in detection_counts.most_common(15):
        print(f"  {count:>5}  {detection}")

    print("\nKIND DISTRIBUTION:")
    for kind, count in kind_counts.most_common():
        print(f"  {count:>5}  {kind}")

    if failures_by_file:
        print("\nVALIDATION FAILURES (would be dropped + warned at envelope-build):")
        for path, fails in failures_by_file.items():
            short = path.replace("C:/Users/bruke/", "~/").replace("\\", "/")
            print(f"  {short}")
            for fail in fails[:5]:
                print(f"    {json.dumps(fail)}")
            if len(fails) > 5:
                print(f"    ... and {len(fails) - 5} more")

    print("\nPER-FILE SUMMARY (regions / default-group / dropped):")
    for path, regions, defaults, fails in per_file_summary:
        short = path.replace("C:/Users/bruke/", "~/").replace("\\", "/")
        marker = " " if (defaults == 0 and fails == 0) else "!"
        print(f"  {marker} {short}  ({regions}/{defaults}/{fails})")

    return 0 if group_counts.get("default", 0) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

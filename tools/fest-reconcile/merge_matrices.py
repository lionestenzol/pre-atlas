"""
Phase 3 · Sequence 05 · merge_matrices

Merge era_*_matrix.json + fs_overlay.json into one master matrix:
festival_out/era_cluster_matrix.json

Shape (per cluster):
  channels: { chatgpt: {era_1: {count, samples}, ...},
              cc:      {era_1: {count, samples}, ...},
              fs_ctime:{era_1: [names], ...},
              fs_mtime:{era_1: [names], ...} }

Era 4 (`era_4_now`) is included for completeness; it was computed during
merge-prep using the same build_era_matrix.py script (not a separately
listed Phase 3 sequence, but its inclusion makes the master matrix
self-consistent and feeds Phase 4 lookups).

HOTL: counts + sample IDs surfaced verbatim; no auto-classification.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "festival_out"

V2 = "--v2" in sys.argv
SUFFIX = "_v2" if V2 else ""

ERA_FILES: list[tuple[str, str]] = [
    ("era_1_pre_cc", f"era_1_matrix{SUFFIX}.json"),
    ("era_2_early_cc", f"era_2_matrix{SUFFIX}.json"),
    ("era_3_heavy_cc", f"era_3_matrix{SUFFIX}.json"),
    ("era_4_now", f"era_4_matrix{SUFFIX}.json"),
]
FS_OVERLAY = f"fs_overlay{SUFFIX}.json"
OUT = OUT_DIR / f"era_cluster_matrix{SUFFIX}.json"


def load_json(name: str) -> dict[str, Any]:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


def main() -> None:
    era_docs: dict[str, dict[str, Any]] = {
        label: load_json(fname) for label, fname in ERA_FILES
    }
    fs = load_json(FS_OVERLAY)

    cluster_names = [c["name"] for c in era_docs["era_1_pre_cc"]["clusters"]]

    # Index each era doc by cluster name
    era_by_name: dict[str, dict[str, dict[str, Any]]] = {}
    for era_label, doc in era_docs.items():
        era_by_name[era_label] = {c["name"]: c for c in doc["clusters"]}

    fs_by_name = {c["name"]: c for c in fs["clusters"]}

    merged_clusters: list[dict[str, Any]] = []
    for name in cluster_names:
        chatgpt_by_era: dict[str, dict[str, Any]] = {}
        cc_by_era: dict[str, dict[str, Any]] = {}
        for era_label in era_by_name:
            cell = era_by_name[era_label][name]["channels"]
            chatgpt_by_era[era_label] = cell["chatgpt"]
            cc_by_era[era_label] = cell["cc"]

        fs_cluster = fs_by_name.get(name, {})
        fs_ctime = fs_cluster.get("ctime_buckets", {})
        fs_mtime = fs_cluster.get("mtime_buckets", {})

        merged_clusters.append(
            {
                "name": name,
                "seed_terms": era_by_name["era_1_pre_cc"][name]["seed_terms"],
                "channels": {
                    "chatgpt": chatgpt_by_era,
                    "cc": cc_by_era,
                    "fs_ctime": {
                        era_label: fs_ctime.get(era_label, [])
                        for era_label, _ in ERA_FILES
                    },
                    "fs_mtime": {
                        era_label: fs_mtime.get(era_label, [])
                        for era_label, _ in ERA_FILES
                    },
                },
                "fs_items": fs_cluster.get("items", []),
                "fs_matched_count": fs_cluster.get("matched_to_fs", 0),
                "fs_portfolio_hit_count": fs_cluster.get(
                    "portfolio_hit_count", 0
                ),
            }
        )

    totals_by_era: dict[str, dict[str, int]] = {}
    for era_label in era_by_name:
        totals_by_era[era_label] = {
            "chatgpt_in_era": era_docs[era_label]["totals"]["chatgpt_in_era"],
            "cc_in_era": era_docs[era_label]["totals"]["cc_in_era"],
        }

    out = {
        "phase": "003_CROSS_REFERENCE_MATRIX",
        "sequence": "05_merge_matrices",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "method": (
            "Merge era_1..era_4 matrices + fs_overlay by cluster name. "
            "Each cluster carries 4 era columns per channel "
            "(chatgpt, cc, fs_ctime, fs_mtime). Era 4 computed at merge "
            "time for completeness; Era 1-3 were the explicit Phase 3 "
            "sequences."
        ),
        "eras": [
            {
                "label": label,
                "start": era_docs[label]["era"]["start"],
                "end": era_docs[label]["era"]["end"],
            }
            for label, _ in ERA_FILES
        ],
        "totals_by_era": totals_by_era,
        "substring_warnings_carried_forward": era_docs["era_1_pre_cc"].get(
            "substring_warnings_carried_forward", []
        ),
        "fs_unmatched_hits": fs.get("unmatched_hits", []),
        "clusters": merged_clusters,
    }

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    print()
    print("Master matrix (counts only, chatgpt | cc | fs_ctime):")
    print(
        f"  {'cluster':22s} "
        f"{'era_1':>14s} {'era_2':>14s} {'era_3':>14s} {'era_4':>14s}"
    )
    for c in merged_clusters:
        cells = []
        for era_label, _ in ERA_FILES:
            cg = c["channels"]["chatgpt"][era_label]["count"]
            cc_ = c["channels"]["cc"][era_label]["count"]
            fs_n = len(c["channels"]["fs_ctime"].get(era_label, []))
            cells.append(f"{cg:3d}|{cc_:3d}|{fs_n:2d}")
        print(f"  {c['name']:22s} " + " ".join(f"{x:>14s}" for x in cells))


if __name__ == "__main__":
    main()

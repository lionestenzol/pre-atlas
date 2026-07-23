"""
Phase 3 sequences 01-03: build (cluster x channel) matrix for one era.

Inputs:
  festival_out/clusters_final.json
  festival_out/chatgpt_temporal.json
  festival_out/cc_temporal.json

Match logic: substring of any cluster seed_term against ChatGPT title
or CC first_user_msg (same rule Phase 2 used, so totals reconcile).

For each (cluster x channel) cell within the era window: emit count +
5 deterministic sample IDs (earliest by date).

HOTL: no auto-classification; substring warnings carried forward
verbatim from clusters_final.json.

Usage:
  python build_era_matrix.py --era-label era_1_pre_cc \\
      --start 2024-08-21 --end 2026-02-08 --out festival_out/era_1_matrix.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from _match import has_seed_match  # word-boundary matcher

OUT_DIR = ROOT / "festival_out"
# CLUSTERS path is overridden by --clusters arg if given.
CLUSTERS = OUT_DIR / "clusters_final.json"
CHATGPT = OUT_DIR / "chatgpt_temporal.json"
CC = OUT_DIR / "cc_temporal.json"

SAMPLES_PER_CELL = 5


def parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    # accept "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS..."
    return dt.date.fromisoformat(s[:10])


def in_era(d: dt.date | None, start: dt.date, end: dt.date) -> bool:
    return d is not None and start <= d <= end


# has_seed_match imported from _match (word-boundary regex).


def build_cell(
    items: list[dict[str, Any]],
    seeds_lc: list[str],
    text_key: str,
    id_key: str,
    date_key: str,
    start: dt.date,
    end: dt.date,
) -> dict[str, Any]:
    matched: list[tuple[dt.date, str, str]] = []
    for it in items:
        d = parse_date(it.get(date_key))
        if not in_era(d, start, end):
            continue
        text = it.get(text_key) or ""
        if has_seed_match(text, seeds_lc):
            matched.append((d, it.get(id_key, ""), text[:160]))
    matched.sort(key=lambda r: (r[0], r[1]))
    return {
        "count": len(matched),
        "samples": [
            {"id": rid, "date": rd.isoformat(), "preview": preview}
            for rd, rid, preview in matched[:SAMPLES_PER_CELL]
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--era-label", required=True)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--out", required=True, help="output JSON path (relative to repo root or absolute)")
    ap.add_argument("--clusters", default=str(CLUSTERS), help="clusters_final.json path (override for v2 run)")
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)

    clusters_doc = json.loads(Path(args.clusters).read_text(encoding="utf-8"))
    chatgpt_doc = json.loads(CHATGPT.read_text(encoding="utf-8"))
    cc_doc = json.loads(CC.read_text(encoding="utf-8"))

    chatgpt_items = chatgpt_doc["items"]
    cc_items = cc_doc["items"]

    out_clusters: list[dict[str, Any]] = []
    chatgpt_total = 0
    cc_total = 0

    for c in clusters_doc["clusters"]:
        seeds_lc = [s.lower() for s in c["seed_terms"]]

        chatgpt_cell = build_cell(
            chatgpt_items,
            seeds_lc,
            text_key="title",
            id_key="convo_id",
            date_key="first_date",
            start=start,
            end=end,
        )
        cc_cell = build_cell(
            cc_items,
            seeds_lc,
            text_key="first_user_msg",
            id_key="session_id",
            date_key="first_ts",
            start=start,
            end=end,
        )

        chatgpt_total += chatgpt_cell["count"]
        cc_total += cc_cell["count"]

        out_clusters.append(
            {
                "name": c["name"],
                "seed_terms": c["seed_terms"],
                "channels": {
                    "chatgpt": chatgpt_cell,
                    "cc": cc_cell,
                },
            }
        )

    out = {
        "phase": "003_CROSS_REFERENCE_MATRIX",
        "sequence": args.era_label,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "era": {
            "label": args.era_label,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "method": (
            "Substring match of cluster seed_terms (case-insensitive) "
            "against ChatGPT title and CC first_user_msg. Items filtered "
            "to era window by first_date (ChatGPT) / first_ts (CC). "
            "Samples sorted by date ascending, capped at "
            f"{SAMPLES_PER_CELL} per cell. HOTL: substring warnings from "
            "Phase 2 (clusters_final.json) still apply and are not "
            "auto-filtered here."
        ),
        "samples_per_cell": SAMPLES_PER_CELL,
        "totals": {
            "chatgpt_in_era": sum(
                1
                for it in chatgpt_items
                if in_era(parse_date(it.get("first_date")), start, end)
            ),
            "cc_in_era": sum(
                1
                for it in cc_items
                if in_era(parse_date(it.get("first_ts")), start, end)
            ),
            "chatgpt_matched_sum_over_clusters": chatgpt_total,
            "cc_matched_sum_over_clusters": cc_total,
            "note": (
                "matched_sum_over_clusters can exceed in_era because one "
                "item may match multiple clusters (e.g. an 'anatomy "
                "canvas' chat hits both anatomy and canvas_render)."
            ),
        },
        "substring_warnings_carried_forward": [
            {"cluster": c["name"], "warning": w}
            for c in clusters_doc["clusters"]
            for w in c.get("validation", {}).get("substring_warnings", [])
        ],
        "clusters": out_clusters,
    }

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / args.out
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"WROTE {out_path}")
    print(f"  era: {args.era_label}  window: {start} -> {end}")
    print(f"  chatgpt_in_era: {out['totals']['chatgpt_in_era']}")
    print(f"  cc_in_era:      {out['totals']['cc_in_era']}")
    print(f"  per-cluster (count chatgpt | count cc):")
    for c in out_clusters:
        cg = c["channels"]["chatgpt"]["count"]
        cc_ = c["channels"]["cc"]["count"]
        print(f"    {c['name']:22s} {cg:6d} | {cc_:6d}")


if __name__ == "__main__":
    main()

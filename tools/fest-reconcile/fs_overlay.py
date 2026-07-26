"""
Phase 3 · Sequence 04 · fs_overlay

For each cluster, join its portfolio_hits (from clusters_final.json,
already classified in Phase 2) against fs_temporal items by
(name, surface) and bucket each item into eras by ctime (appearance
on disk) and mtime (last touch).

HOTL: no auto-classification; we reuse the Phase 2 classification.

Output: festival_out/fs_overlay.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "festival_out"
DEFAULT_CLUSTERS = OUT_DIR / "clusters_final.json"
FS = OUT_DIR / "fs_temporal.json"
DEFAULT_OUT = OUT_DIR / "fs_overlay.json"

ERAS: list[tuple[str, dt.date, dt.date]] = [
    ("era_1_pre_cc", dt.date(2024, 8, 21), dt.date(2026, 2, 8)),
    ("era_2_early_cc", dt.date(2026, 2, 9), dt.date(2026, 3, 31)),
    ("era_3_heavy_cc", dt.date(2026, 4, 1), dt.date(2026, 5, 15)),
    ("era_4_now", dt.date(2026, 5, 16), dt.date(2099, 1, 1)),
]


def parse_iso_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def era_for(d: dt.date | None) -> str | None:
    if d is None:
        return None
    for label, start, end in ERAS:
        if start <= d <= end:
            return label
    if d < ERAS[0][1]:
        return "pre_corpus_start"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clusters", default=str(DEFAULT_CLUSTERS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    clusters_doc = json.loads(Path(args.clusters).read_text(encoding="utf-8"))
    fs_doc = json.loads(FS.read_text(encoding="utf-8"))

    fs_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for it in fs_doc["items"]:
        key = (it.get("name", ""), it.get("surface", ""))
        fs_by_key[key] = it

    out_clusters: list[dict[str, Any]] = []
    unmatched_hits: list[dict[str, Any]] = []

    for c in clusters_doc["clusters"]:
        items_with_dates: list[dict[str, Any]] = []
        ctime_buckets: dict[str, list[str]] = {label: [] for label, _, _ in ERAS}
        ctime_buckets["pre_corpus_start"] = []
        ctime_buckets["unknown"] = []
        mtime_buckets: dict[str, list[str]] = {label: [] for label, _, _ in ERAS}
        mtime_buckets["pre_corpus_start"] = []
        mtime_buckets["unknown"] = []

        for hit in c.get("portfolio_hits", []):
            key = (hit.get("name", ""), hit.get("surface", ""))
            fs_it = fs_by_key.get(key)
            if fs_it is None:
                unmatched_hits.append(
                    {"cluster": c["name"], "name": key[0], "surface": key[1]}
                )
                continue

            mtime = fs_it.get("mtime")
            ctime = fs_it.get("ctime")
            ctime_d = parse_iso_date(ctime)
            mtime_d = parse_iso_date(mtime)
            ctime_era = era_for(ctime_d) or "unknown"
            mtime_era = era_for(mtime_d) or "unknown"

            items_with_dates.append(
                {
                    "name": hit["name"],
                    "surface": hit["surface"],
                    "path": fs_it.get("path"),
                    "ctime": ctime,
                    "mtime": mtime,
                    "ctime_era": ctime_era,
                    "mtime_era": mtime_era,
                    "signal_band": hit.get("signal_band"),
                    "matched_terms": hit.get("matched_terms", []),
                    "fs_error": fs_it.get("error"),
                }
            )
            ctime_buckets[ctime_era].append(hit["name"])
            mtime_buckets[mtime_era].append(hit["name"])

        out_clusters.append(
            {
                "name": c["name"],
                "portfolio_hit_count": c.get("portfolio_hit_count", 0),
                "matched_to_fs": len(items_with_dates),
                "ctime_buckets": ctime_buckets,
                "mtime_buckets": mtime_buckets,
                "items": items_with_dates,
            }
        )

    out = {
        "phase": "003_CROSS_REFERENCE_MATRIX",
        "sequence": "04_fs_overlay",
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "method": (
            "Join cluster.portfolio_hits (from clusters_final.json) "
            "against fs_temporal items by (name, surface). Bucket each "
            "item into eras by ctime (appearance on disk) and mtime "
            "(last touch). No re-classification; Phase 2 classification "
            "is authoritative."
        ),
        "eras": [
            {"label": label, "start": start.isoformat(), "end": end.isoformat()}
            for label, start, end in ERAS
        ],
        "unmatched_hits_count": len(unmatched_hits),
        "unmatched_hits": unmatched_hits,
        "clusters": out_clusters,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"WROTE {out_path}")
    print(f"  unmatched_hits: {len(unmatched_hits)}")
    print(f"  per-cluster ctime distribution:")
    for c in out_clusters:
        cb = c["ctime_buckets"]
        e1 = len(cb["era_1_pre_cc"])
        e2 = len(cb["era_2_early_cc"])
        e3 = len(cb["era_3_heavy_cc"])
        e4 = len(cb["era_4_now"])
        unk = len(cb["unknown"])
        pre = len(cb["pre_corpus_start"])
        print(
            f"    {c['name']:22s} e1={e1:2d} e2={e2:2d} e3={e3:2d} "
            f"e4={e4:2d} pre={pre:2d} unk={unk:2d}  total_matched={c['matched_to_fs']}"
        )


if __name__ == "__main__":
    main()

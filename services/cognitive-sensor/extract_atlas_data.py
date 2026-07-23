"""extract_atlas_data.py — pull the 6.1 MB embedded JSON out of cognitive_atlas.html
into discrete files so atlas_query.py can serve every screen-visible data point.

Run after every `python build_cognitive_atlas.py` (or change the build script
to call this at the end).

Writes:
    atlas_graph.json           — sigma graph: nodes + edges
    atlas_points_index.json    — per-cluster: 2D bounding box, density, centroid,
                                 role breakdown, time histogram (no raw points)
    atlas_points.json          — full per-message arrays (only if --full passed)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()


def _extract_D_blob(html: str) -> dict:
    """Pull `const D = {...}` JSON out of the rendered HTML."""
    needle = "const D = "
    i = html.find(needle)
    if i < 0:
        raise SystemExit("could not find `const D = ` in HTML")
    j = i + len(needle)
    depth = 0
    in_str = False
    esc = False
    end = j
    while j < len(html):
        c = html[j]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"' and not esc:
            in_str = not in_str
        elif not in_str:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        j += 1
    return json.loads(html[i + len(needle): end])


def _build_points_index(D: dict) -> dict:
    """Per-cluster aggregates derived from per-message points.

    For each cluster_id, compute:
      - n_points
      - bbox_2d: {x_min, x_max, y_min, y_max}
      - centroid_2d: (mean_x, mean_y)
      - density: n_points / bbox_area (points-per-unit-area)
      - role_breakdown: {user, assistant, tool}
      - time_histogram: 10-bin (over normalized time 0..1)
    """
    xs = D["x"]; ys = D["y"]
    roles = D["roles"]
    cluster_per_msg = D["layers"]["cluster"]
    time_per_msg = D["layers"].get("time") or []
    if not time_per_msg or len(time_per_msg) != len(xs):
        time_per_msg = [None] * len(xs)

    by_cluster: dict[int, list[int]] = defaultdict(list)
    for i, cl in enumerate(cluster_per_msg):
        by_cluster[int(cl)].append(i)

    index: dict[str, dict] = {}
    for cl, idxs in by_cluster.items():
        cl_xs = [xs[i] for i in idxs]
        cl_ys = [ys[i] for i in idxs]
        x_min, x_max = min(cl_xs), max(cl_xs)
        y_min, y_max = min(cl_ys), max(cl_ys)
        area = max((x_max - x_min) * (y_max - y_min), 0.0001)
        role_counts: Counter = Counter(roles[i] for i in idxs)
        bins = [0] * 10
        for i in idxs:
            t = time_per_msg[i]
            if t is None:
                continue
            b = min(int(t * 10), 9)
            bins[b] += 1

        index[str(cl)] = {
            "n_points": len(idxs),
            "bbox_2d": {
                "x_min": round(x_min, 4), "x_max": round(x_max, 4),
                "y_min": round(y_min, 4), "y_max": round(y_max, 4),
            },
            "centroid_2d": {
                "x": round(sum(cl_xs) / len(cl_xs), 4),
                "y": round(sum(cl_ys) / len(cl_ys), 4),
            },
            "density": round(len(idxs) / area, 4),
            "role_breakdown": {r: role_counts.get(r, 0) for r in ("user", "assistant", "tool")},
            "time_histogram_10bin": bins,
        }
    return index


def main() -> int:
    p = argparse.ArgumentParser(prog="extract_atlas_data")
    p.add_argument("--html", type=Path, default=BASE / "cognitive_atlas.html")
    p.add_argument("--out-dir", type=Path, default=BASE)
    p.add_argument("--full", action="store_true",
                   help="Also write atlas_points.json (the full ~3 MB per-message arrays)")
    args = p.parse_args()

    if not args.html.exists():
        raise SystemExit(f"missing: {args.html}")

    print(f"Reading {args.html.name} ...")
    html = args.html.read_text(encoding="utf-8")
    D = _extract_D_blob(html)
    print(f"  D blob: {len(html):,} chars HTML, {len(D)} top-level keys")

    # 1. atlas_graph.json
    graph = D.get("graph", {})
    out = args.out_dir / "atlas_graph.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(graph, f, separators=(",", ":"))
    print(f"  Wrote {out.name} ({len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges)")

    # 2. atlas_points_index.json
    index = _build_points_index(D)
    out = args.out_dir / "atlas_points_index.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
    print(f"  Wrote {out.name} ({len(index)} cluster aggregates)")

    # 3. atlas_points.json (optional — large)
    if args.full:
        points = {
            "x": D["x"], "y": D["y"],
            "convo_ids": D["convo_ids"],
            "roles": D["roles"],
            "msg_indices": D["msg_indices"],
            "word_counts": D["word_counts"],
            "layers": D["layers"],
            "titleLookup": D.get("titleLookup", {}),
            "dateLookup": D.get("dateLookup", {}),
        }
        out = args.out_dir / "atlas_points.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(points, f, separators=(",", ":"))
        print(f"  Wrote {out.name} ({len(D['x']):,} points, {out.stat().st_size/1024/1024:.1f} MB)")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

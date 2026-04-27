"""
thread_ranker — rank all 1397 conversations by mining potential.

Signals:
  mining_score  = unique_blocks * max(1, resolution_hits)
                  (unimplemented code × how much it actually worked)
  unmined_pct   = unique / total blocks (1.0 = nothing in repo yet)

Usage:
  python thread_ranker.py                 # rank all, print top 20
  python thread_ranker.py --top 50        # top 50
  python thread_ranker.py --min-blocks 10 # only threads with 10+ code blocks
  python thread_ranker.py --json queue.json
  python thread_ranker.py --score-cards top20_cards.json  # full cards for top 20
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from pathlib import Path

from thread_scorer import (
    BASE, DB_PATH, load_memory, load_clusters, load_classifications,
    score_thread, _fix_stdout
)


def rank_all(memory, clusters_tuple, classifications, con,
             min_blocks: int = 1) -> list[dict]:
    clusters, by_cluster = clusters_tuple
    results: list[dict] = []
    total = len(memory)
    for i in range(total):
        if i % 100 == 0:
            print(f"  scoring {i}/{total}...", file=sys.stderr)
        cid = str(i)
        card = score_thread(cid, memory, con, clusters, by_cluster, classifications)
        if "error" in card:
            continue
        blocks = card["code_blocks"]["count"]
        if blocks < min_blocks:
            continue
        rs = card["repo_scan"]
        unique = rs["blocks_unique"]
        res_hits = card["kwic"]["resolution_hits"]
        frust = card["kwic"]["frustration_hits"]
        size = card["size"]["total"]
        mining_score = unique * max(1, res_hits)
        unmined_pct = (unique / blocks) if blocks else 0.0
        results.append({
            "convo_id": cid,
            "title": card["title"],
            "date": card["date"],
            "size": size,
            "blocks": blocks,
            "unique": unique,
            "in_repo": rs["blocks_overlapping"],
            "unmined_pct": round(unmined_pct, 2),
            "resolution": res_hits,
            "frustration": frust,
            "mining_score": mining_score,
            "cluster": card["cluster"]["cluster_id"],
            "domain": card["classification"]["domain"],
            "outcome": card["classification"]["outcome"],
        })
    results.sort(key=lambda r: r["mining_score"], reverse=True)
    return results


def print_table(rows: list[dict], limit: int = 20) -> None:
    header = f"{'rank':<5}{'cid':<6}{'score':<8}{'uniq':<6}{'in_repo':<9}{'res':<5}{'frust':<7}{'date':<12}{'title'}"
    print(header)
    print("-" * 120)
    for i, r in enumerate(rows[:limit]):
        title = (r['title'] or '?')[:55]
        print(f"{i+1:<5}{r['convo_id']:<6}{r['mining_score']:<8}{r['unique']:<6}{r['in_repo']:<9}"
              f"{r['resolution']:<5}{r['frustration']:<7}{(r['date'] or '?'):<12}{title}")


def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-blocks", type=int, default=1)
    ap.add_argument("--json", help="write full ranking to this path")
    ap.add_argument("--score-cards", help="also write scored cards (full signal set) for top N")
    args = ap.parse_args()

    memory = load_memory()
    clusters_tuple = load_clusters()
    classifications = load_classifications()
    con = sqlite3.connect(str(DB_PATH))

    print(f"ranking {len(memory)} conversations (min_blocks={args.min_blocks})...", file=sys.stderr)
    rows = rank_all(memory, clusters_tuple, classifications, con, args.min_blocks)
    print(f"\n{len(rows)} threads have code. Top {args.top}:\n", file=sys.stderr)
    print_table(rows, args.top)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "total_scored": len(rows),
            "ranking": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)

    if args.score_cards:
        clusters, by_cluster = clusters_tuple
        top_ids = [r["convo_id"] for r in rows[:args.top]]
        cards = [score_thread(cid, memory, con, clusters, by_cluster, classifications) for cid in top_ids]
        Path(args.score_cards).write_text(json.dumps({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "count": len(cards),
            "source": "thread_ranker top",
            "cards": cards,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.score_cards}", file=sys.stderr)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

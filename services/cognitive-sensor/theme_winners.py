"""
theme_winners — for each code theme, find the single best thread to stand up as a repo.

Combines thread_ranker's mining_score with code_themes membership:
  For each theme, rank its member threads by mining_score and pick the top.
  That thread becomes the "start here" candidate for that theme.

Output:
  For each theme, emit one winner with: convo_id, title, date, blocks, resolution,
  top_imports, suggested_repo_name.

Usage:
  python theme_winners.py              # print table
  python theme_winners.py --json winners.json
  python theme_winners.py --cards winners_cards.json  # full scored cards for each winner
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

THEMES_PATH = BASE / "code_themes.json"


def _suggest_repo_name(theme: str, title: str) -> str:
    slug = "-".join(w.lower() for w in title.split() if w.isalnum() or w.replace("-", "").isalnum())
    slug = slug[:30].rstrip("-") or "unnamed"
    return f"{theme}__{slug}"


def rank_theme_members(memory, clusters_tuple, classifications, con,
                       theme_threads: dict[str, list[int]],
                       theme_imports: dict[str, dict]) -> list[dict]:
    clusters, by_cluster = clusters_tuple
    winners: list[dict] = []
    total_themes = len(theme_threads)

    for t_idx, (theme, thread_ids) in enumerate(
        sorted(theme_threads.items(), key=lambda kv: len(kv[1]), reverse=True)
    ):
        print(f"  [{t_idx+1}/{total_themes}] {theme}: scoring {len(thread_ids)} threads...", file=sys.stderr)
        scored: list[tuple[int, dict]] = []
        for tid in thread_ids:
            card = score_thread(str(tid), memory, con, clusters, by_cluster, classifications)
            if "error" in card:
                continue
            rs = card["repo_scan"]
            unique = rs["blocks_unique"]
            res = card["kwic"]["resolution_hits"]
            frust = card["kwic"]["frustration_hits"]
            mining = unique * max(1, res)
            scored.append((mining, card))
        if not scored:
            continue
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_card = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else 0

        winners.append({
            "theme": theme,
            "member_count": len(thread_ids),
            "winner": {
                "convo_id": best_card["convo_id"],
                "title": best_card["title"],
                "date": best_card["date"],
                "total_blocks": best_card["code_blocks"]["count"],
                "unique_blocks": best_card["repo_scan"]["blocks_unique"],
                "in_repo": best_card["repo_scan"]["blocks_overlapping"],
                "resolution": best_card["kwic"]["resolution_hits"],
                "frustration": best_card["kwic"]["frustration_hits"],
                "mining_score": best_score,
                "languages": best_card["code_blocks"]["languages"],
                "last_user": best_card["excerpts"]["last_user"][:200],
                "last_assistant": best_card["excerpts"]["last_assistant"][:200],
            },
            "runner_up_score": second_score,
            "theme_imports": theme_imports.get(theme, {}),
            "suggested_repo": _suggest_repo_name(theme, best_card["title"]),
            "all_members": [
                {"convo_id": c["convo_id"], "title": c["title"],
                 "unique": c["repo_scan"]["blocks_unique"], "score": s}
                for s, c in scored[:5]
            ],
        })

    winners.sort(key=lambda w: w["winner"]["mining_score"], reverse=True)
    return winners


def print_table(winners: list[dict]) -> None:
    print(f"\n{'THEME':<22}{'WINNER':<8}{'TITLE':<40}{'UNIQ':<6}{'RES':<5}{'SCORE':<8}{'REPO NAME'}")
    print("-" * 130)
    for w in winners:
        win = w["winner"]
        title = (win["title"] or "?")[:38]
        print(f"{w['theme']:<22}#{win['convo_id']:<7}{title:<40}"
              f"{win['unique_blocks']:<6}{win['resolution']:<5}{win['mining_score']:<8}"
              f"{w['suggested_repo']}")


def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write winners to path")
    ap.add_argument("--cards", help="write full scored cards for each winner")
    args = ap.parse_args()

    if not THEMES_PATH.exists():
        print(f"run code_themes.py --json {THEMES_PATH.name} first", file=sys.stderr)
        return 1

    themes = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    theme_threads = {k: v for k, v in themes["theme_threads"].items()}
    theme_imports = themes.get("theme_imports", {})

    memory = load_memory()
    clusters_tuple = load_clusters()
    classifications = load_classifications()
    con = sqlite3.connect(str(DB_PATH))

    print(f"ranking winners across {len(theme_threads)} themes...", file=sys.stderr)
    winners = rank_theme_members(memory, clusters_tuple, classifications, con,
                                 theme_threads, theme_imports)
    print_table(winners)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "count": len(winners),
            "winners": winners,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)

    if args.cards:
        clusters, by_cluster = clusters_tuple
        ids = [w["winner"]["convo_id"] for w in winners]
        cards = [score_thread(cid, memory, con, clusters, by_cluster, classifications) for cid in ids]
        # Inject theme name into each card for display
        for card, w in zip(cards, winners):
            card["theme"] = w["theme"]
            card["suggested_repo"] = w["suggested_repo"]
            card["theme_member_count"] = w["member_count"]
        Path(args.cards).write_text(json.dumps({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "count": len(cards),
            "source": "theme_winners",
            "cards": cards,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.cards}", file=sys.stderr)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
idea_code_join — attach code signals + repo-presence to every idea in the registry.

Joins:
  idea_registry.json       → canonical_id, tier, priority_score, parent/child, category
  ideas_deduplicated.json  → version_timeline (convo_id per contributing convo)
  thread_scorer.score()    → per-convo code blocks, KWIC, repo-scan
  thread_decisions.json    → optional verdict overlay (if user already swiped)

Emits one rich card per idea, ordered by code_volume_score:
  code_volume_score = unique_blocks * max(1, resolution_hits)

No new clustering. No LLM calls. No mutation of idea_registry.json.

Usage:
  python idea_code_join.py                       # full run, ranked
  python idea_code_join.py --top 50 --json idea_code_join.json
  python idea_code_join.py --with-code-only      # skip ideas with 0 code blocks
  python idea_code_join.py --id canon_0042       # inspect one idea
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from thread_scorer import (
    BASE, DB_PATH, load_memory, load_clusters, load_classifications,
    score_thread, _fix_stdout
)

REGISTRY_PATH = BASE / "idea_registry.json"
DEDUP_PATH = BASE / "ideas_deduplicated.json"
DECISIONS_PATH = BASE / "thread_decisions.json"

# Repo directory → repo name (for "repo_exists" flagging)
# Mirrors REPO_SCAN_DIRS in thread_scorer; stays in sync because scorer imports here.
REPO_LABEL = "apps/code-converter"


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_dedup_timeline() -> dict[str, list[dict]]:
    """canonical_id -> list of {convo_id, convo_title, date, key_quote}."""
    d = json.loads(DEDUP_PATH.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for idea in d.get("ideas", []):
        cid = idea.get("canonical_id")
        if not cid:
            continue
        timeline = idea.get("version_timeline", [])
        out[cid] = [
            {
                "convo_id": str(entry.get("convo_id", "")),
                "convo_title": entry.get("convo_title", ""),
                "date": entry.get("date", ""),
                "key_quote": entry.get("key_quote", "")[:240],
            }
            for entry in timeline
            if entry.get("convo_id") is not None
        ]
    return out


def load_verdicts() -> dict[str, dict]:
    """convo_id -> {verdict, note, decided_at}."""
    if not DECISIONS_PATH.exists():
        return {}
    try:
        d = json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for row in d.get("decisions", []):
        cid = str(row.get("convo_id", ""))
        if cid:
            out[cid] = {
                "verdict": row.get("verdict"),
                "note": row.get("note", ""),
                "decided_at": row.get("decided_at"),
            }
    return out


def aggregate_signals(timeline: list[dict], memory, con, clusters, by_cluster,
                      classifications, verdicts: dict[str, dict],
                      score_cache: dict[str, dict]) -> dict:
    """Call thread_scorer per convo, accumulate signals into an idea-level summary."""
    enriched_timeline: list[dict] = []
    total_blocks = 0
    total_unique = 0
    total_overlap = 0
    total_res = 0
    total_frust = 0
    total_hedge = 0
    langs_combined: dict[str, int] = {}
    dates: list[str] = []
    repo_exists = False

    for entry in timeline:
        cid = entry["convo_id"]
        if not cid:
            continue
        # Deduplicate scorer calls — same convo may appear in many idea timelines.
        if cid not in score_cache:
            try:
                score_cache[cid] = score_thread(cid, memory, con, clusters, by_cluster, classifications)
            except Exception as e:
                score_cache[cid] = {"error": str(e), "convo_id": cid}
        card = score_cache[cid]
        if "error" in card:
            continue

        cb = card["code_blocks"]
        rs = card["repo_scan"]
        kw = card["kwic"]

        total_blocks += cb["count"]
        total_unique += rs["blocks_unique"]
        total_overlap += rs["blocks_overlapping"]
        total_res += kw["resolution_hits"]
        total_frust += kw["frustration_hits"]
        total_hedge += kw["hedge_hits"]
        if rs["blocks_overlapping"] > 0:
            repo_exists = True
        for lang, n in cb["languages"].items():
            langs_combined[lang] = langs_combined.get(lang, 0) + n
        if card.get("date"):
            dates.append(card["date"])

        verdict = verdicts.get(cid, {})
        enriched_timeline.append({
            "convo_id": cid,
            "title": entry.get("convo_title") or card.get("title"),
            "date": card.get("date") or entry.get("date"),
            "blocks": cb["count"],
            "unique": rs["blocks_unique"],
            "in_repo": rs["blocks_overlapping"],
            "resolution": kw["resolution_hits"],
            "frustration": kw["frustration_hits"],
            "cluster_id": card["cluster"]["cluster_id"],
            "verdict": verdict.get("verdict"),
            "note": verdict.get("note", ""),
            "key_quote": entry.get("key_quote", ""),
        })

    enriched_timeline.sort(key=lambda e: (e["date"] or "", e["convo_id"]))

    code_volume_score = total_unique * max(1, total_res)

    return {
        "convo_count": len(enriched_timeline),
        "total_blocks": total_blocks,
        "unique_blocks": total_unique,
        "in_repo": total_overlap,
        "resolution_hits": total_res,
        "frustration_hits": total_frust,
        "hedge_hits": total_hedge,
        "languages": dict(sorted(langs_combined.items(), key=lambda kv: -kv[1])[:8]),
        "date_first": min(dates) if dates else None,
        "date_last": max(dates) if dates else None,
        "repo_exists": repo_exists,
        "repo_path": REPO_LABEL if repo_exists else None,
        "code_volume_score": code_volume_score,
        "timeline": enriched_timeline,
    }


def build_cards(limit: int | None, with_code_only: bool, target_id: str | None) -> list[dict]:
    _fix_stdout()
    registry = load_registry()
    dedup = load_dedup_timeline()
    verdicts = load_verdicts()

    memory = load_memory()
    clusters, by_cluster = load_clusters()
    classifications = load_classifications()
    con = sqlite3.connect(str(DB_PATH))
    score_cache: dict[str, dict] = {}

    full = registry.get("full_registry", [])
    total = len(full)
    cards: list[dict] = []

    for i, idea in enumerate(full):
        cid = idea.get("canonical_id")
        if not cid:
            continue
        if target_id and cid != target_id:
            continue
        if i % 50 == 0:
            print(f"  joining {i}/{total}...", file=sys.stderr)

        timeline = dedup.get(cid, [])
        sig = aggregate_signals(timeline, memory, con, clusters, by_cluster,
                                classifications, verdicts, score_cache)

        if with_code_only and sig["total_blocks"] == 0:
            continue

        cards.append({
            "canonical_id": cid,
            "canonical_title": idea.get("canonical_title"),
            "category": idea.get("category"),
            "tier": idea.get("tier") or _tier_for(registry, cid),
            "priority_score": idea.get("priority_score"),
            "complexity": idea.get("complexity"),
            "status": idea.get("status"),
            "mention_count": idea.get("mention_count"),
            "alignment_score": idea.get("alignment_score"),
            "parent_idea": idea.get("parent_idea"),
            "child_ideas": idea.get("child_ideas", [])[:20],
            "related_ideas": idea.get("related_ideas", [])[:15],
            "dependencies": idea.get("dependencies", []),
            **sig,
        })

    con.close()
    cards.sort(key=lambda c: c["code_volume_score"], reverse=True)
    if limit:
        cards = cards[:limit]
    return cards


def _tier_for(registry: dict, canonical_id: str) -> str | None:
    for tier_name in ("execute_now", "next_up", "backlog", "archive"):
        for entry in registry.get("tiers", {}).get(tier_name, []):
            if entry.get("canonical_id") == canonical_id:
                return tier_name
    return None


def print_summary(cards: list[dict], limit: int = 20) -> None:
    print(f"\n{'rank':<5}{'id':<14}{'tier':<12}{'blocks':<8}{'uniq':<6}{'res':<5}{'score':<8}{'title'}")
    print("-" * 140)
    for i, c in enumerate(cards[:limit]):
        title = (c.get("canonical_title") or "?")[:60]
        print(f"{i+1:<5}{c['canonical_id']:<14}{(c.get('tier') or '-'):<12}"
              f"{c['total_blocks']:<8}{c['unique_blocks']:<6}{c['resolution_hits']:<5}"
              f"{c['code_volume_score']:<8}{title}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--with-code-only", action="store_true")
    ap.add_argument("--id", help="inspect one canonical_id")
    ap.add_argument("--json", help="write cards to this path")
    args = ap.parse_args()

    cards = build_cards(limit=None if args.id else args.top,
                        with_code_only=args.with_code_only,
                        target_id=args.id)

    if args.id:
        if not cards:
            print(f"{args.id}: not found", file=sys.stderr)
            return 1
        print(json.dumps(cards[0], ensure_ascii=False, indent=2))
    else:
        print_summary(cards, limit=args.top)
        print(f"\n{len(cards)} idea cards produced", file=sys.stderr)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "generated_at": datetime.now().isoformat(),
            "count": len(cards),
            "cards": cards,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

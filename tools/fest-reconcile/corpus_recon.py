#!/usr/bin/env python3
"""Part B - conversation corpus vs. portfolio reconciliation.

Cross-references the 6,534-conversation memory_db against portfolio_evidence.json
to emit three buckets:

  1. discussed AND shipped       - talk converged into artifact
  2. discussed but NOT shipped   - intent without execution
  3. shipped but NOT discussed   - execution outside the conversation channel

HOTL: heuristic only. Emits data + samples; doesn't assert "planning addiction."
Human reviews to decide what each bucket means.

Match strategy per portfolio item:
  - Word-boundary regex on item name (dashes preserved AND dashes->spaces).
  - Search corpus = title + first 10 messages truncated to 1000 chars each.
  - "Discussed" threshold: >= 1 conversation matches.

Inputs:
  - tools/fest-reconcile/portfolio_evidence.json (140 items)
  - services/cognitive-sensor/memory_db.json (6534 convos)

Outputs:
  - tools/fest-reconcile/conversation_artifact_reconciliation.json
  - tools/fest-reconcile/RECONCILIATION_REPORT.md
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
MEMORY_DB = REPO / "services" / "cognitive-sensor" / "memory_db.json"
PORTFOLIO = Path(__file__).parent / "portfolio_evidence.json"
JSON_OUT = Path(__file__).parent / "conversation_artifact_reconciliation.json"
MD_OUT = Path(__file__).parent / "RECONCILIATION_REPORT.md"

SHIPPED_BANDS = {"strong", "partial"}
NOT_SHIPPED_BANDS = {"stale", "none"}

GENERIC_TERMS = {
    "atlas", "core", "code", "ai", "api", "app", "apps", "tools", "tool",
    "test", "tests", "main", "src", "lib", "libs", "skill", "skills",
    "services", "common", "shared", "web", "main", "doc", "docs",
    "now", "next", "agent", "agents", "skill", "build", "ship",
    "mcp", "r3f",
}

MAX_MSGS_PER_CONVO = 10
MAX_CHARS_PER_MSG = 1000
MAX_SAMPLE_TITLES = 8


def is_ambiguous_name(name: str) -> bool:
    """A name is ambiguous if it's a single lowercase word with no structure.

    Examples:
      ambiguous: "weather", "perception", "thing", "downloads"
      not ambiguous: "mb3d-blender", "STRUDEL", "AnatomyV1", "delta_kernel"
    """
    nl = name.strip()
    if not nl:
        return True
    if any(c in nl for c in "-_") or any(c.isdigit() for c in nl):
        return False
    if nl != nl.lower():
        return False
    return True


@dataclass(frozen=True)
class MatchEvidence:
    convo_index: int
    title: str
    matched_terms: tuple[str, ...]


@dataclass
class ItemReconciliation:
    item: dict[str, Any]
    discussion_count: int = 0
    sample_titles: list[str] = field(default_factory=list)
    matched_terms_used: set[str] = field(default_factory=set)
    match_policy: str = "unambiguous"  # "unambiguous" | "title_only" | "skipped"


def name_variants(name: str) -> list[str]:
    """Yield distinct match terms for an item name.

    Includes the full name and (sometimes) a dashes/underscores->spaces form.
    The spaced variant is only emitted when every part of the name is >= 4
    chars - this kills false positives from generic phrases like 'my app',
    'my project', 'task manager'.
    """
    nl = name.lower().strip()
    if not nl or nl in GENERIC_TERMS or len(nl) < 4:
        return []
    out: set[str] = {nl}
    if "-" in nl or "_" in nl:
        parts = re.split(r"[-_]+", nl)
        if all(len(p) >= 4 for p in parts):
            spaced = " ".join(parts)
            if spaced not in GENERIC_TERMS:
                out.add(spaced)
    return sorted(out, key=len, reverse=True)


def build_convo_blob(convo: dict[str, Any]) -> str:
    parts: list[str] = [convo.get("title") or ""]
    for m in (convo.get("messages") or [])[:MAX_MSGS_PER_CONVO]:
        text = m.get("text") or ""
        parts.append(text[:MAX_CHARS_PER_MSG])
    return "\n".join(parts).lower()


def compile_patterns(variants: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    pats: list[tuple[str, re.Pattern[str]]] = []
    for v in variants:
        pats.append((v, re.compile(rf"(?<!\w){re.escape(v)}(?!\w)")))
    return pats


def reconcile(items: list[dict[str, Any]], convos: list[dict[str, Any]]) -> list[ItemReconciliation]:
    blobs = [build_convo_blob(c) for c in convos]
    titles_lower = [(c.get("title") or "").lower() for c in convos]
    titles_raw = [c.get("title") or "(no title)" for c in convos]
    results: list[ItemReconciliation] = []
    for it in items:
        variants = name_variants(it["name"])
        rec = ItemReconciliation(item=it)
        if not variants:
            rec.match_policy = "skipped"
            results.append(rec)
            continue
        ambiguous = is_ambiguous_name(it["name"])
        rec.match_policy = "title_only" if ambiguous else "unambiguous"
        patterns = compile_patterns(variants)
        for idx, blob in enumerate(blobs):
            target = titles_lower[idx] if ambiguous else blob
            hits = [v for v, pat in patterns if pat.search(target)]
            if hits:
                rec.discussion_count += 1
                rec.matched_terms_used.update(hits)
                if len(rec.sample_titles) < MAX_SAMPLE_TITLES:
                    rec.sample_titles.append(titles_raw[idx])
        results.append(rec)
    return results


def bucket(recs: list[ItemReconciliation]) -> dict[str, list[ItemReconciliation]]:
    out: dict[str, list[ItemReconciliation]] = {
        "discussed_and_shipped": [],
        "discussed_but_not_shipped": [],
        "shipped_but_not_discussed": [],
        "neither": [],
        "skipped_generic_name": [],
    }
    for r in recs:
        if r.match_policy == "skipped":
            out["skipped_generic_name"].append(r)
            continue
        band = r.item.get("signal_band") or "none"
        discussed = r.discussion_count > 0
        shipped = band in SHIPPED_BANDS
        if discussed and shipped:
            out["discussed_and_shipped"].append(r)
        elif discussed and not shipped:
            out["discussed_but_not_shipped"].append(r)
        elif not discussed and shipped:
            out["shipped_but_not_discussed"].append(r)
        else:
            out["neither"].append(r)
    return out


def rec_to_dict(r: ItemReconciliation) -> dict[str, Any]:
    return {
        "name": r.item["name"],
        "surface": r.item["surface"],
        "signal_band": r.item["signal_band"],
        "memory_index_mention": r.item.get("memory_mention"),
        "match_policy": r.match_policy,
        "discussion_count": r.discussion_count,
        "matched_terms_used": sorted(r.matched_terms_used),
        "sample_titles": r.sample_titles,
        "path": r.item.get("path"),
    }


def write_json(buckets: dict[str, list[ItemReconciliation]], stats: dict[str, Any]) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(),
        "method": {
            "match": "word-boundary regex on item name, plus dashes/underscores->spaces variant",
            "corpus_window": f"title + first {MAX_MSGS_PER_CONVO} messages, {MAX_CHARS_PER_MSG} chars each",
            "discussed_threshold": ">= 1 conversation",
            "generic_terms_skipped": sorted(GENERIC_TERMS),
        },
        "stats": stats,
        "buckets": {
            name: [rec_to_dict(r) for r in items]
            for name, items in buckets.items()
        },
    }
    JSON_OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def md_section(name: str, items: list[ItemReconciliation], limit: int = 10) -> str:
    lines = [f"### {name} ({len(items)})", ""]
    if not items:
        lines.append("_none_")
        lines.append("")
        return "\n".join(lines)
    sorted_items = sorted(items, key=lambda r: r.discussion_count, reverse=True)
    for r in sorted_items[:limit]:
        band = r.item["signal_band"]
        surf = r.item["surface"]
        n = r.discussion_count
        policy_tag = " [title-only]" if r.match_policy == "title_only" else ""
        lines.append(f"- **{r.item['name']}** ({surf}, band={band}, convos={n}){policy_tag}")
        if r.sample_titles:
            for t in r.sample_titles[:3]:
                t_clean = t.strip().replace("\n", " ")[:80]
                lines.append(f"  - `{t_clean}`")
    if len(items) > limit:
        lines.append(f"- _...and {len(items) - limit} more_")
    lines.append("")
    return "\n".join(lines)


def write_markdown(buckets: dict[str, list[ItemReconciliation]], stats: dict[str, Any]) -> None:
    lines = [
        "# Conversation x Portfolio Reconciliation",
        "",
        f"_Generated: {datetime.now().isoformat()}_",
        "",
        "**HOTL gate:** heuristic only. Numbers show match counts, not judgments.",
        "Human reviews each bucket to decide what the pattern means.",
        "",
        "## Corpus caveat (READ FIRST)",
        "",
        "`memory_db.json` is the **ChatGPT conversation export** (see",
        "`services/cognitive-sensor/index_chatgpt_exports.py`). It does **NOT** contain:",
        "",
        "- Claude Code session transcripts",
        "- `/weapon` autonomous runs",
        "- Codex CLI invocations",
        "- Direct shell / `gh` / `git` work outside chat",
        "",
        "So 'shipped but NOT discussed' means: shipped without showing up in the",
        "ChatGPT channel specifically. It does **not** mean undiscussed in any channel.",
        "This is the point - the ChatGPT corpus is one slice of total work.",
        "",
        "## Method",
        "",
        f"- Corpus: {stats['total_convos']} conversations from `memory_db.json`",
        f"- Portfolio: {stats['total_items']} items from `portfolio_evidence.json`",
        "- Match: word-boundary regex on item name + dashes/underscores->spaces variant",
        f"- Window per convo: title + first {MAX_MSGS_PER_CONVO} messages "
        f"({MAX_CHARS_PER_MSG} chars each)",
        "- Match policy:",
        "  - `unambiguous` (name has dash/digit/uppercase): search full window",
        "  - `title_only` (single lowercase word): search title only (FP control)",
        "  - `skipped` (in GENERIC_TERMS or < 4 chars): not measured",
        f"- Discussed threshold: >= 1 matching conversation",
        "",
        "## Top-line counts",
        "",
    ]
    for bucket_name in (
        "discussed_and_shipped",
        "discussed_but_not_shipped",
        "shipped_but_not_discussed",
        "neither",
        "skipped_generic_name",
    ):
        lines.append(f"- **{bucket_name}**: {len(buckets[bucket_name])}")
    lines.append("")
    lines.append("## The three buckets")
    lines.append("")
    lines.append("### Bucket 1 - discussed AND shipped")
    lines.append("Talk converged into artifact. Healthy signal.")
    lines.append("")
    lines.append(md_section("Items", buckets["discussed_and_shipped"], limit=15))
    lines.append("### Bucket 2 - discussed but NOT shipped")
    lines.append("Intent without execution. Potential planning-addiction signal,")
    lines.append("BUT could also be: deliberate research, killed projects, or rename drift.")
    lines.append("HOTL each one before concluding.")
    lines.append("")
    lines.append(md_section("Items", buckets["discussed_but_not_shipped"], limit=15))
    lines.append("### Bucket 3 - shipped but NOT in ChatGPT corpus")
    lines.append("Execution outside the ChatGPT channel. Many of these are real ships")
    lines.append("done through Claude Code / `/weapon` / autonomous runs - which the")
    lines.append("corpus doesn't index. Counter-narrative finding: chat-as-planning")
    lines.append("is a slice of total work, not the whole picture.")
    lines.append("")
    lines.append(md_section("Items", buckets["shipped_but_not_discussed"], limit=15))
    lines.append("### Bucket 4 - neither (no discussion, no ship)")
    lines.append("Likely abandoned starts or stub artifacts. Low signal.")
    lines.append("")
    lines.append(md_section("Items", buckets["neither"], limit=10))
    lines.append("### Skipped (generic name)")
    lines.append("Item names too generic to match safely (in GENERIC_TERMS or < 4 chars).")
    lines.append("Not counted as 'undiscussed' - just unmeasurable.")
    lines.append("")
    lines.append(md_section("Items", buckets["skipped_generic_name"], limit=10))
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("PART B - corpus x portfolio reconciliation\n")
    print(f"  Loading {MEMORY_DB.name}...")
    with MEMORY_DB.open(encoding="utf-8") as f:
        convos = json.load(f)
    print(f"  {len(convos)} conversations loaded")

    print(f"  Loading {PORTFOLIO.name}...")
    with PORTFOLIO.open(encoding="utf-8") as f:
        portfolio = json.load(f)
    items = portfolio.get("items", [])
    print(f"  {len(items)} portfolio items loaded\n")

    print("  Reconciling (140 items x 6534 convos)...")
    recs = reconcile(items, convos)
    print("  Done.")

    buckets = bucket(recs)
    stats = {
        "total_convos": len(convos),
        "total_items": len(items),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
    }

    write_json(buckets, stats)
    write_markdown(buckets, stats)

    print("\n  RESULTS")
    for name, lst in buckets.items():
        print(f"    {name:<32} {len(lst):>4}")
    print(f"\n  Wrote {JSON_OUT}")
    print(f"  Wrote {MD_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

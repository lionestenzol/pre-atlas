#!/usr/bin/env python3
"""Part B v2 - Claude Code transcripts vs. portfolio reconciliation.

The ChatGPT corpus (memory_db.json) misses where the actual ships happen.
This script scans ~1000 Claude Code session .jsonl files in
`~/.claude/projects/**/*.jsonl` instead.

Per session we extract:
  - first user message (acts like a 'title')
  - all user messages + assistant text blocks (the 'body')
  - cwd, gitBranch, startedAt

Then same matcher logic as corpus_recon.py:
  - unambiguous names (dash/digit/uppercase): match full body
  - ambiguous names (single lowercase word): match first-user-message only

Outputs:
  - tools/fest-reconcile/cc_conversation_artifact_reconciliation.json
  - tools/fest-reconcile/CC_RECONCILIATION_REPORT.md
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

REPO = Path(__file__).resolve().parents[2]
CC_PROJECTS = Path(os.path.expanduser("~")) / ".claude" / "projects"
PORTFOLIO = Path(__file__).parent / "portfolio_evidence.json"
JSON_OUT = Path(__file__).parent / "cc_conversation_artifact_reconciliation.json"
MD_OUT = Path(__file__).parent / "CC_RECONCILIATION_REPORT.md"

SHIPPED_BANDS = {"strong", "partial"}

GENERIC_TERMS = {
    "atlas", "core", "code", "ai", "api", "app", "apps", "tools", "tool",
    "test", "tests", "main", "src", "lib", "libs", "skill", "skills",
    "services", "common", "shared", "web", "main", "doc", "docs",
    "now", "next", "agent", "agents", "skill", "build", "ship",
    "mcp", "r3f",
}

MAX_BLOB_CHARS = 50_000
MAX_FIRST_MSG_CHARS = 2_000
MAX_SAMPLE_SESSIONS = 8


@dataclass(frozen=True)
class Session:
    id: str
    project_dir: str   # the C--Users-... slug
    cwd: str
    git_branch: str
    started_at: str
    first_user_msg: str   # truncated, used as 'title' analog
    text_blob: str        # lowercased, truncated


@dataclass
class ItemReconciliation:
    item: dict[str, Any]
    discussion_count: int = 0
    sample_first_msgs: list[str] = field(default_factory=list)
    matched_terms_used: set[str] = field(default_factory=set)
    match_policy: str = "unambiguous"


def is_ambiguous_name(name: str) -> bool:
    nl = name.strip()
    if not nl:
        return True
    if any(c in nl for c in "-_") or any(c.isdigit() for c in nl):
        return False
    if nl != nl.lower():
        return False
    return True


def name_variants(name: str) -> list[str]:
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


def extract_text_from_content(content: Any) -> str:
    """Extract user-visible text from Claude Code's content shape.

    - str: return as-is
    - list of blocks: keep text blocks; skip tool_use, thinking, tool_result
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")
            if btype == "text":
                parts.append(b.get("text") or "")
            elif btype == "tool_use":
                # skip args - they are search terms, file paths, etc., not real talk
                pass
            elif btype == "thinking":
                # skip - encrypted/internal
                pass
            elif btype == "tool_result":
                # skip - command output
                pass
        return "\n".join(parts)
    return ""


def load_session(jsonl: Path) -> Session | None:
    cwd = ""
    git_branch = ""
    started_at = ""
    first_user_msg = ""
    blob_parts: list[str] = []
    blob_len = 0
    try:
        with jsonl.open(encoding="utf-8") as f:
            for line in f:
                if blob_len >= MAX_BLOB_CHARS:
                    break
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if not cwd and d.get("cwd"):
                    cwd = d["cwd"]
                if not git_branch and d.get("gitBranch"):
                    git_branch = d["gitBranch"]
                if not started_at and d.get("timestamp"):
                    started_at = d["timestamp"]
                if t in ("user", "assistant"):
                    msg = d.get("message") or {}
                    if not isinstance(msg, dict):
                        continue
                    text = extract_text_from_content(msg.get("content"))
                    if not text:
                        continue
                    if t == "user" and not first_user_msg:
                        first_user_msg = text[:MAX_FIRST_MSG_CHARS]
                    take = text[: MAX_BLOB_CHARS - blob_len]
                    blob_parts.append(take)
                    blob_len += len(take)
    except OSError:
        return None
    if not blob_parts and not first_user_msg:
        return None
    return Session(
        id=jsonl.stem,
        project_dir=jsonl.parent.name,
        cwd=cwd,
        git_branch=git_branch,
        started_at=started_at,
        first_user_msg=first_user_msg,
        text_blob="\n".join(blob_parts).lower(),
    )


def iter_sessions() -> Iterator[Session]:
    for jsonl in CC_PROJECTS.rglob("*.jsonl"):
        s = load_session(jsonl)
        if s is not None:
            yield s


def compile_patterns(variants: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [(v, re.compile(rf"(?<!\w){re.escape(v)}(?!\w)")) for v in variants]


def reconcile(items: list[dict[str, Any]], sessions: list[Session]) -> list[ItemReconciliation]:
    first_msgs_lower = [s.first_user_msg.lower() for s in sessions]
    first_msgs_raw = [s.first_user_msg for s in sessions]
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
        for idx, s in enumerate(sessions):
            target = first_msgs_lower[idx] if ambiguous else s.text_blob
            hits = [v for v, pat in patterns if pat.search(target)]
            if hits:
                rec.discussion_count += 1
                rec.matched_terms_used.update(hits)
                if len(rec.sample_first_msgs) < MAX_SAMPLE_SESSIONS:
                    snippet = first_msgs_raw[idx].strip().replace("\n", " ")[:120]
                    rec.sample_first_msgs.append(snippet)
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
        "sample_first_msgs": r.sample_first_msgs,
        "path": r.item.get("path"),
    }


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
        policy_tag = " [first-msg-only]" if r.match_policy == "title_only" else ""
        lines.append(f"- **{r.item['name']}** ({surf}, band={band}, sessions={n}){policy_tag}")
        for snip in r.sample_first_msgs[:3]:
            lines.append(f"  - `{snip}`")
    if len(items) > limit:
        lines.append(f"- _...and {len(items) - limit} more_")
    lines.append("")
    return "\n".join(lines)


def write_outputs(buckets: dict[str, list[ItemReconciliation]], stats: dict[str, Any]) -> None:
    JSON_OUT.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "corpus": "claude_code_session_jsonl_under_~/.claude/projects/**",
            "stats": stats,
            "buckets": {k: [rec_to_dict(r) for r in v] for k, v in buckets.items()},
        }, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Claude Code corpus x Portfolio Reconciliation (Part B v2)",
        "",
        f"_Generated: {datetime.now().isoformat()}_",
        "",
        "**HOTL gate:** heuristic only. Numbers show match counts, not judgments.",
        "",
        "## Corpus",
        "",
        f"- {stats['total_sessions']} Claude Code session `.jsonl` files",
        "  under `~/.claude/projects/**`",
        "- Per session: extracted first user message + all user/assistant text "
        "(skipped tool_use/thinking/tool_result blocks)",
        f"- Body cap per session: {MAX_BLOB_CHARS:,} chars",
        f"- Portfolio: {stats['total_items']} items from `portfolio_evidence.json`",
        "",
        "## Method",
        "",
        "Same as `corpus_recon.py` (ChatGPT export sidecar):",
        "- `unambiguous` (name has dash/digit/uppercase): search full session body",
        "- `title_only` (single lowercase word): search first user message only "
        "(FP control - 'cortex' could mean prefrontal cortex)",
        "- `skipped` (in GENERIC_TERMS or < 4 chars): not measured",
        "",
        "## Top-line counts",
        "",
    ]
    for bn in (
        "discussed_and_shipped",
        "discussed_but_not_shipped",
        "shipped_but_not_discussed",
        "neither",
        "skipped_generic_name",
    ):
        lines.append(f"- **{bn}**: {len(buckets[bn])}")
    lines.append("")
    lines.append("## Buckets")
    lines.append("")
    lines.append("### Bucket 1 - discussed AND shipped")
    lines.append("Talk in Claude Code converged into artifact.")
    lines.append("")
    lines.append(md_section("Items", buckets["discussed_and_shipped"], limit=20))
    lines.append("### Bucket 2 - discussed but NOT shipped")
    lines.append("Talked about in Claude Code; band=stale/none. Could be:")
    lines.append("planning that didn't materialize, killed projects, or rename drift.")
    lines.append("")
    lines.append(md_section("Items", buckets["discussed_but_not_shipped"], limit=20))
    lines.append("### Bucket 3 - shipped but NOT discussed in Claude Code")
    lines.append("Shipped, but no Claude Code session matched. Could be:")
    lines.append("- Shipped purely via shell / `gh` / `git` outside Claude Code")
    lines.append("- Shipped via `/weapon` runs (still in jsonl, should match if name is in prompt)")
    lines.append("- Ambiguous-name FP filter hid the discussion (try grep)")
    lines.append("- Cloned/vendored repos with no original discussion")
    lines.append("")
    lines.append(md_section("Items", buckets["shipped_but_not_discussed"], limit=20))
    lines.append("### Bucket 4 - neither")
    lines.append("Low signal: no Claude Code discussion AND no strong ship evidence.")
    lines.append("")
    lines.append(md_section("Items", buckets["neither"], limit=15))
    lines.append("### Skipped (generic name)")
    lines.append("")
    lines.append(md_section("Items", buckets["skipped_generic_name"], limit=10))

    MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("PART B v2 - Claude Code corpus x portfolio reconciliation\n")

    print(f"  Loading {PORTFOLIO.name}...")
    with PORTFOLIO.open(encoding="utf-8") as f:
        portfolio = json.load(f)
    items = portfolio.get("items", [])
    print(f"  {len(items)} portfolio items loaded\n")

    print(f"  Scanning Claude Code sessions in {CC_PROJECTS}...")
    sessions: list[Session] = []
    for s in iter_sessions():
        sessions.append(s)
        if len(sessions) % 100 == 0:
            print(f"    ... {len(sessions)} sessions loaded")
    print(f"  {len(sessions)} sessions loaded\n")

    project_dirs = Counter(s.project_dir for s in sessions)
    print(f"  Sessions span {len(project_dirs)} project directories")
    print(f"  Top 5 project dirs by session count:")
    for pd, n in project_dirs.most_common(5):
        print(f"    {n:>4}  {pd}")
    print()

    print("  Reconciling...")
    recs = reconcile(items, sessions)
    print("  Done.\n")

    buckets = bucket(recs)
    stats = {
        "total_sessions": len(sessions),
        "total_items": len(items),
        "project_dirs": len(project_dirs),
        "bucket_counts": {k: len(v) for k, v in buckets.items()},
    }
    write_outputs(buckets, stats)

    print("  RESULTS")
    for name, lst in buckets.items():
        print(f"    {name:<32} {len(lst):>4}")
    print(f"\n  Wrote {JSON_OUT}")
    print(f"  Wrote {MD_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

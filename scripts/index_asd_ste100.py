"""Index memory files for ASD-STE100 non-conformances.

Runs one pass over every .md file in the memory folder. Counts banned
patterns and long sentences. Skips fenced code blocks. Emits JSON plus a
markdown summary. Zero LLM cost.

Usage:
    python scripts/index_asd_ste100.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-bruke-Pre-Atlas" / "memory"
OUT_JSON = Path("scripts/asd_ste100_index.json")
OUT_MD = Path("scripts/asd_ste100_index.md")

BANNED_WORDS = [
    "utilize", "utilise", "utilizes", "utilized", "utilization",
    "prior to", "subsequent to", "in order to", "with regard to",
    "commence", "commences", "commenced", "commencing",
    "terminate", "terminates", "terminated", "terminating",
    "attempt", "attempts", "attempted", "attempting",
    "assist", "assists", "assisted", "assisting",
    "perform", "performs", "performed", "performing",
    "endeavor", "endeavour",
    "just", "really", "actually", "basically",
    "sort of", "kind of",
    "obviously", "clearly", "simply",
]

PUNCT_PATTERNS = {
    "em_dash": r"—",
    "en_dash": r"–",
    "ellipsis_unicode": r"…",
    "ellipsis_ascii": r"\.\.\.",
    "double_hyphen": r"(?<!-)--(?!-)",
}

CODE_FENCE = re.compile(r"^```")
QUOTE_LINE = re.compile(r"^\s*>")
YAML_FENCE = re.compile(r"^---\s*$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")


def strip_fenced(text: str) -> tuple[str, list[str]]:
    """Return prose text and a list of skipped fenced blocks."""
    lines = text.splitlines()
    out_lines: list[str] = []
    skipped: list[str] = []
    in_code = False
    in_yaml = False
    for i, line in enumerate(lines):
        if i == 0 and YAML_FENCE.match(line):
            in_yaml = True
            skipped.append(line)
            continue
        if in_yaml:
            skipped.append(line)
            if YAML_FENCE.match(line):
                in_yaml = False
            continue
        if CODE_FENCE.match(line):
            in_code = not in_code
            skipped.append(line)
            continue
        if in_code:
            skipped.append(line)
            continue
        out_lines.append(line)
    return "\n".join(out_lines), skipped


def find_long_sentences(prose: str, min_words: int = 25) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for sentence in SENTENCE_SPLIT.split(prose):
        sentence = sentence.strip()
        if not sentence or sentence.startswith("#") or sentence.startswith("|"):
            continue
        word_count = len(re.findall(r"\S+", sentence))
        if word_count >= min_words:
            hits.append((word_count, sentence[:200]))
    hits.sort(reverse=True)
    return hits


def find_gerund_nouns(prose: str) -> list[str]:
    """Find likely gerund-as-noun uses. Heuristic only."""
    pattern = re.compile(
        r"\b(the|by|for|of|after|before|without|through)\s+(\w+ing)\b",
        re.IGNORECASE,
    )
    return [f"{m.group(1)} {m.group(2)}" for m in pattern.finditer(prose)]


def count_banned(prose: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    lower = prose.lower()
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        n = len(re.findall(pattern, lower))
        if n:
            counts[word] = n
    return counts


def count_quote_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if QUOTE_LINE.match(line))


def scan_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    prose, skipped = strip_fenced(raw)
    punct = {name: len(re.findall(pat, prose)) for name, pat in PUNCT_PATTERNS.items()}
    banned = count_banned(prose)
    long_sents = find_long_sentences(prose)
    gerund = find_gerund_nouns(prose)
    return {
        "file": path.name,
        "bytes": len(raw.encode("utf-8")),
        "lines": len(raw.splitlines()),
        "skipped_lines": len(skipped),
        "quote_lines": count_quote_lines(raw),
        "punct": punct,
        "banned": dict(banned),
        "long_sentence_count": len(long_sents),
        "top_long_sentences": long_sents[:3],
        "gerund_noun_hits": gerund[:10],
        "gerund_noun_count": len(gerund),
    }


def main() -> None:
    files = sorted(MEMORY_DIR.glob("*.md"))
    if not files:
        raise SystemExit(f"No .md files found in {MEMORY_DIR}")

    reports = [scan_file(f) for f in files]

    totals: dict[str, int] = {
        "files": len(reports),
        "bytes": sum(r["bytes"] for r in reports),
        "long_sentences": sum(r["long_sentence_count"] for r in reports),
        "gerund_nouns": sum(r["gerund_noun_count"] for r in reports),
    }
    punct_totals: Counter[str] = Counter()
    banned_totals: Counter[str] = Counter()
    for r in reports:
        for k, v in r["punct"].items():
            punct_totals[k] += v
        for k, v in r["banned"].items():
            banned_totals[k] += v

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "totals": totals,
                "punct_totals": dict(punct_totals),
                "banned_totals": dict(banned_totals),
                "files": reports,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines: list[str] = []
    lines.append("# ASD-STE100 Index Report")
    lines.append("")
    lines.append(f"Scanned {totals['files']} files. Total size {totals['bytes']:,} bytes.")
    lines.append("")
    lines.append("## Punctuation totals")
    for k, v in sorted(punct_totals.items(), key=lambda x: -x[1]):
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Banned word totals")
    for k, v in sorted(banned_totals.items(), key=lambda x: -x[1]):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append(f"## Long sentences: {totals['long_sentences']} total over all files")
    lines.append(f"## Gerund-as-noun hits: {totals['gerund_nouns']} total")
    lines.append("")
    lines.append("## Top 20 files by long-sentence count")
    top = sorted(reports, key=lambda r: -r["long_sentence_count"])[:20]
    for r in top:
        lines.append(f"- {r['file']}: {r['long_sentence_count']} long sentences, {r['bytes']:,} bytes")
    lines.append("")
    lines.append("## Top 20 files by em-dash count")
    top_em = sorted(reports, key=lambda r: -r["punct"]["em_dash"])[:20]
    for r in top_em:
        lines.append(f"- {r['file']}: {r['punct']['em_dash']} em dashes")
    lines.append("")
    lines.append("## Top 20 files by quote-line count")
    top_q = sorted(reports, key=lambda r: -r["quote_lines"])[:20]
    for r in top_q:
        if r["quote_lines"] == 0:
            break
        lines.append(f"- {r['file']}: {r['quote_lines']} quote lines")

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_JSON} and {OUT_MD}")
    print(f"Files: {totals['files']}  Bytes: {totals['bytes']:,}")
    print(f"Em dashes: {punct_totals['em_dash']}  Long sentences: {totals['long_sentences']}")


if __name__ == "__main__":
    main()

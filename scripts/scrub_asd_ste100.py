"""Scrub memory files to move them closer to ASD-STE100.

Deterministic transforms only. No LLM. Reversible via the backup folder.

Default mode is dry-run. Pass --apply to write files. Every edit is logged
to scripts/asd_ste100_scrub_manifest.jsonl for audit.

Skips:
- YAML frontmatter block at the top of a file.
- Fenced code blocks (``` ... ```).
- Inline code spans (`...`).
- Quote lines that start with `>` (preserves origin quotes).
- URLs and paths.

Transforms:
- Em dash `—` between words: replaced with `. ` and next word capitalized.
- En dash `–`: replaced with `-`.
- Spaced double hyphen ` -- `: replaced with ` - `. Preserves CLI flags.
- Ellipsis `...` and `…`: replaced with `.`.
- Banned words (case-insensitive, word-boundary): substituted or deleted.

Usage:
    python scripts/scrub_asd_ste100.py                      # dry-run all files
    python scripts/scrub_asd_ste100.py --file MEMORY.md     # dry-run one file
    python scripts/scrub_asd_ste100.py --apply              # write files
    python scripts/scrub_asd_ste100.py --apply --file X.md  # write one file
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--Users-bruke-Pre-Atlas" / "memory"
MANIFEST = Path("scripts/asd_ste100_scrub_manifest.jsonl")

SKIP_FILES = {
    "feedback_asd_ste100_output_mode.md",
    "feedback_no_em_dashes_in_ui.md",
}

# Banned words. Value None means delete the word (plus one leading space).
# Otherwise the value is the replacement.
BANNED: dict[str, str | None] = {
    r"\bjust\b": None,
    r"\bactually\b": None,
    r"\breally\b": None,
    r"\bbasically\b": None,
    r"\bsimply\b": None,
    r"\bobviously\b": None,
    r"\bclearly\b": None,
    r"\bsort of\b": None,
    r"\bkind of\b": None,
    r"\butilize\b": "use",
    r"\butilise\b": "use",
    r"\butilizes\b": "uses",
    r"\butilises\b": "uses",
    r"\butilized\b": "used",
    r"\butilised\b": "used",
    r"\butilization\b": "use",
    r"\bprior to\b": "before",
    r"\bsubsequent to\b": "after",
    r"\bin order to\b": "to",
    r"\bwith regard to\b": "about",
    r"\bcommence\b": "start",
    r"\bcommences\b": "starts",
    r"\bcommenced\b": "started",
    r"\bcommencing\b": "starting",
    r"\bterminate\b": "end",
    r"\bterminates\b": "ends",
    r"\bterminated\b": "ended",
    r"\bterminating\b": "ending",
    r"\battempt\b": "try",
    r"\battempts\b": "tries",
    r"\battempted\b": "tried",
    r"\battempting\b": "trying",
    r"\bassist\b": "help",
    r"\bassists\b": "helps",
    r"\bassisted\b": "helped",
    r"\bassisting\b": "helping",
    r"\bendeavor\b": "try",
    r"\bendeavour\b": "try",
    r"\bendeavors\b": "tries",
    r"\bendeavours\b": "tries",
}


@dataclass
class Edit:
    kind: str
    line_no: int
    before: str
    after: str


@dataclass
class FileReport:
    file: str
    edits: list[Edit] = field(default_factory=list)
    output: str = ""


CODE_FENCE = re.compile(r"^```")
YAML_FENCE = re.compile(r"^---\s*$")
QUOTE_LINE = re.compile(r"^\s*>")


def split_inline_code(line: str) -> list[tuple[bool, str]]:
    """Split a line into (is_code, chunk) parts around backtick spans."""
    parts: list[tuple[bool, str]] = []
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "`":
            end = line.find("`", i + 1)
            if end == -1:
                parts.append((False, line[i:]))
                return parts
            parts.append((True, line[i : end + 1]))
            i = end + 1
        else:
            j = line.find("`", i)
            if j == -1:
                parts.append((False, line[i:]))
                return parts
            parts.append((False, line[i:j]))
            i = j
    return parts


def transform_em_dash(text: str, edits: list[Edit], line_no: int) -> str:
    def replace(match: re.Match) -> str:
        before = match.group(0)
        left, right = match.group(1), match.group(2)
        if right and right[0].isalpha():
            new_right = right[0].upper() + right[1:]
        else:
            new_right = right
        result = f"{left}. {new_right}"
        edits.append(Edit("em_dash", line_no, before, result))
        return result

    return re.sub(r"(\S)\s*—\s*(\S)", replace, text)


def transform_en_dash(text: str, edits: list[Edit], line_no: int) -> str:
    def replace(match: re.Match) -> str:
        before = match.group(0)
        after = before.replace("–", "-")
        edits.append(Edit("en_dash", line_no, before, after))
        return after

    return re.sub(r"–", replace, text)


def transform_double_hyphen(text: str, edits: list[Edit], line_no: int) -> str:
    def replace(match: re.Match) -> str:
        before = match.group(0)
        after = " - "
        edits.append(Edit("double_hyphen", line_no, before, after))
        return after

    return re.sub(r" -- ", replace, text)


def transform_ellipsis(text: str, edits: list[Edit], line_no: int) -> str:
    def replace_uni(match: re.Match) -> str:
        edits.append(Edit("ellipsis_uni", line_no, "…", "."))
        return "."

    def replace_ascii(match: re.Match) -> str:
        edits.append(Edit("ellipsis_ascii", line_no, "...", "."))
        return "."

    text = re.sub(r"…", replace_uni, text)
    text = re.sub(r"\.\.\.", replace_ascii, text)
    return text


def transform_banned(text: str, edits: list[Edit], line_no: int) -> str:
    for pattern, replacement in BANNED.items():
        def make_replace(pat: str, rep: str | None):
            def replace(match: re.Match) -> str:
                before = match.group(0)
                if rep is None:
                    edits.append(Edit(f"delete:{pat}", line_no, before, ""))
                    return ""
                if before[0].isupper():
                    new = rep[0].upper() + rep[1:]
                else:
                    new = rep
                edits.append(Edit(f"swap:{pat}", line_no, before, new))
                return new

            return replace

        text = re.sub(pattern, make_replace(pattern, replacement), text, flags=re.IGNORECASE)
    text = re.sub(r"  +", " ", text)
    return text


def mask_inline_code(line: str) -> tuple[str, list[str]]:
    """Replace `...` spans with placeholders. Return masked line and the spans."""
    spans: list[str] = []

    def replace(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"\x00CODE{len(spans) - 1}\x00"

    masked = re.sub(r"`[^`]*`", replace, line)
    return masked, spans


def unmask_inline_code(text: str, spans: list[str]) -> str:
    for i, span in enumerate(spans):
        text = text.replace(f"\x00CODE{i}\x00", span)
    return text


def scrub_line(line: str, edits: list[Edit], line_no: int) -> str:
    masked, spans = mask_inline_code(line)
    masked = transform_em_dash(masked, edits, line_no)
    masked = transform_en_dash(masked, edits, line_no)
    masked = transform_double_hyphen(masked, edits, line_no)
    masked = transform_ellipsis(masked, edits, line_no)
    masked = transform_banned(masked, edits, line_no)
    return unmask_inline_code(masked, spans)


def scrub_file(path: Path) -> FileReport:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines(keepends=True)
    report = FileReport(file=path.name)

    in_code = False
    in_yaml = False
    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        stripped = line.rstrip("\r\n")
        newline = line[len(stripped):]

        if i == 1 and YAML_FENCE.match(stripped):
            in_yaml = True
            out.append(line)
            continue
        if in_yaml:
            out.append(line)
            if YAML_FENCE.match(stripped):
                in_yaml = False
            continue
        if CODE_FENCE.match(stripped):
            in_code = not in_code
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue
        if QUOTE_LINE.match(stripped):
            out.append(line)
            continue

        new_body = scrub_line(stripped, report.edits, i)
        out.append(new_body + newline)

    report.output = "".join(out)
    return report


def write_manifest(reports: list[FileReport]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", encoding="utf-8") as f:
        for r in reports:
            for e in r.edits:
                row = {
                    "file": r.file,
                    "line": e.line_no,
                    "kind": e.kind,
                    "before": e.before,
                    "after": e.after,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(reports: list[FileReport]) -> None:
    total_edits = sum(len(r.edits) for r in reports)
    by_kind: dict[str, int] = {}
    for r in reports:
        for e in r.edits:
            key = e.kind.split(":", 1)[0]
            by_kind[key] = by_kind.get(key, 0) + 1
    print(f"Files scanned: {len(reports)}")
    print(f"Total edits: {total_edits}")
    print("By kind:")
    for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    top = sorted(reports, key=lambda r: -len(r.edits))[:10]
    print("Top 10 files by edit count:")
    for r in top:
        print(f"  {r.file}: {len(r.edits)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write files. Default is dry-run.")
    parser.add_argument("--file", type=str, help="Scrub only this filename.")
    args = parser.parse_args()

    if args.file:
        target = MEMORY_DIR / args.file
        if not target.exists():
            print(f"Not found: {target}")
            return 1
        files = [target]
    else:
        files = [f for f in sorted(MEMORY_DIR.glob("*.md")) if f.name not in SKIP_FILES]
        skipped = sorted(SKIP_FILES)
        if skipped:
            print(f"Skipped {len(skipped)} doctrine files:")
            for name in skipped:
                print(f"  {name}")

    reports = [scrub_file(f) for f in files]
    write_manifest(reports)

    if args.apply:
        for path, report in zip(files, reports):
            path.write_text(report.output, encoding="utf-8")
        print(f"APPLIED to {len(files)} files")
    else:
        print("DRY-RUN. No files written. Manifest at:", MANIFEST)

    summarize(reports)
    return 0


if __name__ == "__main__":
    sys.exit(main())

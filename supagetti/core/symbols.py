"""
Phase 4 (scan) symbol extraction. No LLM calls in this file, ever.

Ported from services/delta-scp/src/compressor.ts — same INCLUDE_EXT
allowlist, same per-language regex patterns, same one-symbol-per-line-first-
match logic, same token-yield math. Kept in lockstep with that file
deliberately: this is the deterministic core the scan phase should never
need an LLM for.

Symbol extraction is heuristic (lightweight per-language regexes, not a full
AST). It is intentionally cheap and language-agnostic; it favours breadth
and determinism over perfect parsing.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from core.models import SymbolEntry, SymbolicCompression, SymbolicNode

# Extensions worth scanning for structure — mirrors delta-scp's source.ts
# INCLUDE_EXT. Everything else (images, binaries, lockfiles, archives) is
# skipped for symbol extraction; scan.json's own file_count/extension_counts
# still cover every file regardless.
INCLUDE_EXT = {
    "ts", "tsx", "js", "jsx", "mjs", "cjs",
    "py", "go", "rs", "java", "rb", "php",
    "c", "h", "cpp", "hpp", "cs", "swift", "kt",
    "sql", "sh", "md", "json", "yaml", "yml", "toml",
}

EXT_LANGUAGE = {
    "ts": "typescript", "tsx": "typescript", "js": "javascript", "jsx": "javascript",
    "mjs": "javascript", "cjs": "javascript", "py": "python", "go": "go", "rs": "rust",
    "java": "java", "rb": "ruby", "php": "php", "c": "c", "h": "c", "cpp": "cpp",
    "hpp": "cpp", "cs": "csharp", "swift": "swift", "kt": "kotlin", "sql": "sql",
    "sh": "shell", "md": "markdown", "json": "json", "yaml": "yaml", "yml": "yaml",
    "toml": "toml",
}


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def language_for_path(path: str) -> str:
    return EXT_LANGUAGE.get(_ext(path), "other")


def include_file(name: str) -> bool:
    return _ext(name) in INCLUDE_EXT


# Per-language symbol patterns. One regex per line, first match wins — a
# direct port of compressor.ts's SYMBOL_PATTERNS.
_SYMBOL_PATTERNS: dict[str, list[tuple[str, re.Pattern]]] = {
    "typescript": [
        ("class", re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)")),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")),
        ("const", re.compile(r"^\s*export\s+const\s+([A-Za-z_$][\w$]*)")),
        ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+([A-Za-z_$][\w$]*)")),
    ],
    "python": [
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
        ("def", re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)")),
    ],
    "go": [
        ("func", re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")),
        ("type", re.compile(r"^\s*type\s+([A-Za-z_]\w*)")),
    ],
    "rust": [
        ("fn", re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)")),
        ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)")),
        ("enum", re.compile(r"^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)")),
        ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)")),
    ],
    "ruby": [
        ("class", re.compile(r"^\s*class\s+([A-Za-z_]\w*)")),
        ("def", re.compile(r"^\s*def\s+([A-Za-z_][\w?!]*)")),
    ],
    "java": [
        ("class", re.compile(
            r"^\s*(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+)*class\s+([A-Za-z_]\w*)"
        )),
        ("interface", re.compile(r"^\s*(?:public\s+|private\s+)?interface\s+([A-Za-z_]\w*)")),
    ],
}
_SYMBOL_PATTERNS["javascript"] = _SYMBOL_PATTERNS["typescript"]


def estimate_tokens(text: str) -> int:
    """~4 chars/token. A yield estimate, not a real tokenizer — matches compressor.ts."""
    return math.ceil(len(text) / 4)


def extract_symbols(content: str, language: str) -> list[SymbolEntry]:
    patterns = _SYMBOL_PATTERNS.get(language)
    if not patterns:
        return []
    symbols: list[SymbolEntry] = []
    for i, line in enumerate(content.split("\n"), start=1):
        for kind, pattern in patterns:
            m = pattern.match(line)
            if m:
                symbols.append(SymbolEntry(kind=kind, name=m.group(1), line=i))
                break  # one symbol kind per line
    return symbols


def compress_tree(source_dir: Path, rel_paths: list[str], warnings: list[str]) -> SymbolicCompression:
    """
    Given repo-relative paths already filtered by include_file(), read each
    from disk, extract symbols, and report the estimated token yield.
    Mirrors compressTree() in compressor.ts. Unlike the TS version (which
    receives file bytes already in memory from a GitHub fetch), this reads
    from local disk — I/O or decode errors are recorded as scan warnings and
    the file is skipped, never raised.
    """
    symbolic_nodes: list[SymbolicNode] = []
    raw_tokens = 0

    for rel_path in sorted(rel_paths):
        try:
            content = (source_dir / rel_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(f"Symbol extraction skipped unreadable file: {rel_path} ({exc})")
            continue

        language = language_for_path(rel_path)
        tokens_est = estimate_tokens(content)
        raw_tokens += tokens_est
        symbolic_nodes.append(
            SymbolicNode(
                path=rel_path.replace("\\", "/"),
                language=language,
                bytes=len(content.encode("utf-8")),
                tokens_est=tokens_est,
                symbols=extract_symbols(content, language),
            )
        )

    body = {"symbolic_nodes": [n.model_dump() for n in symbolic_nodes]}
    compressed_tokens = estimate_tokens(json.dumps(body))
    token_yield = raw_tokens - compressed_tokens
    ratio = math.floor((compressed_tokens / raw_tokens) * 10000 + 0.5) / 10000 if raw_tokens > 0 else 0.0

    return SymbolicCompression(
        files_included=len(symbolic_nodes),
        raw_tokens_est=raw_tokens,
        compressed_tokens_est=compressed_tokens,
        token_yield=token_yield,
        compression_ratio=ratio,
        symbolic_nodes=symbolic_nodes,
    )

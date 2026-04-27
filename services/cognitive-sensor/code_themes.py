"""
code_themes — group all code blocks across all conversations by what they DO.

Extracts imports + function/class names from every code block and groups threads
by shared signatures. Reveals "projects you've been trying to build" without
needing to read or decide on anything.

Output:
  themes.json  → { theme_name: { threads: [...], block_count, example_imports } }

Usage:
  python code_themes.py                 # print themes + thread lists
  python code_themes.py --json themes.json
  python code_themes.py --theme pdf     # show threads matching a theme
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()
MEMORY_PATH = BASE / "memory_db.json"

CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
IMPORT_PY = re.compile(r"^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", re.MULTILINE)
DEF_PY = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z_][\w]*)", re.MULTILINE)
CLASS_PY = re.compile(r"^\s*class\s+([A-Z][\w]*)", re.MULTILINE)

# Theme definitions — keywords/imports that indicate a project type.
# Order matters — earlier themes win when a block matches multiple.
THEMES: list[tuple[str, set[str]]] = [
    ("pdf_processing",        {"fitz", "pypdf", "pdfplumber", "pdfminer", "PyMuPDF", "pdf2image"}),
    ("vector_search",         {"faiss", "chromadb", "pinecone", "weaviate", "sentence_transformers",
                               "SentenceTransformer", "langchain.vectorstores"}),
    ("llm_integration",       {"openai", "anthropic", "ollama", "together", "litellm", "langchain.llms"}),
    ("web_scraping",          {"bs4", "BeautifulSoup", "selenium", "playwright", "requests_html", "scrapy"}),
    ("local_database",        {"sqlite3", "sqlalchemy", "peewee", "tinydb"}),
    ("cli_tool",              {"argparse", "click", "typer", "fire"}),
    ("gui_app",               {"tkinter", "PyQt5", "PyQt6", "kivy", "flet", "ipywidgets"}),
    ("web_server",            {"fastapi", "flask", "bottle", "starlette", "aiohttp", "django"}),
    ("async_pipeline",        {"asyncio", "aiohttp", "trio"}),
    ("scheduling",            {"schedule", "apscheduler", "celery", "cron"}),
    ("data_analysis",         {"pandas", "polars", "duckdb", "numpy"}),
    ("ml_training",           {"sklearn", "torch", "tensorflow", "keras", "xgboost"}),
    ("code_execution",        {"subprocess", "exec", "compile", "importlib"}),
    ("file_watching",         {"watchdog"}),
    ("image_generation",      {"PIL", "Pillow", "cv2", "opencv", "diffusers"}),
    ("audio",                 {"pyaudio", "sounddevice", "whisper", "librosa"}),
    ("api_clients",           {"requests", "httpx", "urllib"}),
    ("notion_integration",    {"notion_client", "notion"}),
    ("slack_integration",     {"slack_sdk", "slack"}),
    ("crypto_wallet",         {"web3", "eth_account", "solana"}),
    ("game_dev",              {"pygame", "arcade", "pyglet"}),
    ("deploy_ops",            {"docker", "kubernetes", "paramiko", "fabric"}),
    ("native_compilation",    {"cython", "numba", "pybind11", "ctypes"}),
    ("compiler_work",         {"ast", "parser", "tokenize"}),
]


def _fix_stdout() -> None:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _msg_text(msg: dict) -> str:
    raw = msg.get("text", "")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        parts = raw.get("parts", [])
        if parts:
            return " ".join(str(p) for p in parts if isinstance(p, str))
    return ""


def classify_block(body: str) -> set[str]:
    """Return theme names that match a block."""
    # Extract imports (top-level package names)
    imports: set[str] = set()
    for m in IMPORT_PY.finditer(body):
        pkg = (m.group(1) or m.group(2) or "").split(".")[0]
        if pkg:
            imports.add(pkg)

    matches: set[str] = set()
    for theme_name, keywords in THEMES:
        if imports & keywords:
            matches.add(theme_name)
            continue
        # Also match by substring for non-import keywords (e.g., "SentenceTransformer")
        for kw in keywords:
            if kw in body and not kw.islower():  # e.g. class-name-style keywords
                matches.add(theme_name)
                break

    return matches


def analyze_all(memory: list[dict]) -> dict:
    theme_threads: dict[str, set[int]] = defaultdict(set)
    theme_blocks: dict[str, int] = defaultdict(int)
    theme_imports: dict[str, Counter] = defaultdict(Counter)
    thread_themes: dict[int, set[str]] = defaultdict(set)
    thread_blocks: dict[int, int] = defaultdict(int)

    all_imports: Counter = Counter()
    all_defs: Counter = Counter()
    all_classes: Counter = Counter()

    for convo_id, conv in enumerate(memory):
        asst = [m for m in conv.get("messages", []) if m.get("role") == "assistant"]
        text = "\n".join(_msg_text(m) for m in asst)
        blocks = CODE_FENCE.findall(text)
        if not blocks:
            continue
        thread_blocks[convo_id] = len(blocks)

        for lang, body in blocks:
            # Collect all imports/defs/classes for global counters
            for m in IMPORT_PY.finditer(body):
                pkg = (m.group(1) or m.group(2) or "").split(".")[0]
                if pkg:
                    all_imports[pkg] += 1
            for m in DEF_PY.finditer(body):
                all_defs[m.group(1)] += 1
            for m in CLASS_PY.finditer(body):
                all_classes[m.group(1)] += 1

            matches = classify_block(body)
            for t in matches:
                theme_threads[t].add(convo_id)
                theme_blocks[t] += 1
                thread_themes[convo_id].add(t)
                for m in IMPORT_PY.finditer(body):
                    pkg = (m.group(1) or m.group(2) or "").split(".")[0]
                    if pkg:
                        theme_imports[t][pkg] += 1

    return {
        "theme_threads": {k: sorted(v) for k, v in theme_threads.items()},
        "theme_blocks": dict(theme_blocks),
        "theme_imports": {k: dict(v.most_common(10)) for k, v in theme_imports.items()},
        "thread_themes": {str(k): sorted(v) for k, v in thread_themes.items()},
        "thread_blocks": {str(k): v for k, v in thread_blocks.items()},
        "top_imports": dict(all_imports.most_common(40)),
        "top_defs": dict(all_defs.most_common(40)),
        "top_classes": dict(all_classes.most_common(20)),
    }


def get_titles(memory: list[dict], ids: list[int], limit: int = 10) -> list[str]:
    return [memory[i].get("title", f"#{i}") for i in ids[:limit]]


def print_summary(analysis: dict, memory: list[dict], limit: int = 10) -> None:
    themes = sorted(analysis["theme_threads"].items(),
                    key=lambda kv: len(kv[1]), reverse=True)
    print(f"\n{'THEME':<22}{'THREADS':<10}{'BLOCKS':<10}  SAMPLE TITLES")
    print("-" * 120)
    for theme, thread_ids in themes:
        block_count = analysis["theme_blocks"][theme]
        titles = get_titles(memory, thread_ids, limit=3)
        print(f"{theme:<22}{len(thread_ids):<10}{block_count:<10}  {' · '.join(t[:30] for t in titles)}")

    print(f"\nTOP IMPORTS: {list(analysis['top_imports'].items())[:15]}")
    print(f"\nTOP DEFS:    {list(analysis['top_defs'].items())[:15]}")
    print(f"\nTOP CLASSES: {list(analysis['top_classes'].items())[:10]}")


def main() -> int:
    _fix_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full analysis to path")
    ap.add_argument("--theme", help="print threads for a specific theme")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()

    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    print(f"analyzing {len(memory)} conversations for code themes...", file=sys.stderr)
    analysis = analyze_all(memory)

    if args.theme:
        if args.theme not in analysis["theme_threads"]:
            print(f"theme '{args.theme}' not found. Options: {list(analysis['theme_threads'])}", file=sys.stderr)
            return 1
        ids = analysis["theme_threads"][args.theme]
        print(f"\n{args.theme}: {len(ids)} threads, {analysis['theme_blocks'][args.theme]} blocks")
        for i in ids[:args.limit]:
            title = memory[i].get("title", "?")
            blocks = analysis["thread_blocks"].get(str(i), 0)
            print(f"  #{i:>4} blocks={blocks:<4} {title}")
    else:
        print_summary(analysis, memory)

    if args.json:
        Path(args.json).write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())

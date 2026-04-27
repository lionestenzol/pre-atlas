"""
envelope.py — HTML page wrapper for fuzz fragments.

Wraps a sequence of fragments into a full, self-contained HTML document
safe to open in Chrome (or file://) for manual smoke-testing. No external
CDN calls, no scripts, no favicons.
"""
from __future__ import annotations

from fuzz.shapes import Fragment

_DOC_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="generator" content="atl-fuzz"/>
<meta name="atl-fuzz-file-id" content="__FILE_ID__"/>
<meta name="atl-fuzz-seed" content="__SEED__"/>
<meta name="atl-fuzz-count" content="__COUNT__"/>
<title>atl-fuzz __FILE_ID__</title>
<style>
  html, body { margin:0; padding:16px; background:#fff; color:#111;
               font-family: system-ui, -apple-system, "Segoe UI", Arial, sans-serif;
               font-size: 14px; line-height: 1.45; }
  .fz-row { margin: 14px 0; }
  .fz-row > * { max-width: 100%; }
</style>
</head>
<body>
"""

_DOC_FOOT = """</body>
</html>
"""


def wrap(file_id: str, seed: int, fragments: list[Fragment]) -> str:
    """Wrap fragments into a complete HTML document."""
    head = (
        _DOC_HEAD
        .replace("__FILE_ID__", file_id)
        .replace("__SEED__", str(seed))
        .replace("__COUNT__", str(len(fragments)))
    )
    body_parts = [f'<div class="fz-row">{f.html}</div>' for f in fragments]
    return head + "\n".join(body_parts) + "\n" + _DOC_FOOT

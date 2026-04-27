"""Append-only correction recorder.

Step 1: stub. Step 10: real append. When implemented, open with
`mode='a', newline='\\n', encoding='utf-8'` so Windows line endings stay LF and
the JSONL stays parseable.

Schema (per spec §10):
    {
      "timestamp": "ISO8601",
      "page_url": "...",
      "element_id": "...",
      "original_label": "...",
      "corrected_label": "...",
      "original_confidence": 0.0,
      "evidence_streams": ["..."],
      "user_id": "...",
      "session_id": "..."
    }
"""

from __future__ import annotations


def append(entry: dict) -> None:
    raise NotImplementedError("Step 10 - corrections_log.append not yet implemented")

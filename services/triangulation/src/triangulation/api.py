"""FastAPI sidecar. Phase C surface; Phase A ships stubs only.

Run as: `python -m triangulation.api` (after `pip install -e ".[api]"`).
Default port: 3010 (next free after cortex 3009).
"""

from __future__ import annotations


def verify_endpoint(elements: list[dict]) -> list[dict]:
    raise NotImplementedError("Phase C - api.verify_endpoint not yet implemented")


def library_add(label: str, screenshot_path: str) -> dict:
    raise NotImplementedError("Phase C - api.library_add not yet implemented")


def library_stats() -> dict[str, int]:
    raise NotImplementedError("Phase C - api.library_stats not yet implemented")

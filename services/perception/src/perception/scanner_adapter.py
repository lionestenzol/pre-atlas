"""Wraps the existing scanner. Step 1: stub. Step 2: drives anatomy-extension via Playwright.

Per Step 1 BUILD_LOG correction: scanner = `tools/anatomy-extension/content.js`
loaded via the fuzz/runner.py Playwright bootstrap pattern. Adapter reads
`.anatomy-pinned-outline` records + `getBoundingClientRect` and translates
anatomy-v1 envelope into Element schema.
"""

from __future__ import annotations

from .schema import Element


def scan(url: str) -> list[Element]:
    raise NotImplementedError("Step 2 - scanner_adapter.scan not yet implemented")

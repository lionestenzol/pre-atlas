"""Verifies the InPACT consumer never surfaces internal IDs (Rule 5).

Apps in apps/inpact/js/signals.js render only:
  payload.label
  payload.summary
  payload.action_options[].label
  source_layer (translated via SOURCE_LABELS)

This test does a static read of signals.js to confirm:
  1. payload.data is never accessed.
  2. The known internal-ID keys (node_id, path_id, session_id) appear
     nowhere in the source as render targets.
  3. SOURCE_LABELS is the only place source_layer values reach the UI.

A regression here means we may be leaking IDs to the DOM even before
running the browser.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
SIGNALS_JS = ROOT / "apps" / "inpact" / "js" / "signals.js"


def test_signals_js_does_not_read_payload_data():
    src = SIGNALS_JS.read_text(encoding="utf-8")
    # The renderer must not access payload.data at all (it may carry node_id /
    # session_id / path_id from the producer).
    assert ".payload.data" not in src, (
        "signals.js must not read payload.data: it can carry internal IDs"
    )
    assert "payload[\"data\"]" not in src and "payload['data']" not in src


def test_signals_js_does_not_reference_internal_id_keys():
    src = SIGNALS_JS.read_text(encoding="utf-8")
    for key in ("node_id", "path_id", "session_id"):
        # Comments are allowed (we explicitly call them out as forbidden).
        # But any code reference is not.
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue
            assert key not in line, (
                f"signals.js references '{key}' on a non-comment line: {line!r}"
            )


def test_signals_js_translates_source_layer_via_lookup_table():
    """source_layer values must reach the UI only via SOURCE_LABELS map."""
    src = SIGNALS_JS.read_text(encoding="utf-8")
    assert "SOURCE_LABELS" in src
    # The five canonical layer values must all be mapped.
    for layer in ("site_pull", "optogon", "atlas", "ghost_executor", "claude_code"):
        assert layer in src, f"missing source_layer key '{layer}' in SOURCE_LABELS"


def test_no_em_dashes_in_signals_js():
    """feedback_no_em_dashes_in_ui.md: em dash banned from user-facing UI."""
    src = SIGNALS_JS.read_text(encoding="utf-8")
    # Flag em dashes that would land in a rendered string.
    # Allow them in a JS comment line (// or * leading).
    bad_lines = []
    for i, line in enumerate(src.splitlines(), 1):
        if "—" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        bad_lines.append((i, line))
    assert not bad_lines, f"em dashes in user-facing strings: {bad_lines}"


def test_no_em_dashes_in_inpact_screens():
    """Spot-check: the Today-screen Stream block must not introduce em dashes."""
    screens = ROOT / "apps" / "inpact" / "js" / "screens.js"
    src = screens.read_text(encoding="utf-8")
    # Find the Stream block we added.
    match = re.search(r"<!-- Stream: live Signal\.v1 feed.*?ip-stream-list.*?</div>",
                      src, re.DOTALL)
    assert match, "Stream block missing from screens.js"
    block = match.group(0)
    assert "—" not in block, "em dash found in Stream block"

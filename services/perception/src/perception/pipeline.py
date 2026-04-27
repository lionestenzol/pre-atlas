"""Top-level orchestrator. `perceive(url)` runs the full pipeline.

Verbatim from spec §4. Modules are imported as namespaces so monkeypatching in
tests works without dependency injection.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import (
    calibrator,
    chapter_extractor,
    lexicon,
    patterns,
    priors,
    reconciler,
    scanner_adapter,
    text_extractor,
)
from .config import VERSION
from .schema import PageGraph


def perceive(url: str, debug: bool = False) -> PageGraph:
    raw_elements = scanner_adapter.scan(url)
    text_elements = text_extractor.extract(url)

    calibrated = calibrator.calibrate(raw_elements)
    lexicon_tagged = lexicon.apply(calibrated, text_elements)
    predicted = priors.apply(lexicon_tagged)
    matched = patterns.match(predicted)

    unified = reconciler.fuse(
        geometric=matched,
        text=text_elements,
        debug=debug,
    )

    chaptered = chapter_extractor.extract(unified)

    return PageGraph(
        url=url,
        elements=chaptered.elements,
        chapters=chaptered.chapters,
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
        pipeline_version=VERSION,
    )

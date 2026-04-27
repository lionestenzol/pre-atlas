"""Parallel pass over the page that emits text content + typography.

Step 1: stub. Step 3: real implementation. Returns `list[TextContent]` keyed
by approximate position - text doesn't have geometry until merged with scanner
output by the reconciler. Spec §5 Step 3 offered Element vs TextContent;
TextContent honors the type contract (no fabricated x/y/w/h for unpositioned
text nodes).
"""

from __future__ import annotations

from .schema import TextContent


def extract(url: str) -> list[TextContent]:
    raise NotImplementedError("Step 3 - text_extractor.extract not yet implemented")

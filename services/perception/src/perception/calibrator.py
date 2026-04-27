"""Extract dominant x/y axes, compute Signatures, group repeated elements.

Step 1: stub. Step 4: 1D clustering with `AXIS_TOLERANCE_PCT` from config.
"""

from __future__ import annotations

from .schema import Element


def calibrate(elements: list[Element]) -> list[Element]:
    raise NotImplementedError("Step 4 - calibrator.calibrate not yet implemented")

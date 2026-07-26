"""AI-PNG execution storage — port of a working idea from conversation #360
"Decimal vs Binary Logic" (2025-02-24), Pre Atlas harvest pipeline.

Core idea: store a function's source code as base64-encoded PNG metadata,
so the PNG file itself carries executable logic alongside its pixels.
A blank placeholder image is used as the carrier -- this module isn't
about the image content, only the metadata channel.

Bug fixed during porting: the original transcript's store/retrieve pair used
mismatched metadata keys ("execution_logic" on write, "execution_storage" on
read) -- so the original code never actually round-tripped. Both sides use
"execution_logic" here. See code-as-furniture.md: no broken code left in place.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image, PngImagePlugin

METADATA_KEY = "execution_logic"


def store_execution_in_png(function_name: str, code: str, png_file: str | Path) -> None:
    """Encode a function's source into a PNG's metadata."""
    encoded_code = base64.b64encode(code.encode()).decode()
    metadata = {"function_name": function_name, "code": encoded_code}

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    png_metadata = PngImagePlugin.PngInfo()
    png_metadata.add_text(METADATA_KEY, json.dumps(metadata))
    img.save(png_file, "PNG", pnginfo=png_metadata)


def retrieve_execution_from_png(png_file: str | Path) -> dict | None:
    """Decode the function name + source previously stored via store_execution_in_png.

    Returns {"function_name": str, "code": str} with code already base64-decoded,
    or None if the PNG carries no execution metadata.
    """
    img = Image.open(png_file)
    raw = img.info.get(METADATA_KEY)
    if not raw:
        return None

    metadata = json.loads(raw)
    return {
        "function_name": metadata["function_name"],
        "code": base64.b64decode(metadata["code"]).decode(),
    }

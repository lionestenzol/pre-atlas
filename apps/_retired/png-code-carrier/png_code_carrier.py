"""PNG-as-code-carrier — port of conversation #361 "Chatbot Preload
Optimization" (2025-02-23), Pre Atlas harvest pipeline.

The source thread's real, working idea (buried under an "AI-PNG /
self-improving digital DNA" narrative): a PNG's tEXt metadata chunk can
carry a source-code payload alongside the image, so the file is both a
viewable picture and a portable code container in one. This is the
same mechanism tools like Stable Diffusion use to embed generation
parameters in output PNGs — not novel, but real and legitimate.

Departure from the source: the original `extract_and_run()` called
`exec()` on whatever was decoded from the PNG with no gate at all —
arbitrary code execution from a file that could come from anywhere.
That's ported here as `extract_script()` (read-only, no execution) plus
`run_extracted_script()`, which requires `allow_exec=True` to actually
run anything — the PNG is not automatically trusted to be executable
just because it decodes to valid Python.
"""
import base64

from PIL import Image
from PIL.PngImagePlugin import PngInfo


def embed_script(image_path, script_source, out_path, chunk_key="script"):
    encoded = base64.b64encode(script_source.encode()).decode()
    img = Image.open(image_path)
    metadata = PngInfo()
    metadata.add_text(chunk_key, encoded)
    img.save(out_path, "PNG", pnginfo=metadata)


def extract_script(png_path, chunk_key="script"):
    img = Image.open(png_path)
    encoded = img.info.get(chunk_key)
    if encoded is None:
        return None
    return base64.b64decode(encoded).decode()


def run_extracted_script(png_path, chunk_key="script", allow_exec=False):
    script = extract_script(png_path, chunk_key)
    if script is None:
        raise ValueError(f"no '{chunk_key}' chunk found in {png_path}")
    if not allow_exec:
        raise PermissionError(
            "refusing to exec code extracted from a PNG without allow_exec=True "
            "-- a file's metadata is not a trust boundary"
        )
    exec(script, {"__name__": "__png_extracted__"})

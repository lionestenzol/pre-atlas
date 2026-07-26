import tempfile
from pathlib import Path

from ai_png_execution import retrieve_execution_from_png, store_execution_in_png


def test_round_trip():
    code = "def sort_list(lst): return sorted(lst)"
    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "execution.png"
        store_execution_in_png("sort_list", code, png_path)

        result = retrieve_execution_from_png(png_path)

        assert result is not None
        assert result["function_name"] == "sort_list"
        assert result["code"] == code


def test_retrieve_from_png_with_no_metadata_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "blank.png"
        from PIL import Image

        Image.new("RGB", (10, 10)).save(png_path, "PNG")

        assert retrieve_execution_from_png(png_path) is None

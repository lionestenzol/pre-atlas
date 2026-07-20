import os
import tempfile

import pytest
from PIL import Image

from png_code_carrier import embed_script, extract_script, run_extracted_script


@pytest.fixture
def blank_png():
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(path)
    yield path
    os.remove(path)


def test_round_trip(blank_png, tmp_path):
    out_path = str(tmp_path / "carrier.png")
    script = "x = 1 + 1\nprint(x)"
    embed_script(blank_png, script, out_path)

    extracted = extract_script(out_path)
    assert extracted == script


def test_missing_chunk_returns_none(blank_png):
    assert extract_script(blank_png) is None


def test_run_requires_explicit_allow_exec(blank_png, tmp_path):
    out_path = str(tmp_path / "carrier.png")
    embed_script(blank_png, "x = 1", out_path)

    with pytest.raises(PermissionError):
        run_extracted_script(out_path)


def test_run_executes_when_allowed(blank_png, tmp_path):
    out_path = str(tmp_path / "carrier.png")
    embed_script(blank_png, "print('ran')", out_path)

    run_extracted_script(out_path, allow_exec=True)


def test_run_raises_if_no_script(blank_png):
    with pytest.raises(ValueError):
        run_extracted_script(blank_png, allow_exec=True)

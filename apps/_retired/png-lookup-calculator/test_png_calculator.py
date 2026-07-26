import os
import tempfile

import pytest

from png_calculator import generate_lookup_png, retrieve_precomputed_operations


@pytest.fixture(scope="module")
def lookup_png():
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    generate_lookup_png(path)
    yield path
    os.remove(path)


@pytest.mark.parametrize("x,y", [(0, 0), (1, 1), (5, 3), (99, 99), (0, 99), (99, 0), (42, 17)])
def test_matches_real_arithmetic(lookup_png, x, y):
    result = retrieve_precomputed_operations(lookup_png, x, y)
    assert result["addition"] == x + y
    assert result["subtraction"] == x - y
    assert result["multiplication"] == x * y


def test_rejects_out_of_range(lookup_png):
    with pytest.raises(ValueError):
        retrieve_precomputed_operations(lookup_png, 100, 0)
    with pytest.raises(ValueError):
        retrieve_precomputed_operations(lookup_png, 0, -1)

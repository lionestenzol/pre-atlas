import pytest

from novenary import (
    base9_to_int,
    digit_to_ternary_pair,
    int_to_base9,
    novenary_to_trits,
    ternary_pair_to_digit,
    trits_to_novenary,
)


@pytest.mark.parametrize(
    "t_low,t_high,expected",
    [(0, 0, 0), (2, 0, 2), (0, 2, 6), (2, 2, 8), (1, 1, 4)],
)
def test_ternary_pair_to_digit(t_low, t_high, expected):
    assert ternary_pair_to_digit(t_low, t_high) == expected


def test_digit_to_ternary_pair_round_trip():
    for digit in range(9):
        t_low, t_high = digit_to_ternary_pair(digit)
        assert ternary_pair_to_digit(t_low, t_high) == digit


def test_ternary_pair_to_digit_rejects_out_of_range():
    with pytest.raises(ValueError):
        ternary_pair_to_digit(3, 0)


def test_trits_to_novenary_round_trip_even_length():
    trits = [0, 1, 2, 2, 1, 0]
    digits = trits_to_novenary(trits)
    assert novenary_to_trits(digits) == trits


def test_trits_to_novenary_round_trip_odd_length():
    trits = [2, 1, 0]
    digits = trits_to_novenary(trits)
    # without pad_to_length, a trailing 0 padding trit remains
    assert novenary_to_trits(digits) == [2, 1, 0, 0]
    # with pad_to_length, the original length is recovered exactly
    assert novenary_to_trits(digits, pad_to_length=len(trits)) == trits


@pytest.mark.parametrize("n", [0, 1, 8, 9, 80, 81, 12345])
def test_base9_round_trip(n):
    assert base9_to_int(int_to_base9(n)) == n


def test_int_to_base9_known_values():
    assert int_to_base9(0) == [0]
    assert int_to_base9(9) == [1, 0]
    assert int_to_base9(80) == [8, 8]
    assert int_to_base9(81) == [1, 0, 0]


def test_base9_to_int_rejects_invalid_digit():
    with pytest.raises(ValueError):
        base9_to_int([9])

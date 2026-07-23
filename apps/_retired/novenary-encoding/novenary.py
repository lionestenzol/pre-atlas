"""Novenary (base-9) encoding — port of the formal spec from conversation #266
"ChatGPT o1 Overview" (2025-02-27), Pre Atlas harvest pipeline.

The source thread's actual code blocks were an unrelated "AI self ping-pong"
prompt-chaining demo requiring a live OpenAI key (not portable/testable
offline). The genuinely implementable, load-bearing content was in its
final assistant message: a formal mathematical spec for packing two ternary
(base-3) digits into one novenary (base-9) digit, and standard base-9
positional notation for integers. Both are implemented and tested here;
the "DNA-like multi-layer language" framing in the source is left as
unimplemented speculation -- it names an idea (split data into layers,
one novenary sequence per layer) without a concrete algorithm for how a
layer is chosen or what it means to encode, so there's nothing testable
to port for that part.
"""
from __future__ import annotations


def ternary_pair_to_digit(t_low: int, t_high: int) -> int:
    """Pack two ternary digits (each 0-2) into one novenary digit (0-8).

    d = t_low + 3 * t_high, per the source spec's d_i = t_2i + 3*t_2i+1.
    """
    if not (0 <= t_low <= 2 and 0 <= t_high <= 2):
        raise ValueError("ternary digits must each be in 0..2")
    return t_low + 3 * t_high


def digit_to_ternary_pair(digit: int) -> tuple[int, int]:
    """Unpack one novenary digit (0-8) back into two ternary digits (t_low, t_high)."""
    if not (0 <= digit <= 8):
        raise ValueError("novenary digit must be in 0..8")
    return digit % 3, digit // 3


def trits_to_novenary(trits: list[int]) -> list[int]:
    """Pack a sequence of ternary digits into novenary digits, two-at-a-time.

    An odd-length sequence is padded with a trailing 0 trit (undone by
    novenary_to_trits' pad_to_length parameter on the way back).
    """
    padded = list(trits)
    if len(padded) % 2 == 1:
        padded.append(0)
    return [
        ternary_pair_to_digit(padded[i], padded[i + 1])
        for i in range(0, len(padded), 2)
    ]


def novenary_to_trits(digits: list[int], pad_to_length: int | None = None) -> list[int]:
    """Inverse of trits_to_novenary. Pass the original trit count as
    pad_to_length to strip any padding trit added for odd-length input."""
    trits: list[int] = []
    for d in digits:
        t_low, t_high = digit_to_ternary_pair(d)
        trits.extend([t_low, t_high])
    if pad_to_length is not None:
        trits = trits[:pad_to_length]
    return trits


def int_to_base9(n: int) -> list[int]:
    """Standard base-9 positional notation: N = sum(d_i * 9^i).
    Returns digits most-significant-first; [0] for n == 0."""
    if n < 0:
        raise ValueError("only non-negative integers are supported")
    if n == 0:
        return [0]
    digits: list[int] = []
    while n > 0:
        digits.append(n % 9)
        n //= 9
    return list(reversed(digits))


def base9_to_int(digits: list[int]) -> int:
    """Inverse of int_to_base9."""
    n = 0
    for d in digits:
        if not (0 <= d <= 8):
            raise ValueError("base-9 digits must each be in 0..8")
        n = n * 9 + d
    return n

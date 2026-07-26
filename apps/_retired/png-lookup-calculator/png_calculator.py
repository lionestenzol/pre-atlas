"""PNG-as-lookup-table calculator — port of conversation #215
"PNG-based Calculator Overview" (2025-02-25), Pre Atlas harvest pipeline.

Encodes every addition/subtraction/multiplication result for x,y in
[0, 99] into pixel channels of a PNG, then retrieves results by pixel
lookup instead of computing them. The source thread only ever showed
the *read* side (a React component reading pixel data); this adds the
missing generator so the round trip actually exists and can be tested.

Layout (matches the source's described/coded scheme):
  pixel(x, y)       -> red=x+y, green=x-y+99 (shifted to stay non-negative)
  pixel(x+100, y)   -> red=high byte of x*y, blue=low byte of x*y
"""
from PIL import Image

WIDTH = 200
HEIGHT = 100
RANGE = 100


def generate_lookup_png(path):
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    pixels = img.load()
    for y in range(RANGE):
        for x in range(RANGE):
            addition = x + y
            subtraction = x - y + 99  # shifted so it fits in a byte (0..198)
            pixels[x, y] = (addition, subtraction, 0, 255)

            product = x * y
            high = product // 256
            low = product % 256
            pixels[x + 100, y] = (high, 0, low, 255)
    img.save(path)


def retrieve_precomputed_operations(path, x, y):
    if not (0 <= x < RANGE and 0 <= y < RANGE):
        raise ValueError("x and y must be in [0, 99]")

    img = Image.open(path).convert("RGBA")
    pixels = img.load()

    pixel1 = pixels[x, y]
    addition_result = pixel1[0]
    subtraction_result = pixel1[1] - 99

    pixel2 = pixels[x + 100, y]
    multiplication_result = (pixel2[0] * 256) + pixel2[2]

    return {
        "addition": addition_result,
        "subtraction": subtraction_result,
        "multiplication": multiplication_result,
    }

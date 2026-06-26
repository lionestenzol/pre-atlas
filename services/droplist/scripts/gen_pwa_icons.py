"""Generate DropList PWA icons (Task C). Font-free geometric teardrop mark on the
app's dark background, so it needs no asset pipeline and no source image — run it
to (re)materialize ui/icons/. Deviation from the spec's `pwa-asset-generator`:
that tool needs an npm toolchain + a source mark we don't have; a deterministic
PIL draw is simpler for a no-build Python service and produces the same install
artifacts (192/512 + maskable). See ~/.claude/rules/common/assemble-first.md
(hand-roll justified: integration in a pure-Python service, library would add a
Node build step, not make the icon better).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BG = (12, 14, 13, 255)        # --bg #0c0e0d
ACCENT = (95, 227, 179, 255)  # teal accent
ICONS = Path(__file__).resolve().parent.parent / "ui" / "icons"


def _teardrop(size: int, scale: float) -> Image.Image:
    """Dark rounded tile + a centered teal teardrop. `scale` shrinks the glyph so
    maskable icons keep the mark inside the safe zone."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(size * 0.18)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
    # teardrop = circle (bottom) + triangle (top), centered, sized by scale
    cx = size / 2
    r = size * 0.20 * scale
    cy = size * 0.60
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ACCENT)
    tip_y = size * 0.24
    d.polygon([(cx, tip_y), (cx - r, cy), (cx + r, cy)], fill=ACCENT)
    # small highlight bubble
    hr = r * 0.28
    d.ellipse([cx - hr - r * 0.25, cy - hr, cx + hr - r * 0.25, cy + hr], fill=BG)
    return img


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    _teardrop(192, 1.0).save(ICONS / "icon-192.png")
    _teardrop(512, 1.0).save(ICONS / "icon-512.png")
    _teardrop(512, 0.72).save(ICONS / "icon-maskable-512.png")  # mark inside 80% safe zone
    _teardrop(180, 1.0).save(ICONS / "apple-touch-icon.png")
    print("wrote", *(p.name for p in sorted(ICONS.glob("*.png"))))


if __name__ == "__main__":
    main()

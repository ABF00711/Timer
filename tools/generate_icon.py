"""Generate assets/app.ico (multi-size) for Windows tray and installers."""

from __future__ import annotations

import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Install Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "app.ico"

# Deep slate + warm accent — readable at 16px
BG = (26, 39, 68, 255)
ACCENT = (232, 197, 71, 255)
FACE = (240, 244, 252, 255)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m = max(1, size // 16)
    draw.rounded_rectangle(
        [m, m, size - m - 1, size - m - 1],
        radius=max(2, size // 5),
        fill=BG,
    )
    cx = cy = size / 2.0
    r = size * 0.32
    w = max(1, int(round(size / 18)))
    draw.ellipse(
        [
            int(cx - r),
            int(cy - r),
            int(cx + r),
            int(cy + r),
        ],
        outline=ACCENT,
        width=w,
    )
    # Hands ~10:10 (pleasant silhouette)
    def hand(angle_deg: float, length: float, color, width_line: int) -> None:
        rad = math.radians(angle_deg - 90)
        x2 = cx + length * math.cos(rad)
        y2 = cy + length * math.sin(rad)
        draw.line([(cx, cy), (x2, y2)], fill=color, width=width_line)

    hand(300, r * 0.55, FACE, max(1, w))
    hand(60, r * 0.38, ACCENT, max(1, w - 1))
    # Center dot
    cr = max(1.0, size / 28)
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=ACCENT)
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sizes = (16, 24, 32, 48, 64, 128, 256)
    images = [draw_icon(s) for s in sizes]
    images[0].save(
        OUT,
        format="ICO",
        append_images=images[1:],
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

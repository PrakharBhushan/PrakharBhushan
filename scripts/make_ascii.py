"""Turn a photo into the ASCII portraits used by the profile card.

Run locally, once, whenever the photo changes. Only the resulting text files are committed;
the photo itself never goes into the repository.

    pip install pillow numpy
    python scripts/make_ascii.py photo.jpg --crop 250,330,770,830 --cols 72

Writes assets/portrait_dark.txt (bright areas drawn dense, for a dark background) and
assets/portrait_light.txt (dark areas drawn dense, for a light background).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# Sparse to dense. A letter-based ramp (as in jp2a) reads smoother than punctuation-heavy ones.
RAMP = " ...',;:clodxkO0KXNWM"
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def subject_mask(rgb: np.ndarray) -> Image.Image:
    """Separate the person from a green, misty background: background pixels are green-dominant
    or bright and grey. Dark pixels always count as the subject."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    sat = rgb.max(-1) - rgb.min(-1)
    background = ((g > r + 4) & (lum > 50)) | ((lum > 160) & (sat < 45))
    mask = Image.fromarray(((~background) * 255).astype(np.uint8))
    return mask.filter(ImageFilter.MedianFilter(11)).filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))


def largest_region(mask: np.ndarray) -> np.ndarray:
    """Keep only the largest 4-connected region, dropping stray fragments of background."""
    rows, cols = mask.shape
    seen = np.zeros_like(mask)
    best: list[tuple[int, int]] = []
    for sy in range(rows):
        for sx in range(cols):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            region, stack = [], [(sy, sx)]
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                region.append((y, x))
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < rows and 0 <= nx < cols and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(region) > len(best):
                best = region
    out = np.zeros_like(mask)
    for y, x in best:
        out[y, x] = True
    return out


def portrait(photo: Path, crop: tuple[int, int, int, int], cols: int) -> tuple[list[str], list[str]]:
    image = Image.open(photo).convert("RGB").crop(crop)
    rgb = np.asarray(image).astype(np.float32)
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    gray = ImageOps.autocontrast(Image.fromarray(lum.astype(np.uint8)), cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=4, percent=180, threshold=2))  # crisper features

    width, height = image.size
    rows = int(cols * height / width * 0.5)  # terminal cells are about twice as tall as wide
    level = np.asarray(gray.resize((cols, rows), Image.LANCZOS)).astype(np.float32)
    mask = largest_region(np.asarray(subject_mask(rgb).resize((cols, rows), Image.BILINEAR)) > 140)
    lo, hi = np.percentile(level[mask], 2), np.percentile(level[mask], 98)
    norm = np.clip((level - lo) / (hi - lo), 0, 1)

    def draw(values: np.ndarray) -> list[str]:
        return [
            "".join(RAMP[1 + int(values[y, x] * (len(RAMP) - 2))] if mask[y, x] else " " for x in range(cols)).rstrip()
            for y in range(rows)
        ]

    return draw(norm), draw(1 - norm)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photo", type=Path)
    parser.add_argument("--crop", default="250,330,770,830", help="left,top,right,bottom in pixels")
    parser.add_argument("--cols", type=int, default=72)
    args = parser.parse_args()
    dark, light = portrait(args.photo, tuple(int(v) for v in args.crop.split(",")), args.cols)
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "portrait_dark.txt").write_text("\n".join(dark) + "\n")
    (ASSETS / "portrait_light.txt").write_text("\n".join(light) + "\n")
    print(f"wrote {len(dark)} rows x {args.cols} cols to {ASSETS}")


if __name__ == "__main__":
    main()

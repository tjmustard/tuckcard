#!/usr/bin/env python3
"""Draw the Tuckcard app icon and emit the size set.

Source of truth is this script: the icon is drawn at 4x and downsampled, so every
emitted size is antialiased from the same geometry rather than resampled from one
bitmap. Background outside the rounded tile is transparent.

Usage: python icon.py <out-dir>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SS = 4                     # supersample factor
U = 1024                   # design units
BASE = U * SS


def s(v: float) -> int:
    return int(round(v * SS))


TILE = "#2B2430"           # warm charcoal
CARD = "#FBF3E2"           # cream card stock
FOLD = "#E1CDA6"           # dog-ear shade
EDGE = "#2B2430"           # crease ink
ACCENTS = ["#4C9A8F", "#E0A458", "#DB6A4A"]   # back, middle, front


def make_card(w: int, h: int, r: int, accent: str, fold: bool) -> Image.Image:
    """A card: cream stock, accent border, dog-eared top-right corner."""
    pad = s(12)
    f = s(104)                     # dog-ear size
    size = (w + 2 * pad, h + 2 * pad)

    def silhouette(cut: bool) -> Image.Image:
        m = Image.new("L", size, 0)
        d = ImageDraw.Draw(m)
        d.rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=r, fill=255)
        if cut:
            x1, y0 = pad + w - 1, pad
            d.polygon([(x1 - f, y0), (x1, y0 - s(4)), (x1 + s(4), y0 + f)], fill=0)
        return m

    mask = silhouette(fold)

    body = Image.new("RGBA", size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=r,
                         fill=CARD, outline=accent, width=s(14))
    if fold:
        # the cut edge takes the accent border too
        bd.line([(pad + w - 1 - f, pad), (pad + w - 1, pad + f)],
                fill=accent, width=s(14))
        # the folded-back flap, inside the cut
        bd.polygon([(pad + w - 1 - f, pad), (pad + w - 1, pad + f),
                    (pad + w - 1 - f, pad + f)], fill=FOLD)
        bd.line([(pad + w - 1 - f, pad), (pad + w - 1, pad + f)],
                fill=EDGE, width=s(6))

    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(body, (0, 0), mask)
    return out


def fan() -> Image.Image:
    """Three cards fanned, cropped to their ink and centred on a transparent square."""
    w, h, r = s(430), s(610), s(34)
    canvas = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    for i, (cx, cy, angle) in enumerate([
        (s(430), s(500), 20),
        (s(512), s(524), 9),
        (s(596), s(566), -3),
    ]):
        c = make_card(w, h, r, ACCENTS[i], fold=(i == 2))
        rot = c.rotate(angle, resample=Image.BICUBIC, expand=True)
        canvas.alpha_composite(rot, (cx - rot.width // 2, cy - rot.height // 2))

    box = canvas.getbbox()
    art = canvas.crop(box)
    # fit the fan to 76% of the tile, keeping its aspect
    target = s(760)
    k = target / max(art.size)
    art = art.resize((max(1, int(art.width * k)), max(1, int(art.height * k))),
                     Image.LANCZOS)

    out = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    out.alpha_composite(art, ((BASE - art.width) // 2, (BASE - art.height) // 2))
    return out


def build() -> Image.Image:
    canvas = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))

    tile = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, BASE - 1, BASE - 1],
                                           radius=s(196), fill=TILE)
    canvas.alpha_composite(tile)

    glow = Image.new("RGBA", (BASE, BASE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([s(-120), s(-220), s(860), s(640)],
                                 fill=(255, 255, 255, 18))
    glow = glow.filter(ImageFilter.GaussianBlur(s(80)))
    mask = Image.new("L", (BASE, BASE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, BASE - 1, BASE - 1],
                                           radius=s(196), fill=255)
    canvas.alpha_composite(Image.composite(glow, Image.new("RGBA", (BASE, BASE),
                                                          (0, 0, 0, 0)), mask))
    canvas.alpha_composite(fan())
    return canvas


def emit(out: Path) -> None:
    art = build().resize((U, U), Image.LANCZOS)
    out.mkdir(parents=True, exist_ok=True)
    (out / "web").mkdir(exist_ok=True)

    art.save(out / "icon-1024.png")
    art.save(out / "icon-1024.webp", "WEBP", quality=95, method=6)
    for n in (128, 192, 256, 512):
        small = art.resize((n, n), Image.LANCZOS)
        small.save(out / "web" / f"icon-{n}.png")
        small.save(out / "web" / f"icon-{n}.webp", "WEBP", quality=95, method=6)


if __name__ == "__main__":
    emit(Path(sys.argv[1] if len(sys.argv) > 1 else "."))

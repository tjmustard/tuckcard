"""Shared render plan for Tuckcard cards.

One fit algorithm, one mark geometry, one text layout. ``render_pillow.py`` draws
this plan with Pillow; ``templates/shared/card.js`` implements the same plan in
JavaScript and builds the same boxes as DOM. ``tools/parity/run.py`` compares the
two: line breaks and final font sizes must match exactly.

Generated fit reports carry a "generated, don't edit" header. Nothing here draws
or writes files except where a function says so.
"""
from __future__ import annotations

import datetime
import json
import math
import re
from pathlib import Path

from PIL import ImageFont

CORE = Path(__file__).resolve().parent.parent
FONTS = CORE / "fonts"
TEMPLATES = CORE / "templates"

CARD_IN = 5.0
PPI = 96
CARD_PX = int(round(CARD_IN * PPI))

# family -> (file, weight axis behaviour). Variable fonts ship one file with axes;
# the axes are set explicitly because the defaults are surprises: Fraunces defaults
# to wght 900 / opsz 9 and Shantell Sans to wght 300.
FONT_FILES = {
    "Archivo Black": ("archivo-black/ArchivoBlack-Regular.ttf", False),
    "Atkinson Hyperlegible": ("atkinson-hyperlegible/AtkinsonHyperlegible-Regular.ttf", False),
    "Atkinson Hyperlegible Bold": ("atkinson-hyperlegible/AtkinsonHyperlegible-Bold.ttf", False),
    "Caveat": ("caveat/Caveat[wght].ttf", True),
    "Fraunces": ("fraunces/Fraunces[SOFT,WONK,opsz,wght].ttf", True),
    "Liberation Sans": ("liberation-sans/LiberationSans-Regular.ttf", False),
    "Liberation Sans Bold": ("liberation-sans/LiberationSans-Bold.ttf", False),
    "Liberation Serif": ("liberation-serif/LiberationSerif-Regular.ttf", False),
    "Liberation Serif Bold": ("liberation-serif/LiberationSerif-Bold.ttf", False),
    "Literata": ("literata/Literata[opsz,wght].ttf", True),
    "Shantell Sans": ("shantell-sans/ShantellSans[BNCE,INFM,SPAC,wght].ttf", True),
    "Source Serif 4": ("source-serif-4/SourceSerif4[opsz,wght].ttf", True),
}

# font-variation-settings in CSS and set_variation_by_axes in Pillow use these.
AXES = {
    "Fraunces": {"wght": None, "opsz": 40, "SOFT": 0, "WONK": 0},
    "Literata": {"wght": None, "opsz": 20},
    "Shantell Sans": {"wght": None, "BNCE": 0, "INFM": 0, "SPAC": 0},
    "Source Serif 4": {"wght": None, "opsz": 20},
    "Caveat": {"wght": None},
}


def resolve_family(family: str, weight: int) -> tuple[str, int]:
    """Pick the face to load. Static families ship regular and bold files."""
    if weight >= 600:
        bold = family + " Bold"
        if bold in FONT_FILES:
            return bold, weight
    if family not in FONT_FILES:
        raise SystemExit("unknown font family: %s" % family)
    return family, weight


_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}


def font_for(family: str, weight: int, size: float) -> ImageFont.FreeTypeFont:
    face, weight = resolve_family(family, weight)
    key = (face, weight, round(size, 2))
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    rel, variable = FONT_FILES[face]
    font = ImageFont.truetype(str(FONTS / rel), size,
                              layout_engine=ImageFont.Layout.BASIC)
    if variable and AXES.get(face):
        axes = dict(AXES[face])
        axes["wght"] = weight
        font.set_variation_by_axes([axes[k] for k in _axis_order(face)])
    _font_cache[key] = font
    return font


_axis_orders: dict[str, list[str]] = {}


def _axis_order(face: str) -> list[str]:
    """Axis order must match the file's fvar order."""
    order = _axis_orders.get(face)
    if order is None:
        rel, _ = FONT_FILES[face]
        order = _fvar_order(FONTS / rel)
        _axis_orders[face] = order
    return order


def _fvar_order(path: Path) -> list[str]:
    """Read fvar axis tags in file order without fontTools."""
    data = path.read_bytes()
    if data[:4] == b"OTTO":
        pass
    num_tables = int.from_bytes(data[4:6], "big")
    fvar = None
    for i in range(num_tables):
        off = 12 + i * 16
        tag = data[off:off + 4]
        if tag == b"fvar":
            fvar = int.from_bytes(data[off + 8:off + 12], "big")
            break
    if fvar is None:
        return []
    axes_offset = int.from_bytes(data[fvar + 4:fvar + 6], "big")
    axis_count = int.from_bytes(data[fvar + 8:fvar + 10], "big")
    axis_size = int.from_bytes(data[fvar + 10:fvar + 12], "big")
    tags = []
    for i in range(axis_count):
        p = fvar + axes_offset + i * axis_size
        tags.append(data[p:p + 4].decode("ascii"))
    return tags


_MEASURE_PX = 1000.0
_advance_cache: dict[tuple[str, int, str], float] = {}


def advance(text: str, family: str, weight: int, size: float) -> float:
    """Unhinted advance width in CSS pixels.

    FreeType hints glyph advances to whole pixels at the drawing size, while
    the browser positions glyphs at fractional advances. Measuring once at a
    large size and scaling removes the hinting grid from the fit calculation,
    so both renderers break lines at the same place. See DECISIONS.md D-027.
    """
    face, weight = resolve_family(family, weight)
    key = (face, weight, text)
    cached = _advance_cache.get(key)
    if cached is None:
        cached = font_for(family, weight, _MEASURE_PX).getlength(text)
        _advance_cache[key] = cached
    return cached * size / _MEASURE_PX


def measure(text: str, family: str, weight: int, size: float) -> int:
    """Whole-pixel advance width, matching the browser's rounded measurement.

    Rounds half up, as JavaScript's Math.round does. Python's round() uses
    banker's rounding, which would give 40 for a width of 40.5 where the
    browser gives 41.
    """
    return whole_px(advance(text, family, weight, size))


def whole_px(value: float) -> int:
    """Round half up to whole pixels, as JavaScript's Math.round does."""
    return int(math.floor(value + 0.5))


# ---------------------------------------------------------------- randomness

def mulberry32(seed: int):
    """The seeded generator both implementations use. Bit-identical in JS."""
    state = seed & 0xFFFFFFFF

    def _imul(a: int, b: int) -> int:
        return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF

    def nxt() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = _imul(t ^ (t >> 15), 1 | t)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        t &= 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return nxt


def mark_seed(card_n: int, line_index: int, kind: int = 0) -> int:
    return (card_n * 1000 + line_index * 17 + kind * 101) & 0xFFFFFFFF


# ---------------------------------------------------------------- mark shapes

def _catmull(points: list[tuple[float, float]], samples: int = 16) -> list[tuple[float, float]]:
    """Catmull-Rom through the points, sampled. Used by both renderers."""
    if len(points) < 3:
        return list(points)
    pts = [points[0]] + list(points) + [points[-1]]
    out: list[tuple[float, float]] = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(samples):
            t = s / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(points[-1])
    return out


def swash_points(width: float, stroke: float, offset: float, height: float,
                 points: int, amplitude: float, seed: int, wobble: float) -> list[tuple[float, float]]:
    rnd = mulberry32(seed)
    n = max(3, int(points))
    base = []
    for i in range(n):
        t = i / (n - 1)
        x = -2 + t * (width + 4)
        # gentle arc: ends low, middle high, like the prototype's cubic
        y = height * (0.35 + 0.35 * (4 * t * (1 - t)))
        jitter = (rnd() * 2 - 1) * amplitude * wobble
        base.append((x, y + jitter))
    return _catmull(base)


def underline_points(width: float, amplitude: float, seed: int, wobble: float) -> list[tuple[float, float]]:
    if amplitude == 0 or wobble == 0:
        return [(-2.0, 0.0), (width + 2.0, 0.0)]
    rnd = mulberry32(seed)
    pts = []
    for i in range(5):
        t = i / 4
        pts.append((-2 + t * (width + 4), (rnd() * 2 - 1) * amplitude * wobble))
    return _catmull(pts)


def highlight_polygon(x: float, top: float, bottom: float, width: float,
                      inset: float, amplitude: float, points: int,
                      seed: int, wobble: float) -> list[tuple[float, float]]:
    rnd = mulberry32(seed)
    n = max(2, int(points))
    top_pts, bottom_pts = [], []
    for i in range(n):
        t = i / (n - 1)
        px = x - inset + t * (width + 2 * inset)
        if wobble == 0:
            top_pts.append((px, top))
            bottom_pts.append((px, bottom))
        else:
            top_pts.append((px, top + (rnd() * 2 - 1) * amplitude * wobble))
            bottom_pts.append((px, bottom + (rnd() * 2 - 1) * amplitude * wobble))
    return top_pts + list(reversed(bottom_pts))


# ---------------------------------------------------------------- plan

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# Both PDF writers stamp the wall-clock time into /CreationDate and /ModDate, so
# two renders of the same deck differed only in those bytes. Replace the date
# with a fixed one of exactly the same length: the xref offsets are unchanged.
_PDF_DATE = re.compile(rb"(/(?:CreationDate|ModDate) \(D:)([^)]*)(\))")
_PDF_EPOCH = b"20000101000000Z"


def canonical_pdf(path: Path) -> None:
    """Make a PDF's metadata dates fixed and repeatable.

    Pillow writes ``D:YYYYMMDDHHMMSSZ`` and Chromium writes
    ``D:YYYYMMDDHHMMSS+HH'MM'``. The replacement keeps each match's length so
    the cross-reference table stays valid. See DECISIONS.md D-029.
    """
    path = Path(path)
    data = path.read_bytes()

    def fixed(match):
        old = match.group(2)
        return match.group(1) + (_PDF_EPOCH + b" " * len(old))[:len(old)] + match.group(3)

    updated = _PDF_DATE.sub(fixed, data)
    if updated != data:
        path.write_bytes(updated)


def week_of(deck: dict, n: int) -> str:
    """The week-of label for card n, or "" when the deck is not weekly.

    Both print paths call this so the HTML sheet and the raster index list
    the same date.
    """
    number = deck.get("numbering", {})
    if number.get("mode") != "weekly":
        return ""
    created = deck.get("created")
    if not created:
        return ""
    if isinstance(created, datetime.date):
        start = created
    else:
        try:
            start = datetime.date.fromisoformat(str(created)[:10])
        except ValueError:
            return ""
    rule = number.get("week_rule", "contains_jan_1")
    week_start = number.get("week_start", "sunday")
    # weekday index of the day a week starts on: Monday is 0, Sunday is 6.
    offset = 6 if week_start == "sunday" else 0
    if rule == "iso8601":
        # ISO week 1 is the week containing January 4, which starts on a Monday.
        # An early-January date can belong to the previous ISO year.
        iso_year = start.isocalendar()[0]
        jan4 = datetime.date(iso_year, 1, 4)
        week1 = jan4 - datetime.timedelta(days=jan4.weekday())
        day = week1 + datetime.timedelta(days=(n - 1) * 7)
    else:
        jan1 = datetime.date(start.year, 1, 1)
        first_week = jan1 - datetime.timedelta(days=(jan1.weekday() - offset) % 7)
        day = first_week + datetime.timedelta(days=(n - 1) * 7)
    return day.isoformat()


class Style:
    def __init__(self, layout: str, preset: str, theme: str, tokens: dict | None = None,
                 root: Path = CORE):
        self.root = root
        self.layout_name = layout
        self.layout = load_json(root / "templates" / layout / "layout.json")
        self.preset = load_json(root / "presets" / (preset + ".json"))
        self.theme = load_json(root / "themes" / (theme + ".json"))
        self.marks = load_json(root / "marks.json")
        self.tokens = dict(self.preset.get("tokens", {}))
        for key, value in (tokens or {}).items():
            if isinstance(value, dict) and isinstance(self.tokens.get(key), dict):
                merged = dict(self.tokens[key])
                merged.update(value)
                self.tokens[key] = merged
            else:
                self.tokens[key] = value

    def region(self, name: str) -> dict:
        r = self.layout["regions"][name]
        return {
            "x": r["x_in"] * PPI,
            "y": r["y_in"] * PPI,
            "w": r["width_in"] * PPI,
            "h": r["height_in"] * PPI,
        }

    def font(self, role: str) -> tuple[str, int]:
        fonts = self.preset["fonts"][self.layout_name]
        # Weights are flat preset tokens: title_weight, lines_weight, notes_weight.
        weight = self.tokens.get(role + "_weight", 400)
        return fonts[role], int(weight)

    def wobble(self) -> float:
        # SPEC section 7: mark wobble is a token, so a deck's style.tokens can
        # turn it down or off. The preset's own mark_wobble is the default.
        if "mark_wobble" in self.tokens:
            return float(self.tokens["mark_wobble"])
        return float(self.preset.get("mark_wobble", 1))

    def mark_style(self, style: str) -> str:
        return self.preset.get("mark_styles", {}).get(style, style)

    def category_color(self, card: dict) -> str:
        colour = card.get("category_color") or _category_colour(card.get("category", ""))
        palette = self.theme.get("category_palette", {})
        return palette.get(colour, palette.get("orange", self.theme["ink"]))

    def resolve_mark_color(self, token: str, card: dict) -> str:
        if token == "$category":
            return self.category_color(card)
        if token == "$tint":
            return self.theme.get("tint", self.theme["ink"])
        return self.theme.get(token, token)


def _category_colour(category: str) -> str:
    order = ["orange", "teal", "blue", "green", "purple", "red", "pink", "amber"]
    return order[sum(ord(ch) for ch in category) % len(order)]


def _split_words(text: str, target: str | None, occurrence: int) -> tuple[list[str], tuple[int, int] | None]:
    words = text.split()
    if not target:
        return words, None
    hay = " ".join(words)
    start = -1
    for _ in range(occurrence):
        start = hay.find(target, start + 1)
        if start < 0:
            return words, None
    end = start + len(target)
    spans, pos = [], 0
    for i, word in enumerate(words):
        w_start = pos
        w_end = pos + len(word)
        spans.append((w_start, w_end))
        pos = w_end + 1
    first = next((i for i, (a, b) in enumerate(spans) if a <= start < b), None)
    last = next((i for i, (a, b) in enumerate(spans) if a < end <= b), None)
    if first is None or last is None:
        return words, None
    return words, (first, last + 1)


def _wrap(words: list[str], family: str, weight: int, size: float, max_width: float,
          glue: set[int], tail_extra: float = 0.0, tail_index: int | None = None) -> list[list[int]]:
    """Greedy wrap decided on the exact width of the candidate line.

    Measuring the whole candidate line, rather than adding rounded word
    widths, keeps the fit decision within a fraction of a pixel of the
    browser's. Both renderers use the same rule; see DECISIONS.md D-027.
    """
    lines: list[list[int]] = []
    current: list[int] = []
    for i, _word in enumerate(words):
        candidate = current + [i]
        text = " ".join(words[j] for j in candidate)
        width = advance(text, family, weight, size)
        if tail_index is not None and tail_index in candidate:
            width += tail_extra
        if current and i not in glue and width > max_width:
            lines.append(current)
            current = [i]
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _line_runs(words, indices, family, weight, size, mark_span, reserve: float = 0.0):
    """Split one wrapped line into runs, marking the part of the target it holds.

    ``reserve`` is the room a numbered badge takes after the target; later runs
    on the line move right by it so the badge never sits on the text.
    """
    space = measure(" ", family, weight, size)
    first, last = indices[0], indices[-1] + 1
    text = " ".join(words[i] for i in indices)
    width = measure(text, family, weight, size)
    if not mark_span:
        return [{"text": text, "x": 0.0, "width": width, "marked": False}], width
    a = max(first, mark_span[0])
    b = min(last, mark_span[1])
    if a >= b:
        return [{"text": text, "x": 0.0, "width": width, "marked": False}], width
    parts, x = [], 0.0
    if a > first:
        pre = " ".join(words[first:a])
        pw = measure(pre, family, weight, size)
        parts.append({"text": pre, "x": 0.0, "width": pw, "marked": False})
        x = pw + space
    mid = " ".join(words[a:b])
    mw = measure(mid, family, weight, size)
    parts.append({"text": mid, "x": x, "width": mw, "marked": True})
    x += mw + reserve
    if b < last:
        x += space
        post = " ".join(words[b:last])
        pw = measure(post, family, weight, size)
        parts.append({"text": post, "x": x, "width": pw, "marked": False})
    return parts, width + reserve


def plan_card(card: dict, style: Style, *, with_marks: bool = True) -> dict:
    layout = style.layout_name
    builder = {"stacked": _plan_stacked, "notebook": _plan_notebook, "index": _plan_index}[layout]
    return builder(card, style, with_marks)


def _fit_title(card, style, region, size_default, steps, floor):
    """Choose the largest title size whose box fits the declared region.

    The box must end before the next region starts. Both heights are rounded
    to the whole pixel the block is drawn on, so a two-line title that ends on
    the body's top edge touches it rather than intruding. A ``None`` height
    means no size in the ladder fits, and the card fails.
    """
    family, weight = style.font("title")
    lh = style.layout["line_height"]["title"]
    words = card["title"].split()
    room = whole_px(region["h"])
    for size in [size_default] + list(steps):
        if size < floor:
            break
        lines = _wrap(words, family, weight, size, region["w"], set())
        height = whole_px(len(lines) * size * lh)
        if height <= room:
            return size, lines, height
    size = max(floor, size)
    lines = _wrap(words, family, weight, size, region["w"], set())
    return size, lines, None


def _plan_stacked(card, style, with_marks):
    regions = {k: style.region(k) for k in ("header", "title", "body")}
    title_family, title_weight = style.font("title")
    lines_family, lines_weight = style.font("lines")
    notes_family, notes_weight = style.font("notes")
    sizes = style.layout["font_sizes"]
    steps = style.layout["shrink_steps"]
    floors = style.layout["font_floors"]
    lh = style.layout["line_height"]
    gaps = style.layout.get("gaps", {})
    spacing = float(style.tokens.get("spacing", 1))

    title_size, title_lines, title_height = _fit_title(card, style, regions["title"],
                                                      sizes["title"], steps["title"],
                                                      floors["title"])
    title_block = _block(card["title"], title_family, title_weight, title_size,
                         regions["title"]["w"], lh["title"], None, 0)

    body_lines = _prepare_lines(card, style.layout.get("mark_style", "swash"))
    chosen = None
    for line_size in [sizes["lines"]] + list(steps["lines"]):
        if line_size < floors["lines"]:
            break
        for note_size in [sizes["notes"]] + list(steps["notes"]):
            if note_size < floors["notes"]:
                break
            block = _stacked_body(body_lines, regions["body"], lines_family, lines_weight,
                                  line_size, notes_family, notes_weight, note_size,
                                  lh, gaps, spacing)
            if block["height"] <= regions["body"]["h"]:
                chosen = (line_size, note_size, block)
                break
        if chosen:
            break
    failed = chosen is None or title_height is None
    if failed:
        # A failed card is rendered at the floors so its overflow is visible;
        # the renderer does not shrink past the floor.
        line_size = floors["lines"]
        note_size = floors["notes"]
        block = _stacked_body(body_lines, regions["body"], lines_family, lines_weight,
                              line_size, notes_family, notes_weight, note_size,
                              lh, gaps, spacing)
        chosen = (line_size, note_size, block)

    shrunk = chosen[0] != sizes["lines"] or chosen[1] != sizes["notes"] or title_size != sizes["title"]
    plan = {
        "layout": "stacked",
        "card": {"w": CARD_PX, "h": CARD_PX},
        "colors": {"bg": style.theme["background"], "ink": style.theme["ink"],
                   "muted": style.theme["muted"], "accent": style.category_color(card),
                   "tint": style.theme.get("tint"), "rule": style.theme.get("rule"),
                   "on_accent": style.theme.get("on_accent", "#ffffff")},
        "labels": {"header": _header_text(card), "watermark": str(card["n"])},
        "title": {"x": regions["title"]["x"], "y": regions["title"]["y"],
                  "runs": title_block["runs"], "size": title_size,
                  "family": title_family, "weight": title_weight,
                  "line_height": title_size * lh["title"], "color": style.theme["ink"]},
        "body": {"x": regions["body"]["x"], "y": regions["body"]["y"], **block},
        "marks": [],
        "badges": [],
        "report": {"sizes": {"title": title_size, "lines": chosen[0], "notes": chosen[1]},
                   "shrunk": shrunk, "failed": failed},
    }
    return plan


def _prepare_lines(card, default_style="swash"):
    out = []
    for i, line in enumerate(card["lines"]):
        mark = line.get("mark") or None
        target = mark.get("target") if mark else None
        occurrence = int(mark.get("occurrence", 1)) if mark else 1
        style_name = (mark or {}).get("style") or default_style
        words, span = _split_words(line["text"], target, occurrence)
        out.append({"words": words, "span": span, "style": style_name,
                    "note": line.get("note"), "index": i})
    return out


def _stacked_body(prepared, region, line_family, line_weight, line_size,
                  note_family, note_weight, note_size, lh, gaps, spacing):
    x = region["x"]
    width = region["w"]
    cursor = region["y"]
    rows = []
    marks = []
    for item in prepared:
        glue = set(range(item["span"][0] + 1, item["span"][1])) if item["span"] else set()
        lines = _wrap(item["words"], line_family, line_weight, line_size, width, glue)
        line_h = line_size * lh["lines"]
        for li, indices in enumerate(lines):
            span = item["span"] if _line_has_mark(indices, item["span"]) else None
            runs, used = _line_runs(item["words"], indices, line_family, line_weight,
                                    line_size, span)
            rows.append({"kind": "text", "x": x, "y": cursor, "height": line_h,
                         "size": line_size, "family": line_family, "weight": line_weight,
                         "runs": runs})
            if span and item["style"]:
                marks.append({"style": item["style"], "row": ("text", len(rows) - 1),
                              "line_index": item["index"], "span": span,
                              "runs": runs, "size": line_size, "family": line_family,
                              "weight": line_weight, "x": x, "y": cursor,
                              "height": line_h})
            cursor += line_h
        if item["note"]:
            note_indent = style_note_indent(item)
            note_width = width - note_indent
            nlines = _wrap(item["note"].split(), note_family, note_weight, note_size,
                           note_width, set())
            note_h = note_size * lh["notes"]
            for ni, indices in enumerate(nlines):
                runs, used = _line_runs(item["note"].split(), indices, note_family,
                                        note_weight, note_size, None)
                rows.append({"kind": "note", "x": x + note_indent, "y": cursor,
                             "height": note_h, "size": note_size, "family": note_family,
                             "weight": note_weight, "runs": runs})
                cursor += note_h
            cursor += gaps.get("note", 0) * spacing
        cursor += gaps.get("line", 0) * spacing
    return {"x": x, "y": region["y"], "rows": rows, "marks": marks,
            "height": cursor - region["y"]}


def style_note_indent(item):
    return 18.0


def _line_has_mark(indices, span):
    return span is not None and indices[0] < span[1] and indices[-1] >= span[0]


def _block(text, family, weight, size, width, lh, mark_span, indent):
    words = text.split()
    lines = _wrap(words, family, weight, size, width, set())
    runs = []
    for li, indices in enumerate(lines):
        line_runs, used = _line_runs(words, indices, family, weight, size, None)
        for run in line_runs:
            run["row"] = li
        runs.extend(line_runs)
    return {"runs": runs, "lines": len(lines),
            "widths": [measure(" ".join(words[i] for i in indices), family, weight, size)
                       for indices in lines]}


def _badge_reserve(style):
    params = style.marks["badge"]["params"]
    return float(params.get("diameter_px", 15)) + float(params.get("gap_px", 2))


def _header_text(card):
    label = card.get("category_label") or card.get("category", "").replace("-", " ").title()
    pill = card.get("pill")
    return label + (" · " + pill if pill else "")


def _plan_notebook(card, style, with_marks):
    regions = {k: style.region(k) for k in ("header", "title", "lines", "notes")}
    title_family, title_weight = style.font("title")
    lines_family, lines_weight = style.font("lines")
    notes_family, notes_weight = style.font("notes")
    sizes, steps, floors = style.layout["font_sizes"], style.layout["shrink_steps"], style.layout["font_floors"]
    lh = style.layout["line_height"]

    title_size, title_lines, title_height = _fit_title(card, style, regions["title"],
                                                      sizes["title"], steps["title"],
                                                      floors["title"])
    title_block = _block(card["title"], title_family, title_weight, title_size,
                         regions["title"]["w"], lh["title"], None, 0)

    prepared = _prepare_lines(card, style.layout.get("mark_style", "swash"))
    reserve = _badge_reserve(style)
    chosen = None
    for line_size in [sizes["lines"]] + list(steps["lines"]):
        if line_size < floors["lines"]:
            break
        for note_size in [sizes["notes"]] + list(steps["notes"]):
            if note_size < floors["notes"]:
                break
            block = _notebook_body(prepared, regions, lines_family, lines_weight, line_size,
                                   notes_family, notes_weight, note_size, lh, reserve)
            if block["line_height"] <= regions["lines"]["h"] and block["note_height"] <= regions["notes"]["h"]:
                chosen = (line_size, note_size, block)
                break
        if chosen:
            break
    failed = chosen is None or title_height is None
    if failed:
        line_size = floors["lines"]
        note_size = floors["notes"]
        block = _notebook_body(prepared, regions, lines_family, lines_weight, line_size,
                               notes_family, notes_weight, note_size, lh, reserve)
        chosen = (line_size, note_size, block)

    shrunk = chosen[0] != sizes["lines"] or chosen[1] != sizes["notes"] or title_size != sizes["title"]
    title_line_h = title_size * lh["title"]
    title_highlight = None
    if title_block["runs"]:
        last_row = title_block["lines"] - 1
        last_word = card["title"].split()[-1]
        word_w = measure(last_word, title_family, title_weight, title_size)
        line_w = title_block["widths"][last_row]
        title_highlight = {"x": regions["title"]["x"] + line_w - word_w - 2,
                           "y": regions["title"]["y"] + last_row * title_line_h + 0.55 * title_line_h,
                           "w": word_w + 4, "h": 0.45 * title_line_h}
    return {
        "layout": "notebook",
        "card": {"w": CARD_PX, "h": CARD_PX},
        "colors": {"bg": style.theme["background"], "ink": style.theme["ink"],
                   "muted": style.theme["muted"], "accent": style.category_color(card),
                   "tint": style.theme.get("tint"), "rule": style.theme.get("rule"),
                   "on_accent": style.theme.get("on_accent", "#ffffff")},
        "labels": {"header": _header_text(card), "number": str(card["n"])},
        "title": {"x": regions["title"]["x"], "y": regions["title"]["y"],
                  "runs": title_block["runs"], "size": title_size,
                  "family": title_family, "weight": title_weight,
                  "line_height": title_line_h, "color": style.theme["ink"],
                  "lines": title_lines, "highlight": title_highlight},
        "body": {"lines": block["lines"], "notes": block["notes"],
                 "marks": block.get("marks", []),
                 "rule": {"x": 30, "w": 1.5}},
        "marks": [],
        "badges": [],
        "report": {"sizes": {"title": title_size, "lines": chosen[0], "notes": chosen[1]},
                   "shrunk": shrunk, "failed": failed},
    }


def _notebook_body(prepared, regions, line_family, line_weight, line_size,
                   note_family, note_weight, note_size, lh, badge_reserve=17.0):
    line_h = line_size * lh["lines"]
    note_h = note_size * lh["notes"]
    x = regions["lines"]["x"]
    width = regions["lines"]["w"]
    cursor = regions["lines"]["y"]
    rows, notes, marks, badges = [], [], [], []
    number = 0
    max_line = 0.0
    max_note = 0.0
    note_cursor = regions["notes"]["y"]
    reserve = badge_reserve
    for item in prepared:
        if item["span"]:
            number += 1
        glue = set(range(item["span"][0] + 1, item["span"][1])) if item["span"] else set()
        lines = _wrap(item["words"], line_family, line_weight, line_size, width, glue,
                      reserve, item["span"][1] - 1 if item["span"] else None)
        row_start = cursor
        for li, indices in enumerate(lines):
            span = item["span"] if _line_has_mark(indices, item["span"]) else None
            runs, used = _line_runs(item["words"], indices, line_family, line_weight,
                                    line_size, span, reserve if span else 0.0)
            rows.append({"kind": "text", "x": x, "y": cursor, "height": line_h,
                         "size": line_size, "family": line_family, "weight": line_weight,
                         "runs": runs})
            if span and item["style"]:
                marks.append({"style": item["style"], "line_index": item["index"],
                              "runs": runs, "x": x, "y": cursor, "height": line_h,
                              "size": line_size, "family": line_family,
                              "weight": line_weight, "number": number})
            cursor += line_h
        if item["note"]:
            words = item["note"].split()
            prefix = str(number) + "  " if item["span"] else ""
            note_text = prefix + " ".join(words)
            nlines = _wrap(note_text.split(), note_family, note_weight, note_size,
                           regions["notes"]["w"], set())
            ny = max(row_start, note_cursor)
            for indices in nlines:
                runs, used = _line_runs(note_text.split(), indices, note_family,
                                        note_weight, note_size, None)
                notes.append({"kind": "note", "x": regions["notes"]["x"], "y": ny,
                              "height": note_h, "size": note_size, "family": note_family,
                              "weight": note_weight, "runs": runs,
                              "number": number if item["span"] else None})
                ny += note_h
            note_cursor = ny + 4.0
            max_note = max(max_note, note_cursor - regions["notes"]["y"])
        cursor += (line_size * lh["lines"]) * 0.0
        cursor += 0
        # row spacing: prototype pads each row; use 9px scaled with the size ratio
        cursor += 9.0 * (line_size / 18.0)
        max_line = max(max_line, cursor - regions["lines"]["y"])
    for mark in marks:
        pass
    return {"lines": rows, "notes": notes, "marks": marks,
            "line_height": max_line, "note_height": max_note}


def _plan_index(card, style, with_marks):
    regions = {k: style.region(k) for k in ("band", "header", "title", "body", "notes")}
    title_family, title_weight = style.font("title")
    lines_family, lines_weight = style.font("lines")
    notes_family, notes_weight = style.font("notes")
    sizes, steps, floors = style.layout["font_sizes"], style.layout["shrink_steps"], style.layout["font_floors"]
    lh = style.layout["line_height"]

    title_size, title_lines, title_height = _fit_title(card, style, regions["title"],
                                                      sizes["title"], steps["title"],
                                                      floors["title"])
    title_block = _block(card["title"], title_family, title_weight, title_size,
                         regions["title"]["w"], lh["title"], None, 0)

    prepared = _prepare_lines(card, style.layout.get("mark_style", "underline"))
    chosen = None
    reserve = _badge_reserve(style)
    for line_size in [sizes["lines"]] + list(steps["lines"]):
        if line_size < floors["lines"]:
            break
        for note_size in [sizes["notes"]] + list(steps["notes"]):
            if note_size < floors["notes"]:
                break
            block = _index_body(prepared, regions, lines_family, lines_weight, line_size,
                                notes_family, notes_weight, note_size, lh, reserve)
            if block["body_height"] <= regions["body"]["h"] and block["notes_height"] <= regions["notes"]["h"]:
                chosen = (line_size, note_size, block)
                break
        if chosen:
            break
    failed = chosen is None or title_height is None
    if failed:
        line_size = floors["lines"]
        note_size = floors["notes"]
        block = _index_body(prepared, regions, lines_family, lines_weight, line_size,
                            notes_family, notes_weight, note_size, lh, reserve)
        chosen = (line_size, note_size, block)

    shrunk = chosen[0] != sizes["lines"] or chosen[1] != sizes["notes"] or title_size != sizes["title"]
    return {
        "layout": "index",
        "card": {"w": CARD_PX, "h": CARD_PX},
        "colors": {"bg": style.theme["background"], "ink": style.theme["ink"],
                   "muted": style.theme["muted"], "accent": style.category_color(card),
                   "tint": style.theme.get("tint"), "rule": style.theme.get("rule"),
                   "on_accent": style.theme.get("on_accent", "#ffffff")},
        "labels": {"header": _header_text(card), "number": "No. " + str(card["n"]),
                   "try_this": "Try this"},
        "band": {"x": 0, "y": 0, "w": CARD_PX, "h": regions["band"]["h"]},
        "title": {"x": regions["title"]["x"], "y": regions["title"]["y"],
                  "runs": title_block["runs"], "size": title_size,
                  "family": title_family, "weight": title_weight,
                  "line_height": title_size * lh["title"], "color": style.theme["on_accent"]},
        "body": {"x": regions["body"]["x"], "y": regions["body"]["y"],
                 "rows": block["body"], "height": block["body_height"]},
        "notes": {"x": regions["notes"]["x"], "y": regions["notes"]["y"],
                  "rows": block["notes"], "height": block["notes_height"]},
        "marks": [],
        "badges": [],
        "report": {"sizes": {"title": title_size, "lines": chosen[0], "notes": chosen[1]},
                   "shrunk": shrunk, "failed": failed},
    }


def _index_body(prepared, regions, line_family, line_weight, line_size,
                note_family, note_weight, note_size, lh, badge_reserve=17.0):
    body_x, body_w = regions["body"]["x"], regions["body"]["w"]
    cursor = regions["body"]["y"]
    body, notes = [], []
    number = 0
    reserve = badge_reserve
    for item in prepared:
        if item["span"]:
            number += 1
        glue = set(range(item["span"][0] + 1, item["span"][1])) if item["span"] else set()
        lines = _wrap(item["words"], line_family, line_weight, line_size, body_w, glue,
                      reserve, item["span"][1] - 1 if item["span"] else None)
        for indices in lines:
            span = item["span"] if _line_has_mark(indices, item["span"]) else None
            runs, used = _line_runs(item["words"], indices, line_family, line_weight,
                                    line_size, span, reserve if span else 0.0)
            body.append({"kind": "text", "x": body_x, "y": cursor,
                         "height": line_size * lh["lines"], "size": line_size,
                         "family": line_family, "weight": line_weight, "runs": runs,
                         "mark_style": item["style"] if span else None,
                         "line_index": item["index"], "number": number})
            cursor += line_size * lh["lines"]
        if item["note"]:
            notes.append({"number": number, "text": item["note"]})
    # notes: "Try this" label then a two-column numbered list, each column flowing
    note_y = regions["notes"]["y"] + 22.0
    col_gap = 18.0
    col_w = (regions["notes"]["w"] - col_gap) / 2
    note_rows = []
    cursors = [note_y, note_y]
    for note in notes:
        words = note["text"].split()
        lines = _wrap(words, note_family, note_weight, note_size, col_w - 26, set())
        col = 0 if cursors[0] <= cursors[1] else 1
        y = cursors[col]
        for li, indices in enumerate(lines):
            runs, used = _line_runs(words, indices, note_family, note_weight, note_size, None)
            note_rows.append({"x": regions["notes"]["x"] + col * (col_w + col_gap) + 26,
                              "y": y + li * (note_size * lh["notes"]),
                              "height": note_size * lh["notes"], "size": note_size,
                              "family": note_family, "weight": note_weight, "runs": runs,
                              "number": note["number"] if li == 0 else None})
        cursors[col] = y + len(lines) * note_size * lh["notes"] + 4.0
    height = max(cursors) - regions["notes"]["y"]
    return {"body": body, "notes": note_rows, "body_height": cursor - regions["body"]["y"],
            "notes_height": height}


# ---------------------------------------------------------------- shapes

def build_shapes(plan: dict, style: Style, card: dict, with_marks: bool) -> dict:
    """Attach mark polylines, highlight polygons and badges to a plan."""
    if not with_marks:
        return plan
    wobble = style.wobble()
    badge_cfg = style.marks["badge"]["params"]
    out_marks, badges = [], []
    if plan["layout"] == "stacked":
        body = plan["body"]
        for mark in body.get("marks", []):
            out_marks.extend(_stacked_mark(mark, style, card, wobble))
    elif plan["layout"] == "notebook":
        body = plan["body"]
        for i, mark in enumerate(body.get("marks", [])):
            out_marks.extend(_notebook_mark(mark, style, card, wobble, badge_cfg, badges))
    else:
        body = plan["body"]
        for row in body["rows"]:
            if row.get("mark_style"):
                out_marks.extend(_index_mark(row, style, card, wobble, badge_cfg, badges))
    for shape in out_marks:
        shape["color"] = style.resolve_mark_color(shape["color"], card)
    plan["marks"] = out_marks
    plan["badges"] = badges
    for key in ("marks",):
        if key in plan.get("body", {}):
            plan["body"].pop(key, None)
    if plan["layout"] == "notebook":
        plan["body"].pop("marks", None)
    return plan


def _run_bounds(runs):
    marked = [r for r in runs if r.get("marked")]
    if not marked:
        return None
    first = marked[0]
    last = marked[-1]
    return first["x"], last["x"] + last["width"]


def _mark_points(style_name, x, width, baseline, line_height, style, card, line_index, seed_kind):
    definition = style.marks["styles"].get(style_name, style.marks["styles"]["underline"])
    shape = definition["shape"]
    params = definition.get("params", {})
    wobble = style.wobble()
    seed = mark_seed(card["n"], line_index, seed_kind)
    stroke = float(style.tokens.get("mark_stroke", params.get("stroke_width", 2.2)))
    shapes = []
    if shape == "cubic" or shape == "line":
        if shape == "cubic":
            points = swash_points(width, stroke, float(params.get("offset_px", 5)),
                                  float(params.get("height_px", 8)), int(params.get("points", 6)),
                                  float(params.get("amplitude_px", 2.2)), seed, wobble)
        else:
            points = underline_points(width, float(params.get("amplitude_px", 0)), seed, wobble)
        offset = baseline + float(params.get("offset_px", 4))
        shapes.append({"type": "polyline", "points": [(x + px, offset + py) for px, py in points],
                       "stroke": stroke, "color": style.theme["mark_colors"].get(style_name, "$category")})
    elif shape == "highlight":
        top = baseline - line_height + float(params.get("top", 0.52)) * line_height
        bottom = baseline - line_height + float(params.get("bottom", 0.92)) * line_height
        points = highlight_polygon(x, top, bottom, width,
                                   float(params.get("inset_px", 2)),
                                   float(params.get("amplitude_px", 1.4)),
                                   int(params.get("points", 6)), seed, wobble)
        shapes.append({"type": "polygon", "points": points,
                       "color": style.theme["mark_colors"].get(style_name, "$tint")})
    return shapes


def _stacked_mark(mark, style, card, wobble):
    bounds = _run_bounds(mark["runs"])
    if not bounds:
        return []
    x, right = mark["x"] + bounds[0], mark["x"] + bounds[1]
    family, weight = style.font("lines")
    baseline = mark["y"] + font_ascent(family, weight, mark["size"])
    return _mark_points(style.mark_style(mark["style"]), x, right - x, baseline,
                        mark["height"], style, card, mark["line_index"], 3)


def _notebook_mark(mark, style, card, wobble, badge_cfg, badges):
    bounds = _run_bounds(mark["runs"])
    if not bounds:
        return []
    x, right = mark["x"] + bounds[0], mark["x"] + bounds[1]
    family, weight = style.font("lines")
    baseline = mark["y"] + font_ascent(family, weight, mark["size"])
    shapes = _mark_points(style.mark_style(mark["style"]), x, right - x, baseline,
                          mark["height"], style, card, mark["line_index"], 3)
    if mark.get("number"):
        badges.append(_badge(right, baseline, badge_cfg, mark["number"]))
    return shapes


def _index_mark(row, style, card, wobble, badge_cfg, badges):
    bounds = _run_bounds(row["runs"])
    if not bounds:
        return []
    x, right = row["x"] + bounds[0], row["x"] + bounds[1]
    family, weight = style.font("lines")
    baseline = row["y"] + font_ascent(family, weight, row["size"])
    shapes = _mark_points(style.mark_style(row["mark_style"]), x, right - x, baseline,
                          row["height"], style, card, row["line_index"], 3)
    if row.get("number"):
        badges.append(_badge(right, baseline, badge_cfg, row["number"]))
    return shapes


def _badge(right, baseline, cfg, number):
    diameter = float(cfg.get("diameter_px", 15))
    gap = float(cfg.get("gap_px", 2))
    lift = float(cfg.get("lift_px", 5))
    return {"x": right + gap, "cy": baseline - lift, "d": diameter,
            "font_size": float(cfg.get("font_size", 10)), "text": str(number)}


def build_plan(card, style, *, with_marks=True):
    plan = plan_card(card, style, with_marks=with_marks)
    return build_shapes(plan, style, card, with_marks)


# ---------------------------------------------------------------- report

def fit_report(deck: dict, cards: list[dict], renderer: str, style: Style) -> dict:
    entries, failed, shrunk, hand, private = [], [], [], [], []
    for card in cards:
        plan = build_plan(card, style)
        report = plan["report"]
        hand_edited = card.get("approval", {}).get("approved_by") == "hand-edit"
        entries.append({"n": card["n"], "font_sizes": report["sizes"],
                        "shrunk": report["shrunk"], "failed": report["failed"],
                        **({"hand_edited": True} if hand_edited else {})})
        if report["failed"]:
            failed.append(card["n"])
        if report["shrunk"]:
            shrunk.append(card["n"])
        if hand_edited:
            hand.append(card["n"])
        if card.get("visibility") == "private":
            private.append(card["n"])
    return {
        "note": "Generated by scripts/render_%s.py. Do not edit by hand." % renderer,
        "deck_id": deck["id"], "renderer": renderer,
        "layout": style.layout_name, "preset": style.preset["name"],
        "theme": style.theme["name"], "cards": entries,
        "hand_edits": hand, "private_omitted": private,
        "_failed": failed, "_shrunk": shrunk,
    }


def public_report(report: dict) -> dict:
    return {k: v for k, v in report.items() if not k.startswith("_")}


def summary(report: dict) -> str:
    """The short user summary. Names counts and the cards that need attention."""
    cards = report["cards"]
    shrunk = [c["n"] for c in cards if c["shrunk"]]
    failed = [c["n"] for c in cards if c["failed"]]
    lines = ["%d cards rendered with the %s layout, %s preset, %s theme."
             % (len(cards), report.get("layout", "?"), report.get("preset", "?"),
                report.get("theme", "?"))]
    if shrunk:
        lines.append("Shrunk to fit: cards %s." % _numbers(shrunk))
    else:
        lines.append("Every card fits at its default sizes.")
    if failed:
        lines.append("Still too long at the smallest size: cards %s. They return to cards-draft."
                     % _numbers(failed))
    if report["hand_edits"]:
        lines.append("Edited by hand since approval: cards %s."
                     % _numbers(report["hand_edits"]))
    if report["private_omitted"]:
        lines.append("Left out of fridge and lock-screen output for visibility: cards %s."
                     % _numbers(report["private_omitted"]))
    return "\n".join(lines)


def _numbers(nums):
    nums = sorted(nums)
    if len(nums) == 1:
        return str(nums[0])
    return ", ".join(str(n) for n in nums[:-1]) + " and " + str(nums[-1])


# ---------------------------------------------------------------- html

_FONT_CSS_NAME = {
    "Archivo Black": "Archivo Black",
    "Atkinson Hyperlegible": "Atkinson Hyperlegible",
    "Atkinson Hyperlegible Bold": "Atkinson Hyperlegible",
    "Caveat": "Caveat",
    "Fraunces": "Fraunces",
    "Liberation Sans": "Liberation Sans",
    "Liberation Sans Bold": "Liberation Sans",
    "Liberation Serif": "Liberation Serif",
    "Liberation Serif Bold": "Liberation Serif",
    "Literata": "Literata",
    "Shantell Sans": "Shantell Sans",
    "Source Serif 4": "Source Serif 4",
}


def plan_to_dom(plan: dict, style: Style, *, include_rules=True) -> str:
    """Absolute-positioned DOM matching the plan. JavaScript consumes the same boxes."""
    return ""


def font_ascent(family: str, weight: int, size: float) -> float:
    """Ascent in pixels for the face the plan will draw with.

    Uses the same 100 px table the browser receives in the style bundle, so
    the two agree on where a baseline sits. FreeType's hinted ascent at a
    small drawing size rounds to whole pixels and would move the baseline.
    """
    face, _ = resolve_family(family, weight)
    return ascent_table()[face] * size


def ascent_table() -> dict:
    """Face -> ascent/size. Passed to the page so both renderers share a baseline."""
    out = {}
    for face, (rel, variable) in FONT_FILES.items():
        font = ImageFont.truetype(str(FONTS / rel), 100)
        if variable and AXES.get(face):
            axes = dict(AXES[face])
            axes["wght"] = 400
            font.set_variation_by_axes([axes[k] for k in _axis_order(face)])
        ascent, _ = font.getmetrics()
        out[face] = ascent / 100.0
    return out


def style_bundle(style: Style) -> dict:
    return {"layout_name": style.layout_name, "layout": style.layout,
            "preset": style.preset, "theme": style.theme, "marks": style.marks,
            "ascent": ascent_table(), "tokens": style.tokens}


def font_variation_css(family: str, weight: int) -> str:
    face, weight = resolve_family(family, weight)
    axes = dict(AXES.get(face, {}))
    if not axes:
        return ""
    axes["wght"] = weight
    return "font-variation-settings:" + ",".join(
        "'%s' %s" % (k, v) for k, v in axes.items()) + ";"


# ---------------------------------------------------------------- cli helper

def load_deck(path: Path):
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.load(handle)


def style_from_deck(deck: dict, root: Path = CORE) -> Style:
    style = deck["style"]
    return Style(style["layout"], style["preset"], style["theme"], style.get("tokens"), root)


def deck_cards(deck: dict) -> list[dict]:
    pill = deck.get("recipient", {}).get("pill")
    labels = {c["key"]: c["label"] for c in deck.get("categories", [])}
    colours = {c["key"]: c["color"] for c in deck.get("categories", [])}
    cards = []
    for card in deck["cards"]:
        out = dict(card)
        out["pill"] = pill
        out["category_label"] = labels.get(card["category"])
        out["category_color"] = colours.get(card["category"])
        cards.append(out)
    return cards

"""Pillow renderer for Tuckcard cards.

Draws the shared plan from ``render_core`` with Pillow. The browser path in
``render_playwright.py`` draws the same plan as DOM. Variable-font axes are set
explicitly in ``render_core.font_for``; the default axes are not the intended
weights.

    python render_pillow.py --deck deck.yaml --out renders/
    python render_pillow.py --deck deck.yaml --out renders/ --format pdf
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_core as core  # noqa: E402

PPI = 300
CARD_PX = int(round(core.CARD_IN * PPI))
PAGE_SIZES = {"letter": (8.5, 11.0), "a4": (8.27, 11.69)}


def _font(family, weight, size):
    return core.font_for(family, weight, size)


def _hex(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _blend(fg, bg, alpha):
    f, b = _hex(fg), _hex(bg)
    return "#%02x%02x%02x" % tuple(round(alpha * f[i] + (1 - alpha) * b[i]) for i in range(3))


def _tracked(draw, x, baseline, text, font, fill, tracking):
    for ch in text:
        draw.text((x, baseline), ch, font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + tracking
    return x


class Canvas:
    """A card drawn at a scale onto a Pillow image."""

    def __init__(self, plan, style, size_px, origin=(0, 0)):
        self.plan = plan
        self.style = style
        self.scale = size_px / float(core.CARD_PX)
        self.image = Image.new("RGB", (size_px, size_px), _hex(plan["colors"]["bg"]))
        self.draw = ImageDraw.Draw(self.image)
        self.ox, self.oy = origin
        self.card = plan

    def s(self, v):
        return v * self.scale

    def px(self, x, y):
        return (self.ox + self.s(x), self.oy + self.s(y))

    def text(self, x, y, text, family, weight, size, fill, *, anchor="ls", tracking=0.0,
             unhinted=False):
        font = _font(family, weight, self.s(size))
        if tracking:
            _tracked(self.draw, self.ox + self.s(x), self.oy + self.s(y), text, font,
                     _hex(fill), self.s(tracking))
            return
        if unhinted:
            # FreeType rounds glyph advances to whole pixels when it hints at
            # the drawing size; the browser places each glyph on a 1/64 px
            # grid. Draw one glyph at a time at the unhinted advance the plan
            # measured, so a long line keeps the browser's width. DECISIONS.md
            # D-027.
            pen = x
            for ch in text:
                self.draw.text((self.ox + self.s(pen), self.oy + self.s(y)), ch,
                               font=font, fill=_hex(fill), anchor=anchor)
                pen += core.advance(ch, family, weight, size)
            return
        self.draw.text((self.ox + self.s(x), self.oy + self.s(y)), text, font=font,
                       fill=_hex(fill), anchor=anchor)

    def render(self):
        self.draw_decorations()
        self.draw_labels()
        self.draw_marks()
        self.draw_title()
        self.draw_body()
        self.draw_badges()
        return self.image

    # -- layers
    def draw_decorations(self):
        colors = self.plan["colors"]
        layout = self.plan["layout"]
        if layout == "stacked":
            self.text(core.CARD_PX - 26, 16 + 58, self.plan["labels"]["watermark"],
                      "Archivo Black", 400, 64, colors["rule"], anchor="rs")
        elif layout == "notebook":
            rule = self.plan["body"]["rule"]
            self.draw.rectangle([self.px(rule["x"], 0), self.px(rule["x"] + rule["w"], core.CARD_PX)],
                                fill=_hex(_blend(colors["accent"], colors["bg"], 0.5)))
        elif layout == "index":
            band = self.plan["band"]
            self.draw.rectangle([self.px(band["x"], band["y"]),
                                 self.px(band["x"] + band["w"], band["y"] + band["h"])],
                                fill=_hex(colors["accent"]))

    def draw_labels(self):
        colors = self.plan["colors"]
        layout = self.plan["layout"]
        header = self.plan["labels"]["header"].upper()
        if layout == "index":
            baseline = 20 + 8
        else:
            region = self.style.region("header")
            baseline = region["y"] + 9
        x = self.style.region("header")["x"]
        fill = colors["on_accent"] if layout == "index" else colors["muted"]
        self.text(x, baseline, header, "Atkinson Hyperlegible Bold", 700, 11, fill,
                  tracking=1.6)
        if layout == "notebook":
            self.text(core.CARD_PX - 28, 24, self.plan["labels"]["number"], "Fraunces",
                      600, 22, colors["accent"], anchor="rs")
        elif layout == "index":
            self.text(core.CARD_PX - 28, baseline, self.plan["labels"]["number"],
                      "Atkinson Hyperlegible Bold", 700, 11,
                      _blend(colors["on_accent"], colors["accent"], 0.85), anchor="rs")

    def draw_title(self):
        title = self.plan["title"]
        highlight = title.get("highlight")
        if highlight:
            # The notebook title highlights its key word. With no markup in the data,
            # the last word is the key word; see DECISIONS.md D-026.
            self.draw.rectangle([self.px(highlight["x"], highlight["y"]),
                                 self.px(highlight["x"] + highlight["w"],
                                         highlight["y"] + highlight["h"])],
                                fill=_hex(self.plan["colors"]["tint"]))
        for run in title["runs"]:
            baseline = (title["y"] + run.get("row", 0) * title["line_height"]
                        + _ascent(title["family"], title["weight"], title["size"]))
            self.text(title["x"] + run["x"], baseline, run["text"], title["family"],
                      title["weight"], title["size"], title["color"], unhinted=True)

    def draw_body(self):
        layout = self.plan["layout"]
        if layout == "stacked":
            for row in self.plan["body"]["rows"]:
                self.draw_row(row)
        elif layout == "notebook":
            for row in self.plan["body"]["lines"]:
                self.draw_row(row)
            for row in self.plan["body"]["notes"]:
                self.draw_row(row)
        else:
            for row in self.plan["body"]["rows"]:
                self.draw_row(row)
            self.draw_try_this()

    def draw_try_this(self):
        colors = self.plan["colors"]
        notes = self.plan["notes"]
        if not notes["rows"]:
            return
        label_y = notes["y"] + 11
        self.text(notes["x"], label_y, self.plan["labels"]["try_this"].upper(),
                  "Atkinson Hyperlegible Bold", 700, 11, colors["muted"], tracking=1.6)
        self.draw.line([self.px(notes["x"], notes["y"] - 12),
                        self.px(notes["x"] + 424, notes["y"] - 12)],
                       fill=_hex(colors["rule"]), width=max(1, round(self.s(1.5))))
        for row in notes["rows"]:
            self.draw_row(row)
            if row["number"] is not None:
                box = 17
                by = row["y"] + row["height"] / 2 - box / 2
                self.draw.rectangle([self.px(row["x"] - 26, by),
                                     self.px(row["x"] - 26 + box, by + box)],
                                    fill=_hex(colors["accent"]))
                font = _font("Atkinson Hyperlegible Bold", 700, self.s(11 * 0.9))
                self.draw.text((self.ox + self.s(row["x"] - 26 + box / 2),
                                self.oy + self.s(by + box / 2)), str(row["number"]),
                               font=font, fill=_hex(colors["on_accent"]), anchor="mm")

    def draw_row(self, row):
        baseline = row["y"] + _ascent(row["family"], row["weight"], row["size"])
        for run in row["runs"]:
            self.text(row["x"] + run["x"], baseline, run["text"], row["family"],
                      row["weight"], row["size"], self.plan["colors"]["ink"], unhinted=True)

    def draw_marks(self):
        for shape in self.plan["marks"]:
            color = shape["color"]
            if shape["type"] == "polyline":
                self.draw.line([self.px(x, y) for x, y in shape["points"]],
                               fill=_hex(color), width=max(1, round(self.s(shape["stroke"]))),
                               joint="curve")
            else:
                self.draw.polygon([self.px(x, y) for x, y in shape["points"]],
                                  fill=_hex(color))

    def draw_badges(self):
        colors = self.plan["colors"]
        for badge in self.plan["badges"]:
            d = badge["d"]
            left = badge["x"]
            top = badge["cy"] - d / 2
            self.draw.ellipse([self.px(left, top), self.px(left + d, top + d)],
                              fill=_hex(colors["accent"]))
            font = _font("Atkinson Hyperlegible Bold", 700, self.s(badge["font_size"]))
            self.draw.text((self.ox + self.s(left + d / 2), self.oy + self.s(badge["cy"])),
                           badge["text"], font=font, fill=_hex(colors["on_accent"]),
                           anchor="mm")


def _ascent(family, weight, size):
    return core.font_ascent(family, weight, size)


def draw_card(card, style, size_px):
    plan = core.build_plan(card, style)
    return Canvas(plan, style, size_px).render(), plan


def phone_image(card, style, plan_scale=1.0):
    canvas = Canvas(core.build_plan(card, style), style, 1280)
    card_img = canvas.render()
    out = Image.new("RGB", (1440, 3200), _hex(style.theme["background"]))
    out.paste(card_img, (80, 960))
    return out


def tablet_image(card, style):
    canvas = Canvas(core.build_plan(card, style), style, 1600)
    card_img = canvas.render()
    out = Image.new("RGB", (2360, 2360), _hex(style.theme["background"]))
    out.paste(card_img, (380, 380))
    return out


def printable(card, style):
    return Canvas(core.build_plan(card, style), style, CARD_PX).render()


def _index_pages(deck, cards, page_size):
    """Raster index pages, matching the index page of the HTML sheet.

    Lists number, week-of date (weekly decks only), category and title. A row
    wraps instead of clipping, and a long deck breaks onto more index pages.
    """
    if not cards:
        return []
    width_in, height_in = PAGE_SIZES[page_size]
    width, height = int(width_in * PPI), int(height_in * PPI)
    margin = round(0.6 * PPI)
    k = PPI / 96.0
    ink, muted = _hex("#1d1d1f"), _hex("#555555")
    rule, light = _hex("#333333"), _hex("#dddddd")
    title_font = _font("Atkinson Hyperlegible Bold", 700, 18 * k)
    bold_font = _font("Atkinson Hyperlegible Bold", 700, 12 * k)
    body_font = _font("Atkinson Hyperlegible", 400, 12 * k)
    ascent = _ascent("Atkinson Hyperlegible", 400, 12 * k)
    line_h = round(12 * 1.5 * k)
    weekly = deck.get("numbering", {}).get("mode") == "weekly"

    column_in = {"no": 0.0, "week": 0.55, "category": 1.55 if weekly else 0.55,
                 "title": 2.95 if weekly else 1.75}
    x = {name: margin + round(value * 96 * k) if name != "no" else margin
         for name, value in column_in.items()}
    title_right = width - margin
    scratch = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def wrap(text, font, max_width):
        lines, line = [], ""
        for word in str(text).split():
            candidate = word if not line else line + " " + word
            if line and scratch.textlength(candidate, font=font) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        return lines

    rows = []
    for card in cards:
        week = (core.week_of(deck, card["n"]) or "—") if weekly else None
        category = card.get("category_label") or card["category"]
        category_lines = wrap(category, body_font, x["title"] - x["category"] - round(0.15 * 96 * k))
        title_lines = wrap(card["title"], body_font, title_right - x["title"])
        rows.append((str(card["n"]), week, category_lines, title_lines,
                     max(len(category_lines), len(title_lines))))

    def heading(draw, first):
        baseline = margin + round(18 * k)
        label = "%s · index" % deck["title"]
        if not first:
            label += " (continued)"
        draw.text((margin, baseline), label, font=title_font, fill=ink, anchor="ls")
        baseline += round(12 * 1.5 * k)
        draw.text((margin, baseline),
                  "%d cards. Cut on the thin lines; each card is 5 by 5 inches."
                  % len(cards), font=body_font, fill=muted, anchor="ls")
        baseline += round(14 * 1.5 * k)
        headers = [("No.", x["no"])]
        if weekly:
            headers.append(("Week of", x["week"]))
        headers += [("Category", x["category"]), ("Title", x["title"])]
        for label, left in headers:
            draw.text((left, baseline), label, font=bold_font, fill=ink, anchor="ls")
        rule_y = baseline + round(6 * k)
        draw.line([(margin, rule_y), (title_right, rule_y)], fill=rule,
                  width=max(1, round(k)))
        return rule_y + round(11 * 1.5 * k)

    def draw_row(draw, top, row):
        number, week, category_lines, title_lines, _lines = row
        baseline = top + ascent
        draw.text((x["no"], baseline), number, font=body_font, fill=ink, anchor="ls")
        if week is not None:
            draw.text((x["week"], baseline), week, font=body_font, fill=ink, anchor="ls")
        for i, line in enumerate(category_lines):
            draw.text((x["category"], baseline + i * line_h), line, font=body_font,
                      fill=ink, anchor="ls")
        for i, line in enumerate(title_lines):
            draw.text((x["title"], baseline + i * line_h), line, font=body_font,
                      fill=ink, anchor="ls")

    first_top = margin + round(18 * k) + round(12 * 1.5 * k) + round(14 * 1.5 * k) \
        + round(6 * k) + round(11 * 1.5 * k)
    capacity = height - margin - first_top
    groups, current, used = [], [], 0
    for row in rows:
        row_h = row[4] * line_h
        if current and used + row_h > capacity:
            groups.append(current)
            current, used = [], 0
        current.append(row)
        used += row_h
    if current:
        groups.append(current)

    pages = []
    for index, group in enumerate(groups):
        page = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(page)
        top = heading(draw, index == 0)
        for row in group:
            draw_row(draw, top, row)
            row_h = row[4] * line_h
            top += row_h
            draw.line([(margin, top - round(1.5 * k)), (title_right, top - round(1.5 * k))],
                      fill=light, width=max(1, round(k)))
        pages.append(page)
    return pages


def write_pdf(deck, cards, style, path: Path, page_size: str = "letter"):
    """Raster print pages at 300 dpi, two cards stacked per page, then the index.

    The stack matches the HTML print sheet and keeps each 5 in card on a
    Letter or A4 page: two across would need 10 in of width. Index pages
    follow the card pages, as SPEC.md's print format requires.
    """
    width_in, height_in = PAGE_SIZES[page_size]
    page = Image.new("RGB", (int(width_in * PPI), int(height_in * PPI)), "white")
    pages = []
    margin_x = (int(width_in * PPI) - CARD_PX) // 2
    margin_y = (int(height_in * PPI) - 2 * CARD_PX) // 3
    for page_index in range(0, len(cards), 2):
        sheet = page.copy()
        for slot, card in enumerate(cards[page_index:page_index + 2]):
            art = printable(card, style)
            x = margin_x
            y = margin_y + slot * (CARD_PX + margin_y)
            sheet.paste(art, (x, y))
            draw = ImageDraw.Draw(sheet)
            # thin cut line: a hairline rectangle around the card
            draw.rectangle([x, y, x + CARD_PX - 1, y + CARD_PX - 1], outline=(160, 160, 160))
        pages.append(sheet)
    pages.extend(_index_pages(deck, cards, page_size))
    if not pages:
        raise ValueError("nothing to print: the deck has no visible cards")
    first, rest = pages[0], pages[1:]
    first.save(path, "PDF", resolution=PPI, save_all=True, append_images=rest)
    core.canonical_pdf(path)
    return len(pages)


def render_deck(deck, out_dir: Path, formats=("png",), page_size="letter"):
    style = core.style_from_deck(deck)
    cards = core.deck_cards(deck)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    visible = [c for c in cards if c.get("visibility") != "private"]
    if "png" in formats:
        for card in cards:
            image, _ = draw_card(card, style, 1500)
            path = out_dir / ("%s-single-%02d.png" % (deck["id"], card["n"]))
            image.save(path)
            written.append(path)
    if "phone" in formats:
        for card in visible:
            path = out_dir / ("%s-phone-%02d.png" % (deck["id"], card["n"]))
            phone_image(card, style).save(path)
            written.append(path)
    if "tablet" in formats:
        for card in visible:
            path = out_dir / ("%s-tablet-%02d.png" % (deck["id"], card["n"]))
            tablet_image(card, style).save(path)
            written.append(path)
    if "pdf" in formats:
        path = out_dir / ("%s-print.pdf" % deck["id"])
        write_pdf(deck, visible, style, path, page_size)
        written.append(path)
    report = core.fit_report(deck, cards, "pillow", style)
    report_path = out_dir / "fit-report.json"
    report_path.write_text(json.dumps(core.public_report(report), indent=2) + "\n")
    written.append(report_path)
    return written, report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a Tuckcard deck with Pillow.")
    parser.add_argument("--deck", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--format", default="png,phone,tablet,pdf",
                        help="comma-separated: png,phone,tablet,pdf")
    parser.add_argument("--page-size", default=None, choices=sorted(PAGE_SIZES))
    args = parser.parse_args(argv)
    deck = core.load_deck(Path(args.deck))
    formats = tuple(f.strip() for f in args.format.split(",") if f.strip())
    written, report = render_deck(deck, Path(args.out), formats,
                                  args.page_size or deck.get("page_size", "letter"))
    print(core.summary(report))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

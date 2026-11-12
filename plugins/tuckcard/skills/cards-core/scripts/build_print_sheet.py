"""Build the self-contained HTML print sheet.

One file: the cards as JSON, the fonts as base64, the card CSS and the card
engine inline. No network reference. ``@page`` sets the paper and the cut lines
are part of the layout, so the sheet prints the same offline.

    python build_print_sheet.py --deck deck.yaml --out renders/deck-print-sheet.html
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_core as core  # noqa: E402

TEMPLATES = core.TEMPLATES
PAGE_SIZES = {"letter": (8.5, 11.0), "a4": (8.27, 11.69)}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _font_faces() -> str:
    rows = []
    for face, (rel, _variable) in core.FONT_FILES.items():
        family = face[:-5] if face.endswith(" Bold") else face
        weight = 700 if face.endswith(" Bold") else 400
        data = base64.b64encode((core.FONTS / rel).read_bytes()).decode("ascii")
        rows.append(
            '@font-face{font-family:"%s";src:url(data:font/ttf;base64,%s) format("truetype");'
            'font-weight:%d;font-style:normal;font-display:block;}'
            % (family, data, weight))
    return "\n".join(rows)


def _styles() -> str:
    base = _read(TEMPLATES / "shared" / "base.css")
    # base.css imports fonts.css; the sheet embeds the faces itself.
    base = base.replace('@import "fonts.css";', "")
    layout = _read(TEMPLATES / "stacked" / "card.css")
    layout = layout.replace('@import "../shared/base.css";', "")
    return base + "\n" + layout


def sheet_html(deck: dict, cards: list[dict], style: core.Style, page_size: str) -> str:
    width_in, height_in = PAGE_SIZES[page_size]
    cards_json = json.dumps(cards, ensure_ascii=False)
    style_json = json.dumps(core.style_bundle(style), ensure_ascii=False)
    index_rows = []
    for card in cards:
        week = core.week_of(deck, card["n"])
        index_rows.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                           % (card["n"], week or "&mdash;",
                              card.get("category_label") or card["category"], card["title"]))
    has_weeks = deck.get("numbering", {}).get("mode") == "weekly"
    week_header = "<th>Week of</th>" if has_weeks else ""
    index_html = "".join(index_rows)
    pages = (len(cards) + 1) // 2
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s: print sheet</title>
<style>
%(fonts)s
%(styles)s
html, body { background: #dddddd; margin: 0; display: block; }
.sheet { width: %(width)sin; min-height: %(height)sin; background: white; margin: 12px auto; padding: 0.3in;
  box-sizing: border-box; display: flex; flex-direction: column; align-items: center;
  justify-content: flex-start; gap: 0.3in; page-break-after: always; break-after: page; }
.sheet:last-of-type { page-break-after: auto; break-after: auto; }
.slot { width: 480px; height: 480px; outline: 1px solid #999999; flex: none; position: relative; }
.slot .card { border-radius: 0; }
.instructions { font: 12px/1.4 "Atkinson Hyperlegible", sans-serif; color: #333333; text-align: center; margin: 0 0 6px; }
.index-page { width: %(width)sin; min-height: %(height)sin; background: white; margin: 12px auto; padding: 0.6in;
  box-sizing: border-box; page-break-before: always; break-before: page; }
.index-page h1 { font: 700 18px "Atkinson Hyperlegible", sans-serif; margin: 0 0 4px; }
.index-page p { font: 12px/1.4 "Atkinson Hyperlegible", sans-serif; color: #555555; margin: 0 0 14px; }
.index-page table { border-collapse: collapse; width: 100%%; font: 12px/1.5 "Atkinson Hyperlegible", sans-serif; }
.index-page th { text-align: left; border-bottom: 1px solid #333333; padding: 4px 8px 4px 0; }
.index-page td { border-bottom: 1px solid #dddddd; padding: 3px 8px 3px 0; }
@page { size: %(width)sin %(height)sin; margin: 0; }
@media print {
  html, body { background: white; }
  .sheet, .index-page { margin: 0; box-shadow: none; }
  .instructions { display: none; }
}
</style>
</head>
<body>
<p class="instructions">%(title)s &middot; %(count)s &middot; %(pages)s. Print at 100%% / Actual size. Do not use Fit to page.</p>
%(sheet_pages)s
<section class="index-page">
<h1>%(title)s &middot; index</h1>
<p>%(count)s. Cut on the thin lines; each card is 5 by 5 inches.</p>
<table><thead><tr><th>No.</th>%(week_header)s<th>Category</th><th>Title</th></tr></thead>
<tbody>%(index_rows)s</tbody></table>
</section>
<script>
window.TUCK_CARDS = %(cards_json)s;
window.TUCK_STYLE = %(style_json)s;
%(engine)s
function draw() {
  var slots = document.querySelectorAll(".slot");
  slots.forEach(function (slot) {
    var n = parseInt(slot.dataset.n, 10);
    var card = window.TUCK_CARDS.filter(function (c) { return c.n === n; })[0];
    window.Tuckcard.renderInto(card, window.TUCK_STYLE, slot);
  });
  window.__report = { cards: window.TUCK_CARDS.length };
}
window.Tuckcard.loadFonts().then(draw);
</script>
</body>
</html>
""" % {
        "title": deck["title"], "fonts": _font_faces(), "styles": _styles(),
        "width": width_in, "height": height_in,
        "sheet_pages": _sheets(cards, page_size),
        "count": "%d card%s" % (len(cards), "" if len(cards) == 1 else "s"),
        "pages": "%d sheet page%s plus an index page"
                  % (pages, "" if pages == 1 else "s"),
        "week_header": week_header, "index_rows": index_html,
        "cards_json": cards_json, "style_json": style_json,
        "engine": _read(TEMPLATES / "shared" / "card.js"),
    }


def _sheets(cards, page_size):
    out = []
    for i in range(0, len(cards), 2):
        slots = "".join('<div class="slot" data-n="%d"></div>' % card["n"]
                        for card in cards[i:i + 2])
        out.append('<section class="sheet">%s</section>' % slots)
    return "\n".join(out)


def build(deck: dict, out: Path, page_size: str | None = None,
          overlays=None) -> Path:
    style = core.style_from_deck(deck, overlays=overlays)
    cards = [c for c in core.deck_cards(deck) if c.get("visibility") != "private"]
    html = sheet_html(deck, cards, style, page_size or deck.get("page_size", "letter"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a self-contained Tuckcard print sheet.")
    parser.add_argument("--deck", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--page-size", choices=sorted(PAGE_SIZES))
    parser.add_argument("--overlay", action="append", default=[],
                        help="overlay folder laid out like local/ for themes "
                             "and presets (repeatable; an overlay wins over "
                             "cards-core)")
    parser.add_argument("--no-default-overlay", action="store_true",
                        help="do not add local/ when it exists")
    args = parser.parse_args(argv)
    deck = core.load_deck(Path(args.deck))
    path = build(deck, Path(args.out), args.page_size,
                 core.overlay_roots(args.overlay, args.no_default_overlay))
    size = path.stat().st_size
    print("%s: %d bytes, %d font faces embedded"
          % (path, size, len(core.FONT_FILES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

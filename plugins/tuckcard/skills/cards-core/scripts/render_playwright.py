"""Playwright renderer for Tuckcard cards.

The browser is the reference design. Each template page builds the same fit plan
as ``render_pillow.py`` in card.js, so line breaks and font sizes agree; pixels
may differ within the parity threshold in DECISIONS.md.

    python render_playwright.py --deck deck.yaml --out renders/
    python render_playwright.py --deck deck.yaml --out renders/ --format pdf,sheet

Requires Playwright and its Chromium download. These are development-only; the
shipped runtime has no browser dependency.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_core as core  # noqa: E402
import build_print_sheet  # noqa: E402

CARD_PX = core.CARD_PX
SINGLE_PX = 1500
PHONE = (1440, 3200)
TABLET = (2360, 2360)
CARD_IN_PHONE = 1280
CARD_IN_TABLET = 1600


def _launch(playwright):
    return playwright.chromium.launch(args=["--allow-file-access-from-files"])


def _render_card(page, card, bundle, layout):
    template = core.TEMPLATES / layout / "card.html"
    page.goto(template.as_uri())
    page.evaluate("([card, style]) => window.render(card, style, 'single')", [card, bundle])
    page.wait_for_function("window.__ready === true")
    return page.evaluate("window.__report")


def render_single(page, card, bundle, layout, path: Path):
    """1500 by 1500 PNG. The viewport is at device scale so text stays vector-crisp."""
    report = _render_card(page, card, bundle, layout)
    # The template page sits on the editor backdrop. A delivered card sits on
    # its own theme background, which shows through the rounded corners.
    page.evaluate(
        "bg => { document.documentElement.style.background = bg;"
        " document.body.style.background = bg; }",
        bundle["theme"]["background"])
    page.locator(".card").screenshot(path=str(path))
    return report


def compose(browser, card, bundle, layout, page_size, card_px, path):
    """Phone or tablet: a page the size of the output with the card centred."""
    width, height = page_size
    scale = card_px / float(CARD_PX)
    left = (width - card_px) // 2
    top = (height - card_px) // 2 if page_size is PHONE else (height - card_px) // 2
    if page_size is PHONE:
        top = 960
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=1)
    page = context.new_page()
    template = core.TEMPLATES / layout / "card.html"
    page.goto(template.as_uri())
    page.evaluate(
        "async ([card, style, scale, left, top, bg]) => {"
        " await window.render(card, style, 'single');"
        " var cardNode = document.querySelector('.card');"
        " var wrap = document.createElement('div');"
        " wrap.style.cssText = 'position:absolute;left:'+left+'px;top:'+top+'px;"
        "width:'+(480*scale)+'px;height:'+(480*scale)+'px;';"
        " cardNode.style.transform = 'scale('+scale+')';"
        " cardNode.style.transformOrigin = 'top left';"
        " document.documentElement.style.background = bg;"
        " document.body.style.background = bg;"
        " document.body.appendChild(wrap); wrap.appendChild(cardNode);"
        "}",
        [card, bundle, scale, left, top, bundle["theme"]["background"]])
    page.wait_for_function("window.__ready === true")
    report = page.evaluate("window.__report")
    page.screenshot(path=str(path))
    context.close()
    return report


def render_pdf(browser, deck, style, cards, out: Path, page_size: str):
    sheet = build_print_sheet.build(deck, out.with_suffix(".sheet.html"), page_size)
    context = browser.new_context(viewport={"width": 1000, "height": 1200})
    page = context.new_page()
    page.goto(sheet.as_uri())
    page.wait_for_function(
        "document.querySelectorAll('.slot').length > 0 && "
        "document.querySelectorAll('.slot .card').length === document.querySelectorAll('.slot').length")
    page.pdf(path=str(out), width="%.2fin" % build_print_sheet.PAGE_SIZES[page_size][0],
             height="%.2fin" % build_print_sheet.PAGE_SIZES[page_size][1],
             print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
             prefer_css_page_size=True)
    core.canonical_pdf(out)
    context.close()
    return out.with_suffix(".sheet.html")


def render_deck(deck, out_dir: Path, formats=("png",), page_size="letter"):
    style = core.style_from_deck(deck)
    cards = core.deck_cards(deck)
    bundle = core.style_bundle(style)
    out_dir.mkdir(parents=True, exist_ok=True)
    written, reports = [], []
    visible = [c for c in cards if c.get("visibility") != "private"]
    scale = SINGLE_PX / float(CARD_PX)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch(playwright)
        if "png" in formats:
            context = browser.new_context(viewport={"width": CARD_PX, "height": CARD_PX},
                                          device_scale_factor=scale)
            page = context.new_page()
            for card in cards:
                path = out_dir / ("%s-single-%02d.png" % (deck["id"], card["n"]))
                reports.append(render_single(page, card, bundle, style.layout_name, path))
                written.append(path)
            context.close()
        if "phone" in formats:
            for card in visible:
                path = out_dir / ("%s-phone-%02d.png" % (deck["id"], card["n"]))
                compose(browser, card, bundle, style.layout_name, PHONE, CARD_IN_PHONE, path)
                written.append(path)
        if "tablet" in formats:
            for card in visible:
                path = out_dir / ("%s-tablet-%02d.png" % (deck["id"], card["n"]))
                compose(browser, card, bundle, style.layout_name, TABLET, CARD_IN_TABLET, path)
                written.append(path)
        if "pdf" in formats:
            path = out_dir / ("%s-print.pdf" % deck["id"])
            sheet = render_pdf(browser, deck, style, visible, path, page_size)
            written.extend([path, sheet])
        if "sheet" in formats:
            path = out_dir / ("%s-print-sheet.html" % deck["id"])
            build_print_sheet.build(deck, path, page_size)
            written.append(path)
        browser.close()

    by_n = {r["n"]: r for r in reports if r}
    report = core.fit_report(deck, cards, "playwright", style)
    for entry in report["cards"]:
        js = by_n.get(entry["n"])
        if js:
            entry["font_sizes"] = js["sizes"]
            entry["shrunk"] = js["shrunk"]
            entry["failed"] = js["failed"]
    report_path = out_dir / "fit-report.json"
    report_path.write_text(json.dumps(core.public_report(report), indent=2) + "\n")
    written.append(report_path)
    return written, report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a Tuckcard deck with Playwright.")
    parser.add_argument("--deck", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--format", default="png,phone,tablet,pdf,sheet")
    parser.add_argument("--page-size", default=None, choices=sorted(build_print_sheet.PAGE_SIZES))
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

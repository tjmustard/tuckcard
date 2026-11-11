"""The Pillow renderer and the self-contained print sheet. SPEC.md section 7.

These tests need Pillow but no browser, so the CI job that installs
requirements-dev.txt runs them.
"""

import datetime
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
SCRIPTS = CORE / "scripts"
DECK = CORE / "examples/parity-fixture/deck.yaml"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_print_sheet  # noqa: E402
import render_core as core  # noqa: E402
import render_pillow as renderer  # noqa: E402

# A network reference in the sheet: an absolute src or href, a CSS url(), or
# a fetch call. The SVG namespace URI is not a request and is allowed.
NETWORK = re.compile(
    r'(?:src|href)\s*=\s*["\']?https?://|url\(\s*["\']?https?://|'
    r'\bfetch\s*\(|XMLHttpRequest|importScripts|@import\s+url\(')


def deck_and_style():
    deck = core.load_deck(DECK)
    return deck, core.style_from_deck(deck)


def card(n):
    return next(c for c in core.deck_cards(core.load_deck(DECK)) if c["n"] == n)


def test_card_pixels_and_dpi_put_five_inches_on_the_page():
    assert core.CARD_PX == 480
    assert renderer.CARD_PX == 1500
    assert renderer.PPI == 300
    assert renderer.CARD_PX == 5 * renderer.PPI


def test_the_single_png_is_1500_square():
    _, style = deck_and_style()
    image, plan = renderer.draw_card(card(1), style, 1500)
    assert image.size == (1500, 1500)
    assert image.mode == "RGB"
    assert plan["report"]["failed"] is False


def test_the_print_card_is_five_inches_at_300_dpi():
    _, style = deck_and_style()
    image = renderer.printable(card(1), style)
    assert image.size == (1500, 1500)
    assert image.size[0] / renderer.PPI == 5.0


def test_phone_is_1440_by_3200_with_the_card_in_its_band():
    _, style = deck_and_style()
    phone = renderer.phone_image(card(1), style)
    assert phone.size == (1440, 3200)
    art = renderer.Canvas(core.build_plan(card(1), style), style, 1280).render()
    assert phone.crop((80, 960, 80 + 1280, 960 + 1280)).tobytes() == art.tobytes()


def test_tablet_is_2360_square_with_the_card_centred():
    _, style = deck_and_style()
    tablet = renderer.tablet_image(card(1), style)
    assert tablet.size == (2360, 2360)
    art = renderer.Canvas(core.build_plan(card(1), style), style, 1600).render()
    assert tablet.crop((380, 380, 380 + 1600, 380 + 1600)).tobytes() == art.tobytes()


def test_the_raster_pdf_holds_both_cards_and_the_index(tmp_path):
    deck, style = deck_and_style()
    path = tmp_path / "deck.pdf"
    pages = renderer.write_pdf(deck, [card(1), card(2)], style, path, "letter")
    # one card page plus one index page
    assert pages == 2
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 10000


def test_pdf_dates_are_fixed_without_moving_any_offset(tmp_path):
    # Pillow writes D:YYYYMMDDHHMMSSZ; Chromium writes D:YYYYMMDDHHMMSS+00'00'.
    # The two must become the same fixed bytes at the same length.
    pillow_style = b"/CreationDate (D:20261111091927Z)"
    chromium_style = b"/CreationDate (D:20261111091931+00'00')"
    paths = []
    for name, meta in (("a.pdf", pillow_style), ("b.pdf", chromium_style)):
        path = tmp_path / name
        path.write_bytes(b"%PDF-1.7\n" + meta + b"\n%%EOF\n")
        before = path.stat().st_size
        core.canonical_pdf(path)
        assert path.stat().st_size == before
        assert b"D:20000101000000Z" in path.read_bytes()
        paths.append(path)
    assert len(paths[0].read_bytes()) != len(paths[1].read_bytes())
    # Same-length replacements for the same shape give the same bytes.
    first = tmp_path / "c.pdf"
    second = tmp_path / "d.pdf"
    first.write_bytes(pillow_style)
    second.write_bytes(b"/CreationDate (D:20250101000000Z)")
    core.canonical_pdf(first)
    core.canonical_pdf(second)
    assert first.read_bytes() == second.read_bytes()


def test_the_index_lists_the_week_and_breaks_onto_more_pages():
    deck, _style = deck_and_style()
    deck["created"] = datetime.date(2026, 1, 1)
    deck["numbering"] = {"mode": "weekly", "week_rule": "contains_jan_1",
                         "week_start": "sunday"}
    visible = core.deck_cards(deck)[:4]
    pages = renderer._index_pages(deck, visible, "letter")
    assert len(pages) == 1
    assert pages[0].size == (2550, 3300)
    many = visible[:1] * 60
    pages = renderer._index_pages(deck, many, "letter")
    assert len(pages) > 1


def test_the_print_sheet_is_one_self_contained_file(tmp_path):
    deck, style = deck_and_style()
    path = build_print_sheet.build(deck, tmp_path / "sheet.html", "letter")
    html = path.read_text(encoding="utf-8")
    assert not NETWORK.search(html)
    assert html.count("data:font/ttf;base64,") == len(core.FONT_FILES)
    assert "@page { size: 8.5in 11.0in; margin: 0; }" in html
    assert "Print at 100% / Actual size" in html
    sheets = re.findall(r'<section class="sheet">(.*?)</section>', html, re.S)
    # four visible cards, two per sheet page, in sequence
    assert len(sheets) == 2
    assert all(sheet.count('class="slot"') == 2 for sheet in sheets)
    slots = re.findall(r'class="slot" data-n="(\d+)"', html)
    assert slots == ["1", "2", "3", "4"]
    # the index page follows every card
    assert html.index('<section class="index-page">') > html.index('data-n="4"')


def test_the_print_sheet_lists_the_visible_cards_in_its_index(tmp_path):
    deck, style = deck_and_style()
    html = build_print_sheet.build(deck, tmp_path / "sheet.html").read_text(encoding="utf-8")
    assert "<td>4</td>" in html
    assert "A private card" not in html
    assert "4 cards" in html


def test_a4_changes_the_page_size(tmp_path):
    deck, style = deck_and_style()
    html = build_print_sheet.build(
        deck, tmp_path / "sheet.html", "a4").read_text(encoding="utf-8")
    assert "@page { size: 8.27in 11.69in; margin: 0; }" in html

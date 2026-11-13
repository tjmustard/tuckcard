"""The Playwright renderer's command line. Needs a browser, so these tests skip
when Chromium is absent. The CI render job installs the Playwright package but
never downloads a browser, so it runs these as skips.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")
pytest.importorskip("playwright")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
SCRIPTS = CORE / "scripts"
DECK = CORE / "examples/parity-fixture/deck.yaml"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_playwright as renderer  # noqa: E402


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:  # the browser binary is a separate download
            pytest.skip("Chromium is not installed: %s" % exc)
        browser.close()


def test_a_relative_out_directory_renders_every_output(tmp_path, monkeypatch, chromium):
    # The docstring advertises --out renders/, so the first invocation a user
    # tries is a relative path. Chromium loads the print sheet by file URI,
    # which has to be absolute, so the renderer resolves the folder itself.
    monkeypatch.chdir(tmp_path)
    assert renderer.main(["--deck", str(DECK), "--out", "renders"]) == 0

    out = tmp_path / "renders"
    names = {path.name for path in out.iterdir()}
    expected = {"fit-report.json", "parity-fixture-print.pdf",
                "parity-fixture-print.sheet.html", "parity-fixture-print-sheet.html"}
    expected |= {"parity-fixture-single-%02d.png" % n for n in range(1, 6)}
    expected |= {"parity-fixture-phone-%02d.png" % n for n in range(1, 5)}
    expected |= {"parity-fixture-tablet-%02d.png" % n for n in range(1, 5)}
    assert names == expected


def test_an_overlay_theme_reaches_both_planners(tmp_path, chromium):
    # SPEC section 8: a theme in the overlay is merged on top at render time.
    # Both engines must read the same file, so the plans agree and the mark
    # colour resolves from the overlay's palette, not the shipped one.
    import json

    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(ROOT / "tools/parity"))
    import render_core as core
    import run as parity

    theme = json.loads((CORE / "themes/color.json").read_text(encoding="utf-8"))
    theme["name"] = "mint"
    theme["background"] = "#eef7f1"
    theme["category_palette"] = {key: "#123456" for key in theme["category_palette"]}
    overlay = tmp_path / "overlay"
    (overlay / "themes").mkdir(parents=True)
    (overlay / "themes/mint.json").write_text(json.dumps(theme), encoding="utf-8")

    style = core.Style("stacked", "casual", "mint", overlays=[overlay])
    bundle = core.style_bundle(style)
    card = core.deck_cards(core.load_deck(DECK))[0]
    python_plan = core.build_plan(card, style)
    assert {mark["color"] for mark in python_plan["marks"]} == {"#123456"}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_context(
                viewport={"width": core.CARD_PX, "height": core.CARD_PX}).new_page()
            page.goto((core.TEMPLATES / "stacked" / "card.html").as_uri())
            js_plan = page.evaluate(
                "async ([card, style]) => { await window.Tuckcard.loadFonts();"
                " return window.Tuckcard.plan(card, style); }", [card, bundle])
        finally:
            browser.close()

    assert parity.compare_plans(python_plan, js_plan, card["n"]) == []
    assert {mark["color"] for mark in js_plan["marks"]} == {"#123456"}

#!/usr/bin/env python3
"""Renderer parity check.

Renders a reference set through Playwright and Pillow and compares:

- the fit plan: line breaks, final font sizes, run positions, marks, badges;
- the pixels at 1500 by 1500, within the threshold below.

The reference set is every combination of layout (3), preset (2) and theme
(3), 18 combinations, plus each layout token at its default and extreme
values: mark wobble, corner radius, mark stroke weight and spacing, and the
layout file's own regions, sizes, steps, floors, line heights, gaps and note
tokens. See SPEC.md section 7 and DECISIONS.md D-028.

    python tools/parity/run.py
    python tools/parity/run.py --out /tmp/parity --json /tmp/parity/report.json --keep

Needs Pillow and Playwright with Chromium. These are development only, see
requirements-dev.txt. Without them the tool says what could not run and
exits 2 rather than claiming a pass.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "plugins" / "tuckcard" / "skills" / "cards-core"
sys.path.insert(0, str(CORE / "scripts"))

import render_core as core  # noqa: E402
import render_pillow as pillow_renderer  # noqa: E402

DECK = CORE / "examples" / "parity-fixture" / "deck.yaml"
LAYOUTS = ("stacked", "notebook", "index")
PRESETS = ("casual", "professional")
THEMES = ("color", "mono", "dark")

RENDER_PX = 1500
# Both renderers draw the same plan at the same size. What remains is
# rasterisation: Chromium rasterises unhinted outlines through Skia, Pillow
# rasterises hinted outlines through FreeType, and each places glyphs on a
# slightly different sub-pixel grid. The densest reference card, the one that
# deliberately fails to fit and draws at its floors, reaches a mean channel
# difference of 10.5 and 7.1% of pixels over 32. These limits accept that and
# still reject a wrong colour, a missing element or a different typeface. The
# plan comparison is the exact structural check: it holds line breaks, final
# font sizes and element positions, so the pixel check is a second opinion
# rather than the only one. A whole-CSS-pixel displacement on a card with
# body text clears both limits. DECISIONS.md D-028.
MEAN_MAX = 12.0
FRAC_OVER_32_MAX = 0.08

# Chromium lays text out with Skia's 1/64 px positions; FreeType gives Pillow
# an unhinted fractional advance. The two agree to well under a quarter pixel
# for most words but can straddle a whole-pixel boundary, which moves a run
# start by one space advance (about 3 px at the smallest sizes). Whole-pixel
# run widths are internal to each engine: both engines draw their runs
# absolutely at their own plan's x, so a small offset is invisible. Line
# breaks and font sizes are still compared exactly.
TOL_POS = 2.5       # one space advance of measurement slack


def _load_cards():
    deck = core.load_deck(DECK)
    return deck, core.deck_cards(deck)


def _js_plan(page, card, bundle):
    return page.evaluate(
        "async ([card, style]) => { await window.Tuckcard.loadFonts();"
        " return window.Tuckcard.plan(card, style); }", [card, bundle])


def _rows(plan):
    body = plan["body"]
    return body.get("rows") or body.get("lines") or []


def _row_text(row):
    return "".join(run["text"] for run in row["runs"])


def _compare_rows(py_rows, js_rows, label, out):
    if len(py_rows) != len(js_rows):
        out.append("%s row count %d != %d" % (label, len(py_rows), len(js_rows)))
        return
    for i, (a, b) in enumerate(zip(py_rows, js_rows)):
        if _row_text(a) != _row_text(b):
            out.append("%s row %d text %r != %r" % (label, i, _row_text(a), _row_text(b)))
        if a.get("kind") != b.get("kind"):
            out.append("%s row %d kind %s != %s" % (label, i, a.get("kind"), b.get("kind")))
        if a["size"] != b["size"]:
            out.append("%s row %d size %s != %s" % (label, i, a["size"], b["size"]))
        if abs(a["y"] - b["y"]) > 0.55:
            out.append("%s row %d y %.3f != %.3f" % (label, i, a["y"], b["y"]))
        if abs(a["x"] - b["x"]) > TOL_POS:
            out.append("%s row %d x %.3f != %.3f" % (label, i, a["x"], b["x"]))
        if len(a["runs"]) != len(b["runs"]):
            out.append("%s row %d run count %d != %d"
                       % (label, i, len(a["runs"]), len(b["runs"])))
            continue
        for k, (ra, rb) in enumerate(zip(a["runs"], b["runs"])):
            if abs(ra["x"] - rb["x"]) > TOL_POS:
                out.append("%s row %d run %d x %.3f != %.3f"
                           % (label, i, k, ra["x"], rb["x"]))


def compare_plans(py, js, card_n):
    """Return a list of differences. Empty means the plans match."""
    out = []
    if py["title"]["size"] != js["title"]["size"]:
        out.append("card %d title size %s != %s"
                   % (card_n, py["title"]["size"], js["title"]["size"]))
    if len(py["title"]["runs"]) != len(js["title"]["runs"]):
        out.append("card %d title run count" % card_n)
    else:
        for i, (a, b) in enumerate(zip(py["title"]["runs"], js["title"]["runs"])):
            if a["text"] != b["text"]:
                out.append("card %d title run %d text %r != %r"
                           % (card_n, i, a["text"], b["text"]))
            if abs(a["x"] - b["x"]) > TOL_POS:
                out.append("card %d title run %d x %.3f != %.3f"
                           % (card_n, i, a["x"], b["x"]))
    _compare_rows(_rows(py), _rows(js), "card %d body" % card_n, out)
    _compare_rows(py["body"].get("notes", []), js["body"].get("notes", []),
                  "card %d notes" % card_n, out)
    if len(py["marks"]) != len(js["marks"]):
        out.append("card %d mark count %d != %d"
                   % (card_n, len(py["marks"]), len(js["marks"])))
    for i, (a, b) in enumerate(zip(py["marks"], js["marks"])):
        if a["type"] != b["type"]:
            out.append("card %d mark %d type %s != %s"
                       % (card_n, i, a["type"], b["type"]))
        if len(a["points"]) != len(b["points"]):
            out.append("card %d mark %d point count %d != %d"
                       % (card_n, i, len(a["points"]), len(b["points"])))
            continue
        for k, (pa, pb) in enumerate(zip(a["points"], b["points"])):
            if abs(pa[0] - pb[0]) > TOL_POS or abs(pa[1] - pb[1]) > TOL_POS:
                out.append("card %d mark %d point %d (%s,%s) != (%s,%s)"
                           % (card_n, i, k, pa[0], pa[1], pb[0], pb[1]))
                break
    if len(py["badges"]) != len(js["badges"]):
        out.append("card %d badge count %d != %d"
                   % (card_n, len(py["badges"]), len(js["badges"])))
    for i, (a, b) in enumerate(zip(py["badges"], js["badges"])):
        if abs(a["x"] - b["x"]) > TOL_POS or abs(a["cy"] - b["cy"]) > TOL_POS:
            out.append("card %d badge %d position differs" % (card_n, i))
        if a["text"] != b["text"]:
            out.append("card %d badge %d text %r != %r"
                       % (card_n, i, a["text"], b["text"]))
    if py["report"]["sizes"] != js["report"]["sizes"]:
        out.append("card %d report sizes %s != %s"
                   % (card_n, py["report"]["sizes"], js["report"]["sizes"]))
    if py["report"]["shrunk"] != js["report"]["shrunk"]:
        out.append("card %d shrunk flag differs" % card_n)
    if py["report"]["failed"] != js["report"]["failed"]:
        out.append("card %d failed flag differs" % card_n)
    return out


def image_distance(a, b):
    from PIL import ImageChops, ImageStat

    if a.size != b.size:
        return None, "size %s != %s" % (a.size, b.size)
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    mean = sum(ImageStat.Stat(diff).mean) / 3.0
    hist = diff.convert("L").histogram()
    total = sum(hist) or 1
    over32 = sum(hist[33:]) / total
    if mean > MEAN_MAX:
        return (mean, over32), "mean %.2f > %.2f" % (mean, MEAN_MAX)
    if over32 > FRAC_OVER_32_MAX:
        return (mean, over32), "%.2f%% of pixels over 32 > %.2f%%" % (
            over32 * 100, FRAC_OVER_32_MAX * 100)
    return (mean, over32), None


def layout_cases(layout_name):
    """Every value in layout.json at its default and an extreme.

    Regions are tested as one aggregate geometry case in each direction
    because x, y, width and height belong to one another: moving a single
    field is not a layout a power user would set.
    """
    base = json.loads((CORE / "templates" / layout_name / "layout.json").read_text())
    sizes = base["font_sizes"]
    steps = base["shrink_steps"]
    floors = base["font_floors"]
    lh = base["line_height"]
    gaps = base["gaps"]
    cases = [("default", {})]
    cases.append(("font_sizes max", {"font_sizes": {k: v + 4 for k, v in sizes.items()}}))
    cases.append(("font_sizes min", {"font_sizes": {k: max(1, round(v - 4, 1))
                                                    for k, v in sizes.items()}}))
    cases.append(("shrink_steps one", {"shrink_steps": {k: [floors[k]] for k in steps}}))
    cases.append(("shrink_steps many", {"shrink_steps": {
        k: [round(sizes[k] - (sizes[k] - floors[k]) * i / 5, 1) for i in range(1, 5)]
        for k in steps}}))
    cases.append(("font_floors low", {"font_floors": {k: max(1, round(v - 3, 1))
                                                      for k, v in floors.items()}}))
    cases.append(("font_floors high", {"font_floors": dict(sizes)}))
    cases.append(("line_height tight", {"line_height": {k: round(v * 0.85, 3)
                                                         for k, v in lh.items()}}))
    cases.append(("line_height loose", {"line_height": {k: round(v * 1.3, 3)
                                                         for k, v in lh.items()}}))
    cases.append(("gaps zero", {"gaps": {k: 0 for k in gaps}}))
    cases.append(("gaps double", {"gaps": {k: v * 2 for k, v in gaps.items()}}))
    cases.append(("note_indent 0", {"note_indent_px": 0}))
    cases.append(("note_indent 40", {"note_indent_px": 40}))
    cases.append(("note_prefix empty", {"note_prefix": ""}))
    cases.append(("note_prefix arrow", {"note_prefix": "-> "}))
    cases.append(("notes_inline flipped",
                  {"notes_inline": not base.get("notes_inline")}))
    cases.append(("numbered_notes flipped",
                  {"numbered_notes": not base.get("numbered_notes")}))
    for style in ("swash", "highlight", "underline"):
        cases.append(("mark_style " + style, {"mark_style": style}))
    regions_in = {}
    regions_out = {}
    for name, region in base["regions"].items():
        regions_in[name] = {"x_in": max(0.0, round(region["x_in"] - 0.05, 4)),
                            "y_in": max(0.0, round(region["y_in"] - 0.05, 4)),
                            "width_in": round(region["width_in"] + 0.1, 4),
                            "height_in": round(region["height_in"] + 0.1, 4)}
        regions_out[name] = {"x_in": round(region["x_in"] + 0.05, 4),
                             "y_in": round(region["y_in"] + 0.05, 4),
                             "width_in": round(region["width_in"] - 0.1, 4),
                             "height_in": round(region["height_in"] - 0.1, 4)}
    cases.append(("regions inset", {"regions": regions_out}))
    cases.append(("regions outset", {"regions": regions_in}))
    return base, cases


def preset_cases():
    """Layout tokens: mark wobble, corner radius, mark stroke, spacing."""
    return [
        ("default", {}),
        # SPEC section 7 calls mark wobble a token, so the extremes go through
        # the token path a deck's style.tokens would use. The presets' own
        # mark_wobble values (1 and 0) are already covered by the 18 combos.
        ("tokens.mark_wobble 0", {"tokens": {"mark_wobble": 0}}),
        ("tokens.mark_wobble 2", {"tokens": {"mark_wobble": 2}}),
        ("corner_radius 0", {"corner_radius": 0}),
        ("corner_radius 12", {"corner_radius": 12}),
        ("tokens.mark_stroke 1", {"tokens": {"mark_stroke": 1.0}}),
        ("tokens.mark_stroke 4", {"tokens": {"mark_stroke": 4.0}}),
        ("tokens.spacing 0.5", {"tokens": {"spacing": 0.5}}),
        ("tokens.spacing 1.5", {"tokens": {"spacing": 1.5}}),
    ]


def _merge(base, patch):
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def _style_variant(layout, preset, theme, *, layout_patch=None, preset_patch=None):
    style = core.Style(layout, preset, theme)
    if layout_patch:
        style.layout = _merge(style.layout, layout_patch)
    if preset_patch:
        style.preset = _merge(style.preset, preset_patch)
        # Style copies the preset tokens into style.tokens, so a patched
        # preset needs them rebuilt for the token reads to see the change.
        style.tokens = dict(style.preset.get("tokens", {}))
    return style


def _save_pair(work: Path, name: str, py_img, page, background):
    py_path = work / (name + "-pillow.png")
    pw_path = work / (name + "-playwright.png")
    py_img.save(py_path)
    # Put the card on its own theme background so the rounded corners match
    # the Pillow image instead of showing the template page's editor backdrop.
    page.evaluate(
        "bg => { document.documentElement.style.background = bg;"
        " document.body.style.background = bg; }",
        background)
    page.locator(".card").screenshot(path=str(pw_path))
    return py_path, pw_path


def _render_both(work, name, card, style, bundle, page):
    from PIL import Image

    py_img, py_plan = pillow_renderer.draw_card(card, style, RENDER_PX)
    page.evaluate("([card, style]) => window.render(card, style, 'single')",
                  [card, bundle])
    page.wait_for_function("window.__ready === true")
    py_path, pw_path = _save_pair(work, name, py_img, page, style.theme["background"])
    distance, problem = image_distance(Image.open(py_path), Image.open(pw_path))
    return py_plan, distance, problem


def _check_one(work, name, card, style, bundle, page):
    py_plan = core.build_plan(card, style)
    js_plan = _js_plan(page, card, bundle)
    diffs = compare_plans(py_plan, js_plan, card["n"])
    _, distance, problem = _render_both(work, name, card, style, bundle, page)
    entry = {"n": card["n"], "plan_ok": not diffs, "differences": diffs,
             "mean": round(distance[0], 3) if distance else None,
             "frac_over_32": round(distance[1], 4) if distance else None,
             "pixel_ok": problem is None, "problem": problem,
             "sizes": py_plan["report"]["sizes"],
             "shrunk": py_plan["report"]["shrunk"],
             "failed": py_plan["report"]["failed"]}
    return entry, (not diffs and problem is None)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare Tuckcard's two renderers.")
    parser.add_argument("--out", default=None, help="directory for the images and report")
    parser.add_argument("--json", default=None, help="write the machine-readable report here")
    parser.add_argument("--keep", action="store_true", help="keep the rendered images")
    args = parser.parse_args(argv)

    try:
        from PIL import Image  # noqa: F401
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - environment dependent
        print("parity unavailable: %s" % exc)
        print("install the development requirements: python -m pip install -r requirements-dev.txt")
        print("then install Chromium: python -m playwright install chromium")
        return 2

    work = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="tuckcard-parity-"))
    work.mkdir(parents=True, exist_ok=True)
    deck, cards = _load_cards()
    results = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "deck": deck["id"], "render_px": RENDER_PX,
               "threshold": {"mean_max": MEAN_MAX, "frac_over_32_max": FRAC_OVER_32_MAX},
               "combinations": [], "layout_cases": [], "preset_cases": [],
               "could_not_run": []}
    failures = []

    try:
        with sync_playwright() as playwright:
            from render_playwright import _launch

            browser = _launch(playwright)
            try:
                pages = {}
                for layout in LAYOUTS:
                    context = browser.new_context(
                        viewport={"width": core.CARD_PX, "height": core.CARD_PX},
                        device_scale_factor=float(RENDER_PX) / core.CARD_PX)
                    page = context.new_page()
                    page.goto((core.TEMPLATES / layout / "card.html").as_uri())
                    page.evaluate("window.Tuckcard.loadFonts()")
                    pages[layout] = page

                # 18 combinations of layout, preset and theme, every fixture card.
                for layout in LAYOUTS:
                    page = pages[layout]
                    for preset in PRESETS:
                        for theme in THEMES:
                            style = core.Style(layout, preset, theme)
                            bundle = core.style_bundle(style)
                            entry = {"layout": layout, "preset": preset, "theme": theme,
                                     "cards": [], "ok": True}
                            for card in cards:
                                name = "combo-%s-%s-%s-%02d" % (
                                    layout, preset, theme, card["n"])
                                card_result, ok = _check_one(
                                    work, name, card, style, bundle, page)
                                entry["cards"].append(card_result)
                                if not ok:
                                    entry["ok"] = False
                                    failures.append(("%s / %s / %s card %d"
                                                     % (layout, preset, theme, card["n"]),
                                                     card_result))
                            results["combinations"].append(entry)

                # Every layout file value at default and extremes, both presets.
                for layout in LAYOUTS:
                    base, cases = layout_cases(layout)
                    page = pages[layout]
                    for preset in PRESETS:
                        for case_name, patch in cases:
                            style = _style_variant(layout, preset, "color",
                                                   layout_patch=patch)
                            if case_name == "default":
                                style = core.Style(layout, preset, "color")
                            bundle = core.style_bundle(style)
                            entry = {"layout": layout, "preset": preset,
                                     "case": case_name, "cards": [], "ok": True}
                            name = "layout-%s-%s-%s" % (
                                layout, preset, case_name.replace(" ", "-"))
                            card_result, ok = _check_one(
                                work, name, cards[0], style, bundle, page)
                            entry["cards"].append(card_result)
                            if not ok:
                                entry["ok"] = False
                                failures.append(("%s / %s / %s" % (layout, preset, case_name),
                                                 card_result))
                            results["layout_cases"].append(entry)

                # Layout tokens from the presets: wobble, corner radius, stroke, spacing.
                for layout in LAYOUTS:
                    page = pages[layout]
                    for preset in PRESETS:
                        for case_name, patch in preset_cases():
                            style = _style_variant(layout, preset, "color",
                                                   preset_patch=patch)
                            bundle = core.style_bundle(style)
                            entry = {"layout": layout, "preset": preset,
                                     "case": case_name, "cards": [], "ok": True}
                            name = "token-%s-%s-%s" % (
                                layout, preset,
                                case_name.replace(" ", "-").replace(".", "-"))
                            card_result, ok = _check_one(
                                work, name, cards[0], style, bundle, page)
                            if case_name == "tokens.mark_wobble 0":
                                # A clean geometric mark has no random offset, so two
                                # plans must produce exactly the same points.
                                first = _js_plan(page, cards[0], bundle)
                                second = _js_plan(page, cards[0], bundle)
                                if first["marks"] != second["marks"]:
                                    card_result["differences"].append(
                                        "wobble 0 is not deterministic")
                                    card_result["plan_ok"] = False
                                    ok = False
                            entry["cards"].append(card_result)
                            if not ok:
                                entry["ok"] = False
                                failures.append(("%s / %s / %s" % (layout, preset, case_name),
                                                 card_result))
                            results["preset_cases"].append(entry)
            finally:
                browser.close()
    except Exception as exc:  # pragma: no cover - environment dependent
        results["could_not_run"].append(str(exc))
        print("parity could not run: %s" % exc)
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        return 2

    results["ok"] = not failures
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=2) + "\n")

    groups = (("combinations", results["combinations"]),
              ("layout cases", results["layout_cases"]),
              ("token cases", results["preset_cases"]))
    for group_name, entries in groups:
        passed = sum(1 for e in entries if e["ok"])
        print("%s: %d/%d pass" % (group_name, passed, len(entries)))
        for entry in entries:
            label = "%s / %s / %s" % (entry["layout"], entry["preset"],
                                      entry.get("theme") or entry.get("case"))
            if entry["ok"]:
                worst_mean = max((c["mean"] or 0) for c in entry["cards"])
                print("  PASS %-56s worst mean %.2f" % (label, worst_mean))
            else:
                print("  FAIL %s" % label)
                for card in entry["cards"]:
                    for diff in card["differences"][:3]:
                        print("       card %d: %s" % (card["n"], diff))
                    if card["problem"]:
                        print("       card %d pixels: %s" % (card["n"], card["problem"]))
    print("Threshold: mean channel difference <= %.2f and <= %.2f%% of pixels over 32."
          % (MEAN_MAX, FRAC_OVER_32_MAX * 100))
    if failures:
        print("%d case(s) failed." % len(failures))
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("Images under %s" % work)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

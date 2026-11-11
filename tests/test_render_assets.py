"""The render assets: templates, layout files, themes, presets and marks.

These checks need no browser and no Pillow, so the CI job that has only
requirements.txt can run them. SPEC.md sections 7 and 8.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
TEMPLATES = CORE / "templates"
VALIDATE = CORE / "scripts/validate.py"
LAYOUTS = ("stacked", "notebook", "index")
PRESETS = ("casual", "professional")
THEMES = ("color", "mono", "dark")

SIZES = ("title", "lines", "notes")

# An absolute src or href, a CSS url(), an import or a fetch would reach the
# network. The SVG namespace URI is not a request and is allowed.
NETWORK = re.compile(
    r'(?:src|href)\s*=\s*["\']?https?://|url\(\s*["\']?https?://|'
    r'\bfetch\s*\(|XMLHttpRequest|importScripts|@import\s+url\(')


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path):
    return subprocess.run([sys.executable, str(VALIDATE), str(path)],
                          capture_output=True, text=True)


def test_every_layout_has_the_three_template_files():
    for layout in LAYOUTS:
        folder = TEMPLATES / layout
        for name in ("card.html", "card.css", "layout.json"):
            assert (folder / name).is_file(), layout + " is missing " + name


@pytest.mark.parametrize("layout", LAYOUTS)
def test_layout_json_validates_and_describes_five_inches(layout):
    path = TEMPLATES / layout / "layout.json"
    result = validate(path)
    assert result.returncode == 0, result.stdout + result.stderr
    data = read(path)
    assert set(data["regions"]) >= {"header", "title"}
    for name, region in data["regions"].items():
        for key in ("x_in", "y_in", "width_in", "height_in"):
            assert isinstance(region[key], (int, float)), (name, key)
        assert 0 <= region["x_in"] < 5 and 0 <= region["y_in"] < 5, name
        assert region["x_in"] + region["width_in"] <= 5.0 + 1e-9, name
        assert region["y_in"] + region["height_in"] <= 5.0 + 1e-9, name
    for group in ("font_sizes", "shrink_steps", "font_floors"):
        assert set(data[group]) == set(SIZES), (layout, group)
    for role in SIZES:
        floor = data["font_floors"][role]
        assert data["font_sizes"][role] >= floor
        assert all(step >= floor for step in data["shrink_steps"][role])


@pytest.mark.parametrize("layout", LAYOUTS)
def test_a_title_region_ends_before_the_content_below_it(layout):
    """A title must not be declared over the region it sits above.

    The stacked layout once declared 0.95 in of title where only 0.74 in
    existed, so a long title could paint over the first body line while the
    fit test still passed. SPEC.md section 7 gives the title its own region.
    """
    regions = read(TEMPLATES / layout / "layout.json")["regions"]
    title = regions["title"]
    bottom = title["y_in"] + title["height_in"]
    for name in ("body", "lines", "notes"):
        if name in regions:
            assert bottom <= regions[name]["y_in"] + 1e-9, (layout, name)


@pytest.mark.parametrize("path", [
    CORE / "marks.json",
    *(CORE / "themes" / (name + ".json") for name in THEMES),
    *(CORE / "presets" / (name + ".json") for name in PRESETS),
])
def test_style_asset_validates(path):
    result = validate(path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_themes_are_color_mono_and_dark():
    color = read(CORE / "themes/color.json")
    mono = read(CORE / "themes/mono.json")
    dark = read(CORE / "themes/dark.json")
    assert color["background"] == "#ffffff"
    # mono is solid black ink and has no coloured accent for a laser printer
    assert set(mono["category_palette"].values()) == {"#111111"}
    assert dark["background"] != color["background"]
    assert dark["ink"] == "#f4efe7"


def test_presets_match_the_spec_table():
    casual = read(CORE / "presets/casual.json")
    professional = read(CORE / "presets/professional.json")
    assert casual["fonts"]["stacked"] == {
        "title": "Archivo Black", "lines": "Source Serif 4", "notes": "Shantell Sans"}
    assert professional["fonts"]["stacked"] == {
        "title": "Liberation Sans", "lines": "Liberation Serif", "notes": "Liberation Sans"}
    assert professional["fonts"]["index"] == {
        "title": "Liberation Sans", "lines": "Liberation Serif", "notes": "Liberation Sans"}
    assert casual["mark_wobble"] > 0
    assert professional["mark_wobble"] == 0
    assert professional["mark_styles"] == {"swash": "underline"}
    assert professional["corner_radius"] < casual["corner_radius"]


def test_marks_json_has_every_style_and_a_badge():
    marks = read(CORE / "marks.json")
    assert {"swash", "highlight", "underline"} <= set(marks["styles"])
    for name, definition in marks["styles"].items():
        assert definition["shape"] in {"cubic", "line", "highlight"}, name
        assert isinstance(definition["params"], dict)
    assert marks["badge"]["shape"] == "badge"
    assert marks["badge"]["params"]["diameter_px"] > 0


def test_template_pages_load_the_shared_engine_and_expose_render():
    for layout in LAYOUTS:
        html = (TEMPLATES / layout / "card.html").read_text(encoding="utf-8")
        assert "../shared/card.js" in html
        assert "window.render =" in html
        assert "window.__report" in html
        assert "window.Tuckcard.render(card, style, format)" in html
        css = (TEMPLATES / layout / "card.css").read_text(encoding="utf-8")
        assert "../shared/base.css" in css


def test_shared_page_styles_the_five_inch_card_from_variables():
    base = (TEMPLATES / "shared/base.css").read_text(encoding="utf-8")
    assert "width: 480px" in base
    assert "height: 480px" in base
    for name in ("--bg", "--ink", "--corner-radius"):
        assert "var(" + name in base
    # Kerning and ligatures are off so the browser uses the advances the plan
    # measured. Removing this breaks parity. See DECISIONS.md D-027.
    assert "font-kerning: none" in base
    assert '"kern" 0, "liga" 0' in base


def test_templates_make_no_network_request():
    for path in TEMPLATES.rglob("*"):
        if path.suffix not in {".html", ".css", ".js"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not NETWORK.search(text), path


def test_the_print_sheet_instruction_names_actual_size():
    source = (CORE / "scripts/build_print_sheet.py").read_text(encoding="utf-8")
    assert "Print at 100%% / Actual size" in source
    assert "@page" in source

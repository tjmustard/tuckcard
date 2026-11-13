"""Overlay themes and presets resolve at render time. SPEC.md sections 2 and 8.

An overlay folder is shaped like ``local/``: it holds ``themes/`` and
``presets/``. A name found there wins over cards-core, so a user can replace a
shipped style without editing the plugin. See DECISIONS.md D-038.
"""

import json
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

import render_core as core  # noqa: E402
import lint  # noqa: E402


def write_style(root, folder, name, changes, base=None):
    """One overlay theme or preset under ``root``, based on a shipped file."""
    source = CORE / folder / ((base or ("color" if folder == "themes" else "casual")) + ".json")
    data = json.loads(source.read_text(encoding="utf-8"))
    data.update(changes)
    data["name"] = name
    path = root / folder / (name + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def deck_with(theme="color", preset="casual"):
    deck = core.load_deck(DECK)
    deck["style"]["theme"] = theme
    deck["style"]["preset"] = preset
    return deck


def test_an_overlay_only_theme_resolves(tmp_path):
    write_style(tmp_path, "themes", "mint", {"background": "#eef7f1", "ink": "#112233"})
    style = core.Style("stacked", "casual", "mint", overlays=[tmp_path])
    assert style.theme["name"] == "mint"
    assert style.theme["background"] == "#eef7f1"


def test_an_overlay_only_preset_resolves(tmp_path):
    write_style(tmp_path, "presets", "bold", {"corner_radius": 24})
    style = core.Style("stacked", "bold", "color", overlays=[tmp_path])
    assert style.preset["name"] == "bold"
    assert style.preset["corner_radius"] == 24


def test_a_same_name_overlay_entry_wins_over_the_shipped_one(tmp_path):
    write_style(tmp_path, "themes", "color", {"background": "#101010"})
    overlaid = core.Style("stacked", "casual", "color", overlays=[tmp_path])
    shipped = core.Style("stacked", "casual", "color")
    assert overlaid.theme["background"] == "#101010"
    assert shipped.theme["background"] != "#101010"


def test_the_first_overlay_given_wins(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    write_style(first, "themes", "mint", {"background": "#aaaaaa"})
    write_style(second, "themes", "mint", {"background": "#bbbbbb"})
    style = core.Style("stacked", "casual", "mint", overlays=[first, second])
    assert style.theme["background"] == "#aaaaaa"


def test_a_missing_theme_names_every_location_it_tried(tmp_path):
    with pytest.raises(FileNotFoundError) as raised:
        core.Style("stacked", "casual", "nope", overlays=[tmp_path])
    message = str(raised.value)
    assert str(tmp_path / "themes" / "nope.json") in message
    assert str(CORE / "themes" / "nope.json") in message


def test_a_missing_preset_names_the_same_locations(tmp_path):
    with pytest.raises(FileNotFoundError) as raised:
        core.Style("stacked", "nope", "color", overlays=[tmp_path])
    message = str(raised.value)
    assert str(tmp_path / "presets" / "nope.json") in message
    assert str(CORE / "presets" / "nope.json") in message


def test_no_overlay_still_uses_the_shipped_theme():
    style = core.style_from_deck(deck_with())
    shipped = json.loads((CORE / "themes/color.json").read_text(encoding="utf-8"))
    assert style.theme == shipped


def test_a_deck_with_an_overlay_theme_renders(tmp_path):
    import render_pillow

    write_style(tmp_path / "overlay", "themes", "mint", {"background": "#eef7f1"})
    deck = deck_with(theme="mint")
    written, report = render_pillow.render_deck(
        deck, tmp_path / "out", formats=("png",),
        overlays=[tmp_path / "overlay"])
    assert report["theme"] == "mint"
    assert any(path.suffix == ".png" for path in written)
    assert (tmp_path / "out" / "fit-report.json").is_file()


def test_lint_fit_uses_the_overlay_it_is_given(tmp_path):
    write_style(tmp_path, "themes", "mint", {})
    deck = deck_with(theme="mint")
    cards = core.deck_cards(deck)
    findings, notes = lint.check_fit(deck, cards, None, [tmp_path])
    assert notes == []
    skipped, missing_notes = lint.check_fit(deck, cards, None)
    assert skipped == []
    assert missing_notes and "mint" in missing_notes[0]


def test_the_default_overlay_is_local_when_it_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert core.overlay_roots([], False) == []
    (tmp_path / "local").mkdir()
    assert core.overlay_roots([], False) == [Path("local")]
    assert core.overlay_roots([], True) == []
    assert core.overlay_roots(["other"], False) == [Path("other")]

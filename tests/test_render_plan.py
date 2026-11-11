"""The shared render plan: fit, marks and the fit report. SPEC.md section 7.

Pillow is a development dependency. Without it these tests skip instead of
failing, and the asset tests still cover the files CI can check.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
SCRIPTS = CORE / "scripts"
DECK = CORE / "examples/parity-fixture/deck.yaml"
LAYOUTS = ("stacked", "notebook", "index")
PRESETS = ("casual", "professional")
THEMES = ("color", "mono", "dark")
SIZES = ("title", "lines", "notes")

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_core as core  # noqa: E402

from jsonschema import Draft202012Validator  # noqa: E402


def cards():
    return core.deck_cards(core.load_deck(DECK))


def by_n(n):
    return next(card for card in cards() if card["n"] == n)


def row_texts(plan):
    body = plan["body"]
    rows = []
    if "lines" in body:
        rows.extend(body["lines"])
    if "notes" in body:
        rows.extend(body["notes"])
    if "rows" in body:
        rows.extend(body["rows"])
    return [" ".join(run["text"] for run in row["runs"]) for row in rows]


def test_the_fixture_has_every_report_case():
    numbers = [card["n"] for card in cards()]
    assert numbers == [1, 2, 3, 4, 5]
    assert by_n(5)["visibility"] == "private"
    assert by_n(4)["approval"]["approved_by"] == "hand-edit"


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("theme", THEMES)
def test_every_combination_builds_the_same_plan_twice(layout, preset, theme):
    style = core.Style(layout, preset, theme)
    card = by_n(1)
    first = core.build_plan(card, style)
    second = core.build_plan(card, style)
    assert first == second
    assert first["report"]["sizes"]["title"] > 0
    assert row_texts(first), (layout, preset, theme)


def test_line_breaks_keep_every_word_in_order():
    style = core.Style("stacked", "casual", "color")
    plan = core.build_plan(by_n(2), style)
    words = " ".join(row_texts(plan)).split()
    expected = []
    for line in by_n(2)["lines"]:
        expected.extend(line["text"].split())
        if line.get("note"):
            expected.extend(line["note"].split())
    assert words == expected


def test_a_short_card_fits_at_its_default_sizes():
    style = core.Style("stacked", "casual", "color")
    plan = core.build_plan(by_n(1), style)
    assert plan["report"]["failed"] is False
    assert plan["report"]["shrunk"] is False
    assert plan["report"]["sizes"] == {role: style.layout["font_sizes"][role]
                                       for role in SIZES}


def test_a_card_that_needs_one_step_still_fits():
    # The fixture's card 3 covers shrink-to-the-floor and failure. A card one
    # line longer than card 2 needs one shrink step and still fits, so the
    # report can say "shrunk" without "failed".
    style = core.Style("stacked", "casual", "color")
    card = copy.deepcopy(by_n(2))
    card["lines"] = list(card["lines"]) + [
        {"text": "Keep going even when the week is busy and the plan slips.",
         "mark": None, "note": "The plan is a direction, not a test."}]
    plan = core.build_plan(card, style)
    report = plan["report"]
    assert report["shrunk"] is True
    assert report["failed"] is False
    assert report["sizes"]["lines"] < style.layout["font_sizes"]["lines"]
    assert report["sizes"]["lines"] >= style.layout["font_floors"]["lines"]


def test_the_long_card_fails_at_the_floor_not_below_it():
    style = core.Style("stacked", "casual", "color")
    plan = core.build_plan(by_n(3), style)
    assert plan["report"]["failed"] is True
    assert plan["report"]["shrunk"] is True
    assert plan["report"]["sizes"]["lines"] == style.layout["font_floors"]["lines"]
    assert plan["report"]["sizes"]["notes"] == style.layout["font_floors"]["notes"]


def test_professional_draws_the_swash_as_a_straight_underline():
    style = core.Style("stacked", "professional", "color")
    plan = core.build_plan(by_n(1), style)
    assert plan["marks"], "card 1 has three marks"
    for shape in plan["marks"]:
        assert shape["type"] == "polyline"
        assert len(shape["points"]) == 2
        assert shape["points"][0][1] == shape["points"][1][1]


def test_wobble_zero_is_geometric_and_wobble_one_is_seeded():
    calm = core.swash_points(200, 2.4, 5, 8, 6, 2.2, seed=7, wobble=0)
    assert core.swash_points(200, 2.4, 5, 8, 6, 2.2, seed=99, wobble=0) == calm
    assert core.swash_points(200, 2.4, 5, 8, 6, 2.2, seed=7, wobble=1) != calm
    hand = core.underline_points(200, 1.4, seed=7, wobble=0)
    assert len(hand) == 2 and hand[0][1] == hand[1][1] == 0.0


def test_a_deck_token_overrides_the_preset_mark_wobble():
    # SPEC section 7 calls mark wobble a token, so style.tokens can set it to
    # 0 for clean geometric marks, whatever the preset says.
    default = core.Style("stacked", "casual", "color")
    assert default.wobble() == 1
    calm = core.Style("stacked", "casual", "color", {"mark_wobble": 0})
    assert calm.wobble() == 0
    assert core.build_plan(by_n(1), calm)["marks"] != core.build_plan(by_n(1), default)["marks"]
    assert core.Style("stacked", "professional", "color").wobble() == 0


def test_mark_seed_is_keyed_to_the_card_and_line():
    assert core.mark_seed(1, 0) != core.mark_seed(2, 0)
    assert core.mark_seed(1, 0) != core.mark_seed(1, 1)
    a = [core.mulberry32(core.mark_seed(3, 1))() for _ in range(4)]
    b = [core.mulberry32(core.mark_seed(3, 1))() for _ in range(4)]
    assert a == b
    assert all(0 <= value < 1 for value in a)


def test_notebook_and_index_carry_numbered_marks_and_badges():
    for layout in ("notebook", "index"):
        plan = core.build_plan(by_n(1), core.Style(layout, "casual", "color"))
        assert plan["badges"], layout
        assert all(badge["text"].isdigit() for badge in plan["badges"]), layout


def test_week_of_follows_the_deck_numbering_rules():
    def deck(**number):
        return {"created": "2026-01-01", "numbering": dict(mode="weekly", **number)}

    assert core.week_of({"created": "2026-01-01"}, 1) == ""
    # January 1 2026 is a Thursday; a Sunday week 1 starts December 28 2025.
    assert core.week_of(deck(), 1) == "2025-12-28"
    assert core.week_of(deck(), 2) == "2026-01-04"
    assert core.week_of(deck(week_start="monday"), 1) == "2025-12-29"
    # ISO week 1 is the week containing January 4, starting Monday.
    assert core.week_of(deck(week_rule="iso8601"), 1) == "2025-12-29"
    assert core.week_of(deck(week_rule="iso8601"), 2) == "2026-01-05"
    # December 30 2025 is ISO week 1 of 2026.
    early = {"created": "2025-12-30",
             "numbering": {"mode": "weekly", "week_rule": "iso8601"}}
    assert core.week_of(early, 1) == "2025-12-29"


def test_fit_report_is_generated_and_lists_every_case():
    deck = core.load_deck(DECK)
    style = core.style_from_deck(deck)
    report = core.fit_report(deck, cards(), "pillow", style)
    public = core.public_report(report)
    assert public["note"] == "Generated by scripts/render_pillow.py. Do not edit by hand."
    assert public["hand_edits"] == [4]
    assert public["private_omitted"] == [5]
    assert [entry["n"] for entry in public["cards"] if entry["failed"]] == [3]
    assert [entry["n"] for entry in public["cards"] if entry.get("hand_edited")] == [4]
    schema = json.loads((CORE / "schemas/fit_report.schema.json").read_text())
    Draft202012Validator(schema).validate(public)


def test_the_summary_names_the_cards_that_need_attention():
    deck = core.load_deck(DECK)
    style = core.style_from_deck(deck)
    report = core.fit_report(deck, cards(), "pillow", style)
    summary = core.summary(report)
    assert "Shrunk to fit: cards 3." in summary
    assert "Still too long at the smallest size: cards 3." in summary
    assert "Edited by hand since approval: cards 4." in summary
    assert "Left out of fridge and lock-screen output for visibility: cards 5." in summary

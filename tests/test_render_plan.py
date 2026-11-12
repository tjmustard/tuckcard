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


def test_a_marked_phrase_wider_than_the_line_region_wraps_in_parts():
    # Before the width check, the wrapper glued the whole phrase into one chunk
    # and drew it through the notebook notes column while the report still said
    # the card fitted. A phrase wider than the region now wraps normally.
    style = core.Style("notebook", "casual", "color")
    region = style.region("lines")
    limit = min(region["w"], style.region("notes")["x"] - region["x"])
    family, weight = style.font("lines")
    size = style.layout["font_sizes"]["lines"]
    phrase = "one two three four five six seven eight nine ten eleven twelve thirteen"
    assert core.advance(phrase, family, weight, size) > limit

    card = copy.deepcopy(by_n(1))
    card["lines"] = [{"text": "Before " + phrase + " after.",
                      "mark": {"target": phrase}, "note": None}]
    plan = core.build_plan(card, style)
    rows = plan["body"]["lines"]
    outside = [row for row in rows for run in row["runs"]
               if row["x"] - region["x"] + run["x"] + run["width"] > limit + 0.5]
    assert not outside or plan["report"]["failed"] is True
    assert plan["report"]["failed"] is False
    marked_rows = [row for row in rows if any(run["marked"] for run in row["runs"])]
    assert len(marked_rows) >= 2


def test_the_restyled_card_seven_line_wraps_inside_the_notebook_region():
    # The high-school card 7 line, in the style the restyle pass uses. At
    # 93529ec the wrapper glued "where you are" and drew the line 49 px into
    # the notes column while the report said it fitted. It now wraps.
    style = core.Style("notebook", "professional", "mono")
    region = style.region("lines")
    limit = min(region["w"], style.region("notes")["x"] - region["x"])
    card = copy.deepcopy(by_n(1))
    card["lines"] = [{
        "text": "Being bad at something says where you are, not where you stop.",
        "mark": {"target": "where you are"},
        "note": "a starting point can move"}]
    plan = core.build_plan(card, style)
    ends = [row["x"] - region["x"] + run["x"] + run["width"]
            for row in plan["body"]["lines"] for run in row["runs"]]
    assert max(ends) <= limit + 0.5
    assert plan["report"]["failed"] is False


def test_an_unbreakable_word_wider_than_the_region_is_a_failure():
    style = core.Style("notebook", "casual", "color")
    region = style.region("lines")
    family, weight = style.font("lines")
    size = style.layout["font_floors"]["lines"]
    word = "supercalifragilisticexpialidocioussupercalifragilisticexpialidocious"
    assert core.advance(word, family, weight, size) > region["w"]

    card = copy.deepcopy(by_n(1))
    card["lines"] = [{"text": word, "mark": {"target": word}, "note": None}]
    plan = core.build_plan(card, style)
    assert plan["report"]["failed"] is True


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


def title_with_rows(rows, style):
    """A title that wraps to exactly ``rows`` lines at the default title size."""
    family, weight = style.font("title")
    width = style.region("title")["w"]
    size = style.layout["font_sizes"]["title"]
    for count in range(1, 200):
        title = " ".join(["Steady"] * count)
        lines = core._wrap(title.split(), family, weight, size, width, set())
        if len(lines) == rows:
            return title
    raise AssertionError("no title wraps to %d rows" % rows)


@pytest.mark.parametrize("rows,title_size,failed", [
    (1, 33, False),
    (2, 33, False),
    (3, 27, True),
    (4, 27, True),
])
def test_the_stacked_title_must_end_before_the_body(rows, title_size, failed):
    # The stacked title region is 0.740 in, the space between its top edge and
    # the body's top edge. A one- or two-line title still fits at 33 px because
    # a title that ends on the body's top edge touches it, not intrudes.
    style = core.Style("stacked", "casual", "color")
    card = copy.deepcopy(by_n(1))
    card["title"] = title_with_rows(rows, style)
    card["lines"] = [{"text": "One short line.", "mark": None, "note": None}]
    plan = core.build_plan(card, style)
    report = plan["report"]
    assert report["sizes"]["title"] == title_size
    assert report["failed"] is failed
    if not failed:
        fitted = max(run["row"] for run in plan["title"]["runs"]) + 1
        bottom = plan["title"]["y"] + fitted * plan["title"]["line_height"]
        assert bottom <= plan["body"]["y"] + 0.5


def test_a_four_row_title_with_a_short_body_is_reported_as_failed():
    # The case the old predicate missed: the body fits, so the card reported
    # failed: false while its fourth title line painted over the body.
    style = core.Style("stacked", "casual", "color")
    card = copy.deepcopy(by_n(1))
    card["title"] = title_with_rows(4, style)
    card["lines"] = [{"text": "One short line.", "mark": None, "note": None}]
    plan = core.build_plan(card, style)
    assert plan["report"]["failed"] is True
    assert plan["body"]["height"] <= style.region("body")["h"]


def test_no_fitting_card_paints_its_title_over_the_body():
    style = core.Style("stacked", "casual", "color")
    for card in cards():
        plan = core.build_plan(card, style)
        if plan["report"]["failed"]:
            continue
        rows = max(run["row"] for run in plan["title"]["runs"]) + 1
        bottom = plan["title"]["y"] + rows * plan["title"]["line_height"]
        assert bottom <= plan["body"]["y"] + 0.5, card["n"]


LONG_PILL = "A very long age label that should never fit the header line"
PILL_CASES = (
    "A very long age label that should… never fit the header line",
    "A very long … age label that should never fit the header line",
    "A very long age label that should never fit…",
    "…" * 40,
    "\U0001d544" * 60,
    "\U0001f600" * 20,
    "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466" * 8,
    "\U0001f1fa\U0001f1f8" * 20,
    "é" * 30,
    "\U0001f44b\U0001f3fd" * 10,
    "\U0001f393" * 12,
    "Class of 2026 \U0001f393 and friends \U0001f469‍\U0001f469‍\U0001f467 " * 3,
)
# The cases whose kept prefix is a literal slice of the pill, so the
# longest-cut check can append one more cluster and expect it to overflow.
SLICE_CASES = (
    "\U0001d544" * 60,
    "\U0001f600" * 20,
    "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466" * 8,
    "\U0001f1fa\U0001f1f8" * 20,
    "é" * 30,
    "\U0001f44b\U0001f3fd" * 10,
    "\U0001f393" * 12,
)


def pill_card(pill):
    card = copy.deepcopy(by_n(1))
    card["pill"] = pill
    return card


def grapheme_end(points, cut):
    """The index after the cluster that starts at ``cut``."""
    end = cut + 1
    while end < len(points):
        if points[end] == core.ZWJ:
            end += 1
            if end < len(points):
                end += 1
            continue
        if core._is_continuation(points[end]):
            end += 1
            continue
        break
    if (core._is_regional_indicator(points[cut]) and end < len(points)
            and core._is_regional_indicator(points[end])):
        end += 1
    return end


def test_an_over_long_pill_keeps_one_ellipsis_and_a_whole_grapheme():
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        for pill in PILL_CASES:
            card = pill_card(pill)
            label = core.header_label(card, style)
            room = core.header_room(card, style)
            full = "Growth · " + pill
            if core.tracked_width(full.upper()) <= room:
                assert label == full, (layout, pill)
                continue
            assert label.count(core.ELLIPSIS) == 1, (layout, pill)
            assert label.endswith(core.ELLIPSIS), (layout, pill)
            assert "�" not in label, (layout, pill)
            assert not any(0xD800 <= ord(ch) <= 0xDFFF for ch in label), (layout, pill)
            label.encode("utf-8")
            assert core.tracked_width(label.upper()) <= room, (layout, pill)
            prefix = label[len("Growth · "):-len(core.ELLIPSIS)]
            assert core._safe_cut(list(pill), len(prefix)) == len(prefix), (layout, pill)
            assert not prefix.endswith(core.ZWJ), (layout, pill)


def test_the_cut_keeps_the_longest_prefix_that_fits():
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        for pill in SLICE_CASES:
            card = pill_card(pill)
            room = core.header_room(card, style)
            if core.tracked_width(("Growth · " + pill).upper()) <= room:
                continue
            label = core.header_label(card, style)
            prefix = label[len("Growth · "):-len(core.ELLIPSIS)]
            points = list(pill)
            assert pill.startswith(prefix), (layout, pill)
            cut = len(prefix)
            assert cut < len(points), (layout, pill)
            end = grapheme_end(points, cut)
            wider = "Growth · " + "".join(points[:end]) + core.ELLIPSIS
            assert core.tracked_width(wider.upper()) > core.header_room(card, style), (
                layout, pill)



def test_a_short_pill_is_unchanged():
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        assert core.header_label(by_n(1), style) == "Growth · High School", layout


def test_a_pill_that_exactly_fits_is_unchanged():
    # The longest run of "x" that fits is untouched; one more character is
    # cut to a single ellipsis and still fits. This is the boundary the rule
    # turns on, not a width tolerance.
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        card = copy.deepcopy(by_n(1))
        room = core.header_room(card, style)
        fixed = "Growth · "
        length = 0
        while core.tracked_width((fixed + "x" * (length + 1)).upper()) <= room:
            length += 1
        assert length > 0, layout
        card["pill"] = "x" * length
        assert core.header_label(card, style) == fixed + "x" * length, layout
        card["pill"] = "x" * (length + 1)
        label = core.header_label(card, style)
        assert label.endswith(core.ELLIPSIS), layout
        assert label.count(core.ELLIPSIS) == 1, layout
        assert core.tracked_width(label.upper()) <= room, layout


def test_a_long_pill_is_truncated_without_moving_the_header_or_body():
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        card = copy.deepcopy(by_n(1))
        card["pill"] = LONG_PILL
        label = core.header_label(card, style)
        assert label.startswith("Growth · A very long"), layout
        assert label.endswith(core.ELLIPSIS), layout
        assert label.count(core.ELLIPSIS) == 1, layout
        assert core.tracked_width(label.upper()) <= core.header_room(card, style), layout

        long_plan = core.build_plan(card, style)
        short_plan = core.build_plan(by_n(1), style)
        assert long_plan["labels"]["header"] == label
        # Only the header string changes: every box, size and row is the same,
        # so the header height and the body position cannot move.
        long_rest = copy.deepcopy(long_plan)
        short_rest = copy.deepcopy(short_plan)
        long_rest["labels"] = short_rest["labels"] = None
        assert long_rest == short_rest, layout
        # Same deck, same bytes: the cut is a pure function of the card.
        assert core.build_plan(copy.deepcopy(card), style)["labels"] == \
            long_plan["labels"], layout


def test_the_header_room_leaves_the_watermark_and_number_clear():
    # Stacked and index reserve the right-hand element; notebook draws its
    # number on a higher baseline, so its header may use the whole region.
    for layout in LAYOUTS:
        style = core.Style(layout, "casual", "color")
        card = by_n(1)
        room = core.header_room(card, style)
        region_width = style.region("header")["w"]
        if layout == "notebook":
            assert room == core.whole_px(region_width)
        else:
            assert room < region_width, layout


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
    assert "These cards were edited by hand and not linted since: cards 4." in summary
    assert "cards-review" in summary
    assert "Left out of fridge and lock-screen output for visibility: cards 5." in summary
    assert report["hand_edits_note"] == (
        "Edited by hand, not linted since. Run cards-review on these cards "
        "to clear the flag.")

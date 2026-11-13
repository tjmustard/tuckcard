"""A hand-edited card reaches the fit report. SPEC.md section 2, Approval enforcement."""

import copy
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/tuckcard/skills/cards-core/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import approval_hash  # noqa: E402
import render_core as core  # noqa: E402

DECK = ROOT / "plugins/tuckcard/skills/cards-core/examples/parity-fixture/deck.yaml"


def fixture():
    return core.load_deck(DECK)


def card(number):
    return copy.deepcopy(next(c for c in fixture()["cards"] if c["n"] == number))


def approved(number=1):
    """A card whose approval record matches its current content."""
    one = card(number)
    one["approval"] = {"approved_hash": approval_hash.card_hash(one),
                       "linted_hash": approval_hash.card_hash(one),
                       "approved_by": "round"}
    return one


def report(cards):
    deck = fixture()
    return core.fit_report(deck, cards, "pillow", core.style_from_deck(deck))


def test_a_rewritten_card_is_listed_in_the_fit_report():
    edited = approved()
    edited["lines"][0]["text"] = "You cannot do it yet."
    result = report([edited])
    assert result["hand_edits"] == [1]
    assert result["cards"][0]["hand_edited"] is True
    assert result["hand_edits_note"] == core.HAND_EDITS_NOTE
    summary = core.summary(result)
    assert "edited by hand" in summary
    assert "not linted since" in summary
    assert "cards-review" in summary
    assert "cards 1" in summary


def test_an_untouched_card_is_not_listed():
    result = report([approved()])
    assert result["hand_edits"] == []
    assert "hand_edited" not in result["cards"][0]
    assert "hand_edits_note" not in result


def test_a_card_with_no_approval_block_is_not_a_hand_edit():
    one = card(1)
    one.pop("approval", None)
    result = report([one])
    assert result["hand_edits"] == []
    assert "hand_edited" not in result["cards"][0]


def test_a_card_marked_hand_edit_is_listed_even_when_its_hash_matches():
    one = approved()
    one["approval"]["approved_by"] = "hand-edit"
    result = report([one])
    assert result["hand_edits"] == [1]
    assert result["cards"][0]["hand_edited"] is True


def test_a_matching_linted_hash_is_enough():
    one = approved()
    one["approval"]["approved_hash"] = "0" * 64
    result = report([one])
    assert result["hand_edits"] == []

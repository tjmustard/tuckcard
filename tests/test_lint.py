"""Lint: the checks cards-draft and cards-review call, with planted cases."""

import json

import support
import lint

FIXTURES = support.FIXTURES / "lint"
CLEAN = FIXTURES / "clean.deck.yaml"
PLANTED = FIXTURES / "planted.deck.yaml"
RULES = FIXTURES / "effective-rules.yaml"
FINDINGS = FIXTURES / "findings"


def card(number, title="A title", lines=("A line of copy.",), **changes):
    data = {
        "n": number,
        "category": "habits",
        "title": title,
        "lines": [{"text": text, "mark": None, "note": None} for text in lines],
        "basis": ["R-core-L001"],
        "visibility": "public",
    }
    data.update(changes)
    return data


def deck(cards, **changes):
    data = {
        "id": "lint-unit",
        "status": "drafted",
        "style": {"layout": "stacked", "preset": "casual", "theme": "color"},
        "recipient": {"age_band": "high-school"},
        "cards": cards,
    }
    data.update(changes)
    return data


def rule(rule_id="R-core-L001", **changes):
    data = {
        "id": rule_id,
        "strength": "must",
        "applies_to": ["lines"],
        "text": "Do not use the word never.",
        "why": "Absolute words undercut the tone.",
        "lint": {"pattern": "\\bnever\\b"},
        "check": "lint",
    }
    data.update(changes)
    return data


def test_a_clean_fixture_passes(capsys):
    code = lint.main([str(CLEAN), "--rules", str(RULES), "--findings", str(FINDINGS),
                      "--no-default-overlay"])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 errors, 0 warnings" in out
    assert "reading targets are not set" in out


def test_the_planted_error_and_warning_are_caught(capsys):
    code = lint.main([str(PLANTED), "--rules", str(RULES), "--findings", str(FINDINGS),
                      "--no-default-overlay"])
    out = capsys.readouterr().out
    assert code == 1
    assert "error: card 1 lines: matches 'never'" in out
    assert "[R-core-L001]" in out
    assert "warning: card 2 lines: line repeats card 1" in out


def test_json_report_names_the_findings_and_hand_edits(capsys):
    code = lint.main([str(PLANTED), "--rules", str(RULES), "--findings", str(FINDINGS),
                      "--no-default-overlay", "--json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["cards_checked"] == 2
    assert any(item["check"] == "rules" and item["rule"] == "R-core-L001"
               for item in report["findings"])
    assert any(item["check"] == "repetition" for item in report["findings"])
    assert report["hand_edited"] == []


def test_cards_selection_limits_the_checks():
    findings, _ = lint.check_rules([rule()], [card(1, lines=("never again",)), card(2)],
                                   {2})
    assert findings == []


def test_strength_decides_the_level():
    cards = [card(1, lines=("You never know",))]
    errors, _ = lint.check_rules([rule(strength="must")], cards, None)
    warnings, _ = lint.check_rules([rule(strength="should")], cards, None)
    assert [item["level"] for item in errors] == ["error"]
    assert [item["level"] for item in warnings] == ["warning"]


def test_judge_rules_are_left_to_the_model():
    cards = [card(1, lines=("You never know",))]
    findings, notes = lint.check_rules([rule(check="judge")], cards, None)
    assert findings == [] and notes == []


def test_applies_to_and_categories_scope_a_rule():
    cards = [card(1, title="Never settle", lines=("A line.",), category="growth")]
    by_field, _ = lint.check_rules([rule()], cards, None)
    by_category, _ = lint.check_rules([rule(categories=["habits"])], cards, None)
    assert by_field == []
    assert by_category == []


def test_a_broken_pattern_is_a_note_not_a_crash():
    findings, notes = lint.check_rules(
        [rule(lint={"pattern": "("})], [card(1)], None)
    assert findings == []
    assert notes and "does not compile" in notes[0]


def test_format_limits_come_from_the_band_file():
    defaults = {"card": {"max_title_words": 2, "max_lines": 1, "max_words_per_line": 3}}
    findings = lint.check_format(
        [card(1, title="Three words here", lines=("one two three four", "second"))],
        defaults, None,
    )
    messages = [item["message"] for item in findings]
    assert any("title is 3 words" in message for message in messages)
    assert any("card has 2 lines" in message for message in messages)
    assert any("line is 4 words" in message for message in messages)


def test_reading_targets_warn_only_when_set():
    cards = [card(1, lines=("Extraordinarily complicated terminology appears.",))]
    empty, notes = lint.check_reading(cards, {"reading": {}}, None, None)
    strict, _ = lint.check_reading(
        cards, {"reading": {"max_avg_syllables_per_word": 1.0,
                            "deck_fk_grade_warning": 1.0}}, None, None)
    assert empty == [] and notes
    assert any("syllables per word" in item["message"] for item in strict)
    assert any("deck reads at grade" in item["message"] for item in strict)


def test_syllables_and_grade_are_stable_estimates():
    assert [lint.syllables(word) for word in ("cat", "table", "extraordinary")] == [1, 2, 5]
    assert lint.flesch_kincaid_grade("") is None
    assert lint.flesch_kincaid_grade("We start small. We keep going.") < 5


def test_the_familiarity_list_flags_unknown_words(tmp_path):
    words = tmp_path / "words.txt"
    words.write_text("a\nline\ncopy\n# a comment\n", encoding="utf-8")
    age = tmp_path / "age.yaml"
    age.write_text("defaults:\n  reading:\n    familiarity_list: words.txt\n",
                   encoding="utf-8")
    findings, notes = lint.check_reading(
        [card(1, lines=("A line of copy with jargon",))],
        {"reading": {"familiarity_list": "words.txt"}}, age, None,
    )
    assert any("jargon" in item["message"] for item in findings)
    assert notes == []


def test_help_resources_must_match_a_verified_finding():
    resources = lint.verified_help([{
        "id": "L-9001", "status": "active", "grade": "D",
        "claim": "A helpline answers calls.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch", "anchor": "Call 1-800-555-0100."},
    }])
    good = [card(1, lines=("Call 1-800-555-0100 or see https://example.org/helpline.",
                           ))]
    bad = [card(1, lines=("Call 1-800-555-0199 or see https://example.org/other.",))]
    assert lint.check_help(good, resources, None) == []
    found = lint.check_help(bad, resources, None)
    assert len(found) == 2
    assert {item["level"] for item in found} == {"error"}


def test_a_partial_number_does_not_match_a_resource():
    resources = lint.verified_help([{
        "id": "L-9001", "status": "active", "grade": "D",
        "claim": "A helpline answers calls.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch", "anchor": "Call 1-800-273-8255."},
    }])
    found = lint.check_help(
        [card(1, lines=("Call 273-8255 and keep going.",))], resources, None)
    assert [item["message"] for item in found] == [
        "phone number 2738255 does not match a verified help resource exactly"]


def test_a_leading_country_code_may_be_omitted():
    resources = lint.verified_help([{
        "id": "L-9001", "status": "active", "grade": "D",
        "claim": "A helpline answers calls.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch", "anchor": "Call 1-800-273-8255."},
    }])
    with_code = [card(1, lines=("Call 1-800-273-8255.",))]
    without_code = [card(1, lines=("Call 800-273-8255.",))]
    assert lint.check_help(with_code, resources, None) == []
    assert lint.check_help(without_code, resources, None) == []


def test_a_leading_one_does_not_bridge_different_numbers():
    resources = lint.verified_help([{
        "id": "L-9001", "status": "active", "grade": "D",
        "claim": "A helpline answers calls.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch", "anchor": "Call 988-273-8255."},
    }])
    found = lint.check_help(
        [card(1, lines=("Call 1-800-273-8255.",))], resources, None)
    assert [item["message"] for item in found] == [
        "phone number 18002738255 does not match a verified help resource exactly"]


def test_short_codes_are_read_as_phone_numbers():
    found = lint.check_help(
        [card(1, lines=("Call 988 or 911, or dial 988 911.",))], [], None)
    values = {item["message"].split()[2] for item in found}
    assert values == {"988", "911"}
    resources = lint.verified_help([{
        "id": "L-9001", "status": "active", "grade": "D",
        "claim": "Call 988 or 911 at any hour.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch", "anchor": "Call 988 or 911."},
    }])
    assert lint.check_help(
        [card(1, lines=("Call 988 or 911.",))], resources, None) == []


def test_a_formatted_seven_digit_number_is_seen():
    found = lint.check_help([card(1, lines=("Call 555-0100.",))], [], None)
    assert [item["message"] for item in found] == [
        "phone number 5550100 does not match a verified help resource exactly"]


def test_date_shapes_are_not_phone_numbers():
    cards = [card(1, lines=("Tryouts run 11-11-2026 for the 2026-2027 season.",
                            "The form is due 2026-11-11.",
                            "The window is 2025 - 2026 and 2025 – 2026; "
                            "sign by 11 - 11 - 2026."))]
    assert lint.check_help(cards, [], None) == []


def test_real_numbers_are_still_phone_numbers():
    cards = [card(1, lines=("Call 555-0100, 1-800-273-8255, 988 or 911; "
                            "local 5550-0100 or 555 - 0100.",))]
    found = lint.check_help(cards, [], None)
    values = {item["message"].split()[2] for item in found}
    assert values == {"5550100", "18002738255", "988", "911", "55500100"}


def test_a_year_a_score_and_a_url_digit_are_not_phone_numbers():
    cards = [card(1, lines=("In 2026, 98 out of 100; the score was 3-2; "
                            "see https://example.org/2026.",))]
    found = lint.check_help(cards, [], None)
    assert len(found) == 1
    assert found[0]["message"].startswith("URL ")


def test_an_unverified_finding_does_not_authorise_a_url():
    resources = lint.verified_help([{
        "id": "F-0001", "status": "provisional", "grade": "D",
        "claim": "A helpline answers calls.",
        "source": {"url": "https://example.org/helpline"},
        "verification": {"exists": "fetch"},
    }])
    assert resources == []


def test_visibility_keeps_a_confirmed_detail_off_a_public_card():
    public_deck = deck([card(1, lines=("Plays on the school team.",))],
                       personal_details=[{"id": "P-01",
                                          "text": "Plays on the school team.",
                                          "confirmed": True}])
    private_deck = deck([card(1, lines=("Plays on the school team.",),
                              visibility="private")],
                        personal_details=public_deck["personal_details"])
    assert len(lint.check_visibility(public_deck["cards"], public_deck, None)) == 1
    assert lint.check_visibility(private_deck["cards"], private_deck, None) == []


def test_repetition_flags_duplicates_and_example_reuse():
    cards = [card(1, lines=("Same line.",)), card(2, lines=("Same line.",))]
    found = lint.check_repetition(cards, {"same line": "parity-fixture"}, None)
    messages = [item["message"] for item in found]
    assert "line repeats card 1" in messages
    assert any("reused verbatim" in message for message in messages)


def test_hand_edits_compare_the_covered_fields():
    edited = card(1)
    edited["approval"] = {"approved_hash": lint.card_hash(edited),
                          "linted_hash": lint.card_hash(edited)}
    untouched, edited_numbers = lint.check_hand_edits([edited], None)
    assert untouched == [] and edited_numbers == []

    edited["lines"][0]["text"] = "Changed after approval."
    found, edited_numbers = lint.check_hand_edits([edited], None)
    assert edited_numbers == [1]
    assert found[0]["check"] == "hand-edit"


def test_the_hash_ignores_number_basis_and_notes_beside_covered_fields():
    first = card(1)
    second = dict(first)
    second["basis"] = ["R-core-J001"]
    assert lint.card_hash(first) == lint.card_hash(second)


def test_fit_is_checked_when_the_renderer_is_available():
    findings, notes = lint.check_fit(deck([card(1)]), [card(1)], None)
    try:
        import render_core  # noqa: F401
    except Exception:  # noqa: BLE001
        assert findings == [] and notes
    else:
        assert findings == []


def test_a_missing_rules_snapshot_stops_the_run(tmp_path):
    deck_path = tmp_path / "deck.yaml"
    deck_path.write_text(CLEAN.read_text(), encoding="utf-8")
    try:
        lint.main([str(deck_path), "--no-default-overlay"])
    except SystemExit as exit_error:
        assert "no rules snapshot" in str(exit_error)
    else:  # pragma: no cover - the exit is the assertion
        raise AssertionError("lint accepted a deck with no compiled rules")

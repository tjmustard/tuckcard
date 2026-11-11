"""Behaviour the schemas cannot express: deck cross-file checks and CLI choices."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "plugins/tuckcard/skills/cards-core/scripts/validate.py"
VALID = ROOT / "tests/fixtures/valid"
INVALID = ROOT / "tests/fixtures/invalid"


def run(paths, extra=()):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return subprocess.run(
        [sys.executable, str(VALIDATE), *map(str, paths), *extra],
        capture_output=True,
        text=True,
    )


def load_validate_module():
    spec = importlib.util.spec_from_file_location("tuckcard_validate", VALIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deck_copy(tmp_path, snapshot=None):
    deck = tmp_path / "deck.yaml"
    shutil.copy(VALID / "deck.fixture.yaml", deck)
    if snapshot is None:
        shutil.copy(VALID / "effective-rules.yaml", tmp_path / "effective-rules.yaml")
    else:
        (tmp_path / "effective-rules.yaml").write_text(snapshot, encoding="utf-8")
    return deck


def test_basis_rule_missing_from_snapshot_names_card_and_rule(tmp_path):
    deck = deck_copy(tmp_path, snapshot="rules:\n  - id: R-core-001\n")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/cards/1/basis/1" in result.stdout
    assert "card 2" in result.stdout
    assert "R-high-school-001" in result.stdout


def test_mark_without_note_is_rejected(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "        note: Starting beats waiting for motivation.",
        "        note: null",
    )
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/cards/0/lines/0/note" in result.stdout


def test_mark_occurrence_beyond_matches_is_rejected(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "          target: first two minutes",
        "          target: first two minutes\n          occurrence: 3",
    )
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/cards/0/lines/0/mark/target" in result.stdout
    assert "occurs 1 time(s), occurrence is 3" in result.stdout


def test_snapshot_missing_skips_the_basis_check(tmp_path):
    deck = tmp_path / "deck.yaml"
    shutil.copy(VALID / "deck.fixture.yaml", deck)
    result = run(deck)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "basis check skipped" in result.stdout


def test_schema_override_applies(tmp_path):
    deck = tmp_path / "deck.yaml"
    shutil.copy(VALID / "deck.fixture.yaml", deck)
    result = run(deck, ("--schema", "card"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "'n' is a required property" in result.stdout


def test_unrecognised_file_asks_for_a_schema(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("plain text\n", encoding="utf-8")
    result = run(notes)
    assert result.returncode == 1
    assert "could not pick a schema" in result.stdout


def test_one_failure_makes_the_whole_run_fail():
    result = run([VALID / "card.yaml", INVALID / "card.yaml"])
    assert result.returncode == 1
    assert "valid (card)" in result.stdout
    assert "/visibility" in result.stdout


def test_snapshot_with_no_rule_ids_reports_the_skip(tmp_path):
    deck = deck_copy(tmp_path, snapshot="# no rules here\n")
    result = run(deck)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "basis check skipped" in result.stdout
    assert "no rule ids" in result.stdout


def test_age_band_ladder_rejects_a_value_the_band_does_not_allow(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "age_band: high-school", "age_band: grade-school"
    ).replace("substances: omit", "substances: harm_reduction")
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/policies/substances" in result.stdout
    assert "grade-school" in result.stdout
    assert "harm_reduction" in result.stdout


def test_unlisted_age_band_allows_only_omit_for_sensitive_topics(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "age_band: high-school", "age_band: overlay-band"
    ).replace("substances: omit", "substances: safety_only")
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/policies/substances" in result.stdout
    assert "overlay-band" in result.stdout


def test_unlisted_age_band_accepts_omit(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "age_band: high-school", "age_band: overlay-band"
    )
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unresolvable_ref_is_one_line_naming_the_ref():
    module = load_validate_module()
    errors = module.schema_errors_for(
        {}, {"$ref": "https://tuckcard.local/schemas/common.schema.json"}
    )
    assert len(errors) == 1, errors
    assert errors[0].startswith("/: could not resolve a $ref:")
    assert "common.schema.json" in errors[0]


def _deck_with_snapshot(tmp_path):
    deck = tmp_path / "deck.yaml"
    shutil.copy(VALID / "deck.fixture.yaml", deck)
    shutil.copy(VALID / "effective-rules.yaml", tmp_path / "effective-rules.yaml")
    return deck


def test_missing_policies_reports_the_ladder_skip(tmp_path, monkeypatch, capsys):
    module = load_validate_module()
    monkeypatch.setattr(module, "POLICIES_PATH", tmp_path / "missing-policies.yaml")
    deck = _deck_with_snapshot(tmp_path)
    assert module.main([str(deck)]) == 0
    out = capsys.readouterr().out
    assert "ladder check skipped" in out
    assert "not found" in out


def test_unreadable_policies_reports_the_ladder_skip(tmp_path, monkeypatch, capsys):
    module = load_validate_module()
    policies = tmp_path / "policies.yaml"
    policies.write_text("ladder: [\n", encoding="utf-8")
    monkeypatch.setattr(module, "POLICIES_PATH", policies)
    deck = _deck_with_snapshot(tmp_path)
    assert module.main([str(deck)]) == 0
    out = capsys.readouterr().out
    assert "ladder check skipped" in out
    assert "unreadable" in out


def test_card_category_must_be_declared_by_the_deck(tmp_path):
    deck = deck_copy(tmp_path)
    text = deck.read_text(encoding="utf-8").replace(
        "    category: habits", "    category: game-day", 1
    )
    deck.write_text(text, encoding="utf-8")
    result = run(deck)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/cards/0/category" in result.stdout
    assert "game-day" in result.stdout

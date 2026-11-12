"""The PII scan tool: whole-word matching, folders, explicit paths and exit codes."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pii_scan  # noqa: E402


def terms(tmp_path, *lines):
    path = tmp_path / "terms.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_clean_file_exits_zero(tmp_path, capsys):
    listing = terms(tmp_path, "Riverton", "blue kite")
    target = write(tmp_path, "deck.md", "A deck about ordinary practice.\n")
    assert pii_scan.main([str(target), "--terms", str(listing)]) == 0
    out = capsys.readouterr().out
    assert "0 hits" in out


def test_a_term_hit_names_path_and_line_and_exits_one(tmp_path, capsys):
    listing = terms(tmp_path, "# comment", "", "Riverton")
    target = write(tmp_path, "deck.md", "first line\nAt Riverton we ran.\n")
    assert pii_scan.main([str(target), "--terms", str(listing)]) == 1
    out = capsys.readouterr().out
    assert "{}:2: Riverton".format(target) in out
    assert "first line" not in out


def test_matching_is_case_insensitive_and_whole_word(tmp_path):
    listing = terms(tmp_path, "Riverton")
    target = write(tmp_path, "deck.md", "RIVERTON station\nRivertonians came\n")
    assert pii_scan.main([str(target), "--terms", str(listing)]) == 1


def test_a_multi_word_term_matches_as_a_phrase(tmp_path):
    listing = terms(tmp_path, "clear your plate")
    target = write(tmp_path, "deck.md", "Please clear   your plate.\nClear the table.\n")
    assert pii_scan.main([str(target), "--terms", str(listing)]) == 1


def test_a_folder_is_searched_recursively(tmp_path, capsys):
    listing = terms(tmp_path, "Riverton")
    write(tmp_path, "examples/a/deck.yaml", "x: Riverton\n")
    write(tmp_path, "examples/b/deck.yaml", "x: clean\n")
    assert pii_scan.main([str(tmp_path / "examples"), "--terms", str(listing)]) == 1
    out = capsys.readouterr().out
    assert "a/deck.yaml:1" in out
    assert "b/deck.yaml" not in out


def test_the_json_report_lists_each_hit(tmp_path, capsys):
    listing = terms(tmp_path, "Riverton")
    target = write(tmp_path, "deck.md", "Riverton\n")
    assert pii_scan.main([str(target), "--terms", str(listing), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["terms"] == 1
    assert report["hits"] == [{"path": str(target), "line": 1, "term": "Riverton"}]


def test_a_missing_terms_file_exits_two(tmp_path, capsys):
    assert pii_scan.main([str(tmp_path), "--terms", str(tmp_path / "nope.txt")]) == 2
    assert "could not read terms" in capsys.readouterr().out


def test_a_terms_file_with_no_terms_exits_two(tmp_path):
    listing = terms(tmp_path, "# only comments")
    assert pii_scan.main([str(tmp_path), "--terms", str(listing)]) == 2


def test_a_missing_target_exits_two(tmp_path):
    listing = terms(tmp_path, "Riverton")
    assert pii_scan.main([str(tmp_path / "gone"), "--terms", str(listing)]) == 2


def test_binary_files_are_skipped(tmp_path):
    listing = terms(tmp_path, "Riverton")
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\nRiverton")
    assert pii_scan.main([str(binary), "--terms", str(listing)]) == 0


def test_the_default_target_is_the_examples_folder(monkeypatch, tmp_path, capsys):
    listing = terms(tmp_path, "Riverton")
    examples = tmp_path / "examples"
    write(tmp_path, "examples/grade-school/deck.yaml", "Riverton\n")
    monkeypatch.setattr(pii_scan, "EXAMPLES", examples)
    assert pii_scan.main(["--terms", str(listing)]) == 1
    assert "grade-school/deck.yaml:1" in capsys.readouterr().out

"""Bundle: the section 6 tree, matching hashes and a stable re-bundle."""

import hashlib
import json
import shutil
import zipfile

import pytest

import support
import bundle

CREATED = "2026-11-11T12:00:00Z"


def deck_tree(tmp_path):
    """A deck folder with its compiled rules, and one overlay of every kind."""
    deck_dir = tmp_path / "deck"
    deck_dir.mkdir()
    deck = deck_dir / "deck.yaml"
    shutil.copy(support.DECK, deck)
    shutil.copy(support.FIXTURES / "valid/effective-rules.yaml",
                deck_dir / "effective-rules.yaml")
    (deck_dir / "review.md").write_text("# Review\n\nApproved.\n", encoding="utf-8")

    overlay = tmp_path / "local"
    findings = overlay / "knowledge/findings"
    findings.mkdir(parents=True)
    (findings / "L-9001.md").write_text("---\nid: L-9001\n---\nBody.\n", encoding="utf-8")
    (findings / "_TEMPLATE.md").write_text("template\n", encoding="utf-8")
    rules = overlay / "knowledge/rules"
    rules.mkdir(parents=True)
    (rules / "core.yaml").write_text("scope: core\nrules: []\n", encoding="utf-8")
    gaps = overlay / "knowledge/gaps"
    gaps.mkdir(parents=True)
    (gaps / "G-0001.md").write_text("# Gap\n", encoding="utf-8")
    themes = overlay / "themes"
    themes.mkdir()
    (themes / "navy.json").write_text("{}\n", encoding="utf-8")
    presets = overlay / "presets"
    presets.mkdir()
    (presets / "calm.json").write_text("{}\n", encoding="utf-8")
    return deck, overlay


def read_zip(path):
    with zipfile.ZipFile(str(path)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_the_bundle_holds_the_tree_its_manifest_and_matching_hashes(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    out = tmp_path / "deck.tuckcard.zip"
    path, manifest = bundle.bundle(deck, out, [overlay], "claude.ai", CREATED, None)

    files = read_zip(path)
    assert "manifest.json" in files
    assert set(files) == {"manifest.json"} | {item["path"] for item in manifest["files"]}
    for item in manifest["files"]:
        assert hashlib.sha256(files[item["path"]]).hexdigest() == item["sha256"]
    assert "deck/deck.yaml" in files
    assert "deck/effective-rules.yaml" in files
    assert "deck/review.md" in files
    assert "knowledge/findings/L-9001.md" in files
    assert "themes/navy.json" in files
    assert "presets/calm.json" in files
    assert not any("_TEMPLATE" in name for name in files)


def test_the_manifest_names_the_deck_overlay_and_personal_details(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    _, manifest = bundle.bundle(deck, tmp_path / "out.zip", [overlay],
                                "claude-code", CREATED, None)
    written = json.loads(read_zip(tmp_path / "out.zip")["manifest.json"])

    assert written == manifest
    assert manifest["schema_version"] == 1
    assert manifest["plugin_version"] == "0.1.0"
    assert manifest["created"] == CREATED
    assert manifest["platform"] == "claude-code"
    assert manifest["deck_id"] == "field-notes-demo"
    assert manifest["deck_status"] == "drafted"
    assert manifest["contains_personal_details"] is True
    assert manifest["overlay"] == {"findings": 1, "rules": 1, "gaps": 1,
                                   "themes": 1, "presets": 1}


def test_a_bundle_unzips_and_re_bundles_to_the_same_manifest(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    first = tmp_path / "first.tuckcard.zip"
    bundle.bundle(deck, first, [overlay], "claude.ai", CREATED, None)

    unpacked = tmp_path / "unpacked"
    with zipfile.ZipFile(str(first)) as archive:
        archive.extractall(str(unpacked))
    manifest = json.loads((unpacked / "manifest.json").read_text(encoding="utf-8"))

    second = tmp_path / "second.tuckcard.zip"
    _, rebuilt = bundle.bundle(unpacked / "deck/deck.yaml", second, [unpacked],
                               manifest["platform"], manifest["created"], None)

    stable = ("schema_version", "plugin_version", "created", "platform", "deck_id",
              "deck_status", "contains_personal_details", "overlay", "files")
    assert {key: rebuilt[key] for key in stable} == {key: manifest[key] for key in stable}
    assert second.read_bytes() == first.read_bytes()


def test_the_same_inputs_and_created_give_the_same_bytes(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    bundle.bundle(deck, first, [overlay], "claude.ai", CREATED, None)
    bundle.bundle(deck, second, [overlay], "claude.ai", CREATED, None)
    assert first.read_bytes() == second.read_bytes()


def test_renders_ride_after_the_deck_tree(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    renders = tmp_path / "renders"
    (renders / "print").mkdir(parents=True)
    (renders / "print" / "sheet.pdf").write_bytes(b"%PDF-1.4\n")
    path, manifest = bundle.bundle(deck, tmp_path / "out.zip", [overlay],
                                   "claude.ai", CREATED, renders)
    files = read_zip(path)
    assert files["renders/print/sheet.pdf"] == b"%PDF-1.4\n"
    assert {item["path"] for item in manifest["files"]} == set(files) - {"manifest.json"}


def test_a_relative_out_dir_takes_the_deck_id_name(tmp_path, monkeypatch):
    deck, overlay = deck_tree(tmp_path)
    monkeypatch.chdir(str(tmp_path))
    path, _ = bundle.bundle(deck, bundle.Path("bundles"), [overlay],
                            "claude.ai", CREATED, None)
    assert path == bundle.Path("bundles/field-notes-demo.tuckcard.zip")
    assert path.is_file()


def test_a_duplicate_bundle_path_is_refused(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    other = tmp_path / "other"
    (other / "knowledge/findings").mkdir(parents=True)
    (other / "knowledge/findings/L-9001.md").write_text("---\nid: L-9001\n---\n",
                                                        encoding="utf-8")
    with pytest.raises(bundle.BundleError) as error:
        bundle.bundle(deck, tmp_path / "out.zip", [overlay, other],
                      "claude.ai", CREATED, None)
    assert "comes from both" in str(error.value)


def test_a_source_outside_the_folders_is_refused(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    with pytest.raises(bundle.BundleError) as error:
        bundle.safe_copy(outside, tmp_path / "copy.txt", [allowed])
    assert "outside the deck and overlay folders" in str(error.value)


def test_a_missing_snapshot_is_refused(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    (deck.parent / "effective-rules.yaml").unlink()
    with pytest.raises(bundle.BundleError) as error:
        bundle.bundle(deck, tmp_path / "out.zip", [overlay], "claude.ai", CREATED, None)
    assert "rules snapshot" in str(error.value)


def test_an_invalid_deck_is_refused_before_writing(tmp_path):
    deck, overlay = deck_tree(tmp_path)
    deck.write_text("schema_version: 1\n", encoding="utf-8")
    with pytest.raises(bundle.BundleError) as error:
        bundle.bundle(deck, tmp_path / "out.zip", [overlay], "claude.ai", CREATED, None)
    assert "failed validation" in str(error.value)
    assert not (tmp_path / "out.zip").exists()


def test_created_is_normalised_to_utc(tmp_path):
    assert bundle.parse_created("2026-11-11T13:00:00+01:00") == "2026-11-11T12:00:00Z"
    assert bundle.parse_created("2026-11-11T12:00:00") == "2026-11-11T12:00:00Z"
    with pytest.raises(bundle.BundleError):
        bundle.parse_created("not a date")


def test_the_cli_reports_the_file_count_and_exits_zero(tmp_path, capsys):
    deck, overlay = deck_tree(tmp_path)
    code = bundle.main([str(deck), "--out", str(tmp_path / "out.zip"),
                        "--overlay", str(overlay), "--created", CREATED])
    out = capsys.readouterr().out
    assert code == 0
    assert "files" in out
    assert "field-notes-demo" in out


def test_the_cli_exits_one_with_one_line_on_a_refusal(tmp_path, capsys):
    deck, overlay = deck_tree(tmp_path)
    deck.write_text("schema_version: 1\n", encoding="utf-8")
    code = bundle.main([str(deck), "--out", str(tmp_path / "out.zip"),
                        "--overlay", str(overlay), "--created", CREATED])
    assert code == 1
    assert "failed validation" in capsys.readouterr().err

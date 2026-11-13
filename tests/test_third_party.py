"""THIRD_PARTY.md generation and the license check. SPEC.md section 9."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import third_party  # noqa: E402


class Metadata(dict):
    """The fields third_party reads, with email-message style get_all."""

    def get_all(self, key):
        value = self.get(key)
        if value is None:
            return None
        return [value] if isinstance(value, str) else list(value)


class Distribution:
    def __init__(self, version, **metadata):
        self.version = version
        self.metadata = Metadata(metadata)


def installed_everything():
    from importlib import metadata

    missing = []
    for pin in third_party.pinned_requirements(third_party.REQUIREMENTS):
        try:
            metadata.distribution(third_party.lookup_name(pin.name))
        except metadata.PackageNotFoundError:
            missing.append(pin.name)
    return not missing


REQUIRES_ALL_PINS = pytest.mark.skipif(
    not installed_everything(),
    reason="the pinned runtime and development dependencies are not installed")


@REQUIRES_ALL_PINS
def test_the_committed_file_is_current(capsys):
    assert third_party.main(["--check"]) == 0
    assert "is current" in capsys.readouterr().out


@REQUIRES_ALL_PINS
def test_generation_is_deterministic():
    first = third_party.render()
    second = third_party.render()
    assert first == second
    assert third_party.HEADER in first
    assert "generated_at" not in first


def test_a_copyleft_license_fails():
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.check_license("libcopyleft", "GPL-3.0-only")
    assert "copyleft" in str(raised.value)


def test_an_unknown_license_fails():
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.check_license("libmystery", "Proprietary-1.0")
    assert "not on the allowed license list" in str(raised.value)


def test_a_permissive_license_named_in_the_list_passes():
    for license_id in ("MIT", "MIT-CMU", "BSD-2-Clause", "Apache-2.0", "PSF-2.0"):
        third_party.check_license("liballowed", license_id)


def test_the_license_expression_is_read_first():
    info = Metadata({"License-Expression": "MIT", "License": "BSD License"})
    assert third_party.license_label("lib", info) == "MIT"


def test_a_legacy_license_field_is_normalised():
    assert third_party.license_label("lib", Metadata({"License": "MIT"})) == "MIT"


def test_a_classifier_is_the_fallback():
    info = Metadata({"Classifier": "License :: OSI Approved :: Apache Software License"})
    assert third_party.license_label("lib", info) == "Apache-2.0"


def test_a_distribution_with_no_license_fails():
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.license_label("libbare", Metadata({}))
    assert "no license" in str(raised.value)


def test_family_spellings_normalise_to_one_lookup_name():
    spellings = ("RuaMel.YAML", "ruamel_yaml", "ruamel-yaml", "ruamel..yaml")
    assert {third_party.lookup_name(name) for name in spellings} == {"ruamel-yaml"}


def test_resolution_looks_up_the_normalised_name():
    seen = []

    def lookup(name):
        seen.append(name)
        return Distribution("0.19.1", **{"License-Expression": "MIT"})

    pins = [third_party.Pin("ruamel.yaml", "0.19.1", "requirements.txt")]
    third_party.resolve(pins, lookup)
    assert seen == ["ruamel-yaml"]


def test_a_pinned_dependency_that_is_not_installed_fails():
    def missing(name):
        from importlib import metadata
        raise metadata.PackageNotFoundError(name)

    pins = [third_party.Pin("ghost", "1.0", "requirements.txt")]
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.resolve(pins, missing)
    assert "not installed" in str(raised.value)


def test_an_installed_version_that_differs_from_the_pin_fails():
    lookup = lambda name: Distribution("9.9", **{"License-Expression": "MIT"})
    pins = [third_party.Pin("jsonschema", "4.25.1", "requirements.txt")]
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.resolve(pins, lookup)
    assert "installed at 9.9" in str(raised.value)


def test_a_planted_copyleft_dependency_fails_resolution():
    lookup = lambda name: Distribution("4.25.1", **{"License-Expression": "GPL-3.0-only"})
    pins = [third_party.Pin("jsonschema", "4.25.1", "requirements.txt")]
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.resolve(pins, lookup)
    assert "copyleft" in str(raised.value)


def test_an_unknown_license_on_a_planted_package_fails_resolution():
    lookup = lambda name: Distribution("4.25.1", **{"License-Expression": "Mystery-2.0"})
    pins = [third_party.Pin("jsonschema", "4.25.1", "requirements.txt")]
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.resolve(pins, lookup)
    assert "Mystery-2.0" in str(raised.value)


def test_two_pins_of_one_name_with_different_versions_fail(tmp_path):
    one = tmp_path / "one.txt"
    two = tmp_path / "two.txt"
    one.write_text("jsonschema==4.25.1\n", encoding="utf-8")
    two.write_text("jsonschema==4.26.0\n", encoding="utf-8")
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.pinned_requirements([one, two])
    assert "jsonschema" in str(raised.value)


def test_a_font_family_without_its_license_file_fails(tmp_path):
    fonts = tmp_path / "fonts"
    (fonts / "sans").mkdir(parents=True)
    (fonts / "sans" / "Sans.ttf").write_bytes(b"\0\0\0\0")
    with pytest.raises(third_party.ThirdPartyError) as raised:
        third_party.font_rows(fonts)
    assert "missing OFL.txt" in str(raised.value)


def test_the_font_table_covers_every_shipped_family():
    rows = third_party.font_rows()
    assert len(rows) == 9
    assert {row.license for row in rows} == {"SIL OFL 1.1"}


def test_a_missing_file_under_check_fails(tmp_path, capsys):
    target = tmp_path / "THIRD_PARTY.md"
    target.write_text("stale\n", encoding="utf-8")
    if not installed_everything():
        pytest.skip("the pinned runtime and development dependencies are not installed")
    assert third_party.main(["--check", "--out", str(target)]) == 1
    assert "is stale" in capsys.readouterr().err


def test_the_familiarity_note_says_the_list_does_not_ship():
    lines = " ".join(third_party.familiarity_entries())
    assert "No word-familiarity list is shipped" in lines

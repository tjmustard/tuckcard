"""Every schema has one valid and one invalid fixture, and validate.py agrees."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "plugins/tuckcard/skills/cards-core/scripts/validate.py"
VALID = ROOT / "tests/fixtures/valid"
INVALID = ROOT / "tests/fixtures/invalid"

CASES = {
    "deck": ("deck.fixture.yaml", "deck.fixture.yaml", "/status", "is not one of"),
    "card": ("card.yaml", "card.yaml", "/visibility", "is not one of"),
    "finding": ("finding.md", "finding.md", "/grade", "is not one of"),
    "rule_file": ("rule_file.yaml", "rule_file.yaml", "/rules/0", "'cites' is a required property"),
    "policies": (
        "policies.yaml",
        "policies.yaml",
        "/keys/substances/default",
        "is not one of",
    ),
    "gap": ("gap.md", "gap.md", "/entries/0/date", "does not match"),
    "index": ("index.yaml", "index.yaml", "/findings/0", "'status' is a required property"),
    "bundle_manifest": (
        "bundle_manifest.json",
        "bundle_manifest.json",
        "/platform",
        "is not one of",
    ),
    "layout": ("layout.json", "layout.json", "/font_sizes", "'notes' is a required property"),
    "marks": ("marks.json", "marks.json", "/badge/shape", ""),
    "theme": ("theme.json", "theme.json", "/", "is a required property"),
    "preset": ("preset.json", "preset.json", "/mark_wobble", "less than the minimum"),
    "fit_report": ("fit_report.json", "fit_report.json", "/renderer", "is not one of"),
}


def run(paths, extra=()):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return subprocess.run(
        [sys.executable, str(VALIDATE), *map(str, paths), *extra],
        capture_output=True,
        text=True,
    )


def test_schema_inventory_is_thirteen():
    schemas = sorted(
        path.name.removesuffix(".schema.json")
        for path in (ROOT / "plugins/tuckcard/skills/cards-core/schemas").glob("*.json")
    )
    assert schemas == sorted(CASES)


@pytest.mark.parametrize("kind", sorted(CASES))
def test_valid_fixture_passes(kind):
    filename = CASES[kind][0]
    result = run(VALID / filename)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "valid ({})".format(kind) in result.stdout


@pytest.mark.parametrize("kind", sorted(CASES))
def test_invalid_fixture_fails_at_the_expected_pointer(kind):
    filename, expected_pointer, expected_message = CASES[kind][1:]
    result = run(INVALID / filename)
    assert result.returncode == 1, result.stdout + result.stderr
    assert expected_pointer in result.stdout
    if expected_message:
        assert expected_message in result.stdout

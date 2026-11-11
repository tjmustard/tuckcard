"""The spec's own examples validate, and status follows the verification block."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "plugins/tuckcard/skills/cards-core/scripts/validate.py"
SPEC = ROOT / "tests/fixtures/spec"


def run(paths):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return subprocess.run(
        [sys.executable, str(VALIDATE), *map(str, paths)],
        capture_output=True,
        text=True,
    )


def finding_variant(tmp_path, name, replacements, extra=""):
    text = (SPEC / "finding.md").read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    if extra:
        text = text.replace("related: []", extra + "\nrelated: []")
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_spec_finding_example_validates():
    result = run(SPEC / "finding.md")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "valid (finding)" in result.stdout


def test_spec_manifest_example_validates():
    result = run(SPEC / "manifest.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "valid (bundle_manifest)" in result.stdout


def test_manifest_does_not_accept_an_illustrative_ellipsis_hash(tmp_path):
    text = (SPEC / "manifest.json").read_text(encoding="utf-8")
    path = tmp_path / "manifest.json"
    path.write_text(text.replace(
        "5d41402abc4b2a76b9719d911017c5925d41402abc4b2a76b9719d911017c592", "..."
    ), encoding="utf-8")
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/files/0/sha256" in result.stdout
    assert "does not match" in result.stdout


def test_active_requires_a_script_check(tmp_path):
    path = finding_variant(tmp_path, "fetch-active.md", [("exists: script", "exists: fetch")])
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/verification/exists" in result.stdout


def test_active_requires_support_beyond_unchecked(tmp_path):
    path = finding_variant(
        tmp_path, "unchecked-active.md", [("support: abstract", "support: unchecked")]
    )
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/verification/support" in result.stdout


def test_contested_requires_the_active_base(tmp_path):
    path = finding_variant(
        tmp_path,
        "contested-from-fetch.md",
        [("status: active", "status: contested"), ("exists: script", "exists: fetch")],
    )
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/verification/exists" in result.stdout


def test_provisional_requires_fetch_or_unchecked_support(tmp_path):
    path = finding_variant(
        tmp_path, "script-provisional.md", [("status: active", "status: provisional")]
    )
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/verification" in result.stdout
    assert "is not valid under any of the given schemas" in result.stdout


def test_a_retracted_paper_cannot_be_active(tmp_path):
    path = finding_variant(
        tmp_path, "retracted-active.md", [("retraction: none", "retraction: retracted")]
    )
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "/status" in result.stdout
    assert "quarantined" in result.stdout


def test_quarantined_needs_a_reason(tmp_path):
    path = finding_variant(
        tmp_path,
        "concern-no-reason.md",
        [("status: active", "status: quarantined"), ("retraction: none", "retraction: concern")],
    )
    result = run(path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "'quarantine_reason' is a required property" in result.stdout


def test_quarantined_with_a_reason_validates(tmp_path):
    path = finding_variant(
        tmp_path,
        "concern-with-reason.md",
        [("status: active", "status: quarantined"), ("retraction: none", "retraction: concern")],
        extra="quarantine_reason: Expression of concern.",
    )
    result = run(path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "valid (finding)" in result.stdout

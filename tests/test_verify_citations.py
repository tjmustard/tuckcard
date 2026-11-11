"""Offline citation checks: quarantine reasons, comparisons and the skip."""

import shutil
import socket

import pytest

import support
import verify_citations


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """The whole file replays recorded responses; a socket is a test bug."""

    def blocked(*args, **kwargs):
        raise AssertionError("the offline suite tried to open a network socket")

    monkeypatch.setattr(socket.socket, "connect", blocked)


def knowledge(tmp_path):
    root = tmp_path / "knowledge"
    (root / "findings").mkdir(parents=True)
    (root / "quarantine").mkdir()
    shutil.copy(support.ALLOWLIST, root / "sources-allowlist.yaml")
    return root


def run(root, *paths):
    args = ["--knowledge", str(root), "--responses", str(support.RESPONSES)]
    args += ["--today", "2026-11-11", *map(str, paths)]
    return verify_citations.main(args)


def quarantined(root, finding_id="F-0001"):
    path = root / "quarantine" / "{}.md".format(finding_id)
    assert path.is_file(), sorted(p.name for p in (root / "quarantine").iterdir())
    data, _ = support.files.read_frontmatter(path)
    return data


def shipped(root, finding_id="F-0001"):
    path = root / "findings" / "{}.md".format(finding_id)
    data, _ = support.files.read_frontmatter(path)
    return data


def test_fake_doi_is_quarantined_and_nothing_is_left_behind(tmp_path):
    root = knowledge(tmp_path)
    support.write_finding(
        root / "findings",
        support.finding("F-0001", source={"doi": "10.1234/example.fake"}),
    )
    assert run(root) == 1
    assert not (root / "findings/F-0001.md").exists()
    data = quarantined(root)
    assert data["status"] == "quarantined"
    assert "10.1234/example.fake" in data["quarantine_reason"]
    assert "did not resolve" in data["quarantine_reason"]
    assert "HTTP 404" in data["quarantine_reason"]
    assert data["verification"]["checked_on"] == "2026-11-11"
    # exists records whether the source resolved, not whether it passed.
    assert data["verification"]["exists"] == "none"


def test_retracted_doi_is_quarantined(tmp_path):
    root = knowledge(tmp_path)
    support.write_finding(
        root / "findings",
        support.finding(
            "F-0001", source={"doi": "10.1016/S0140-6736(97)11096-0"}
        ),
    )
    assert run(root) == 1
    data = quarantined(root)
    assert "retracted" in data["quarantine_reason"]
    assert "retraction-watch" in data["quarantine_reason"]
    assert data["verification"]["retraction"] == "retracted"


@pytest.mark.parametrize(
    "changes, expected",
    [
        (
            {"doi": "10.1234/example.mismatch", "title": "A small start helps"},
            "title expected 'A small start helps', found 'A different title'",
        ),
        (
            {"doi": "10.1234/example.valid", "year": 2019},
            "year expected 2019, found 2020",
        ),
        (
            {"doi": "10.1234/example.valid", "first_author": "Nguyen"},
            "first_author expected 'Nguyen', found 'Rivera'",
        ),
    ],
)
def test_metadata_mismatch_names_field_expected_and_found(tmp_path, changes, expected):
    root = knowledge(tmp_path)
    support.write_finding(
        root / "findings", support.finding("F-0001", source=changes)
    )
    assert run(root) == 1
    data = quarantined(root)
    assert data["status"] == "quarantined"
    assert expected in data["quarantine_reason"]
    assert "metadata mismatch" in data["quarantine_reason"]
    # The source resolved; the mismatch is why it was quarantined.
    assert data["verification"]["exists"] == "script"


def test_valid_source_with_all_three_metadata_fields_stays(tmp_path):
    root = knowledge(tmp_path)
    source = {
        "doi": "10.1234/example.valid",
        "title": "A small start helps",
        "year": 2020,
        "first_author": "Rivera",
    }
    support.write_finding(root / "findings", support.finding("F-0001", source=source))
    assert run(root) == 0
    data = shipped(root)
    assert data["verification"]["metadata_match"] == [
        "title",
        "year",
        "first_author",
    ]
    assert data["verification"]["checked_on"] == "2026-11-11"
    assert data["verification"]["retraction"] == "none"
    assert data["verification"]["exists"] == "script"


def test_guidance_url_compares_the_page_title(tmp_path):
    root = knowledge(tmp_path)
    source = {
        "doi": None,
        "pmid": None,
        "url": "https://www.cdc.gov/example/sleep.html",
        "title": "Sleep and Your Child",
    }
    support.write_finding(root / "findings", support.finding("F-0001", source=source))
    assert run(root) == 0
    assert shipped(root)["verification"]["metadata_match"] == ["title"]


def test_guidance_without_source_title_skips_the_comparison(tmp_path, capsys):
    root = knowledge(tmp_path)
    source = {
        "doi": None,
        "pmid": None,
        "url": "https://www.cdc.gov/example/sleep.html",
        "title": None,
    }
    support.write_finding(root / "findings", support.finding("F-0001", source=source))
    assert run(root) == 0
    out = capsys.readouterr().out
    assert "title comparison skipped: source.title is absent" in out
    assert shipped(root)["verification"]["metadata_match"] == []


def test_guidance_domain_must_be_allowlisted(tmp_path):
    root = knowledge(tmp_path)
    source = {
        "doi": None,
        "pmid": None,
        "url": "https://example.com/advice",
        "title": None,
    }
    support.write_finding(root / "findings", support.finding("F-0001", source=source))
    assert run(root) == 1
    reason = quarantined(root)["quarantine_reason"]
    assert "example.com" in reason
    assert "sources-allowlist.yaml" in reason


def test_pmid_resolves_through_pubmed(tmp_path):
    root = knowledge(tmp_path)
    source = {
        "doi": None,
        "pmid": 12345678,
        "title": "Sleep habits in teenagers",
        "year": 2021,
        "first_author": "Lee",
    }
    support.write_finding(root / "findings", support.finding("F-0001", source=source))
    assert run(root) == 0
    assert shipped(root)["verification"]["metadata_match"] == [
        "title",
        "year",
        "first_author",
    ]


def test_a_passing_check_moves_provisional_to_active(tmp_path):
    root = knowledge(tmp_path)
    support.write_finding(
        root / "findings",
        support.finding(
            "F-0001",
            source={"doi": "10.1234/example.valid"},
            verification={"exists": "fetch"},
            status="provisional",
        ),
    )
    assert run(root) == 0
    data = shipped(root)
    assert data["status"] == "active"
    assert data["verification"]["exists"] == "script"


def test_a_passing_check_leaves_an_incomplete_record_provisional(tmp_path, capsys):
    root = knowledge(tmp_path)
    support.write_finding(
        root / "findings",
        support.finding(
            "F-0001",
            source={"doi": "10.1234/example.valid"},
            verification={"exists": "fetch", "support": "unchecked"},
            status="provisional",
        ),
    )
    assert run(root) == 0
    data = shipped(root)
    assert data["status"] == "provisional"
    assert data["verification"]["exists"] == "script"
    assert "status left provisional" in capsys.readouterr().out


def no_sleep(monkeypatch):
    """Record retry delays instead of sleeping through them."""
    waits = []
    monkeypatch.setattr(verify_citations, "_wait", waits.append)
    return waits


@pytest.mark.parametrize(
    "doi, status",
    [
        ("10.1234/example.rate-limited", 429),
        ("10.1234/example.server-error", 503),
    ],
)
def test_a_busy_service_leaves_the_finding_in_place(tmp_path, capsys, monkeypatch, doi, status):
    waits = no_sleep(monkeypatch)
    root = knowledge(tmp_path)
    path = support.write_finding(
        root / "findings", support.finding("F-0001", source={"doi": doi})
    )
    assert run(root) == 1
    assert path.is_file()
    assert not any((root / "quarantine").iterdir())
    out = capsys.readouterr().out
    assert "could not check: {}".format(path) in out
    assert "HTTP {}".format(status) in out
    # One attempt plus two retries, so two waits.
    assert len(waits) == 2


def test_a_timeout_leaves_the_finding_in_place(tmp_path, monkeypatch):
    no_sleep(monkeypatch)

    class Refusing:
        def __init__(self):
            self.calls = 0

        def get(self, url):
            self.calls += 1
            raise verify_citations.CouldNotCheck("network error: timed out")

    root = knowledge(tmp_path)
    path = support.write_finding(
        root / "findings",
        support.finding("F-0001", source={"doi": "10.1234/example.valid"}),
    )
    transport = Refusing()
    passed, lines = verify_citations.check_path(
        path, transport, None, None, root / "quarantine", "2026-11-11", move=True
    )
    assert passed is False
    assert lines[0].startswith("could not check: ")
    assert "timed out" in lines[0]
    assert path.is_file()
    assert not any((root / "quarantine").iterdir())
    assert transport.calls == 3


def test_no_move_never_writes(tmp_path, monkeypatch, capsys):
    no_sleep(monkeypatch)
    root = knowledge(tmp_path)
    failing = support.write_finding(
        root / "findings",
        support.finding("F-0001", source={"doi": "10.1234/example.fake"}),
    )
    # A normal run refreshes this one: today is not its recorded checked_on.
    passing = support.write_finding(
        root / "findings",
        support.finding(
            "F-0002",
            source={"doi": "10.1234/example.valid"},
            verification={"checked_on": "2026-11-10"},
        ),
    )
    before = {path: path.read_text() for path in (failing, passing)}
    args = [
        "--knowledge",
        str(root),
        "--responses",
        str(support.RESPONSES),
        "--today",
        "2026-11-11",
        "--no-move",
    ]
    assert verify_citations.main(args) == 1
    for path, text in before.items():
        assert path.read_text() == text
    assert not any((root / "quarantine").iterdir())
    out = capsys.readouterr().out
    assert "{}: ok".format(passing) in out
    assert "would quarantine" in out


def test_a_path_outside_the_knowledge_folder_is_refused(tmp_path, capsys):
    root = knowledge(tmp_path)
    outside = support.write_finding(
        tmp_path / "elsewhere",
        support.finding("F-0002", source={"doi": "10.1234/example.valid"}),
    )
    args = [
        "--knowledge",
        str(root),
        "--responses",
        str(support.RESPONSES),
        str(outside),
    ]
    assert verify_citations.main(args) == 1
    assert outside.is_file()
    assert not any((root / "quarantine").iterdir())
    out = capsys.readouterr().out
    assert "refusing to check" in out
    assert str(root) in out


def test_a_template_is_skipped_not_quarantined(tmp_path, capsys):
    root = knowledge(tmp_path)
    template = root / "findings/_TEMPLATE.md"
    shutil.copy(support.CORE / "knowledge/findings/_TEMPLATE.md", template)
    real = support.write_finding(
        root / "findings",
        support.finding("F-0001", source={"doi": "10.1234/example.valid"}),
    )
    assert real.is_file()
    assert run(root) == 0
    assert template.is_file()
    assert shipped(root)["verification"]["exists"] == "script"
    # Naming the template explicitly is skipped too, not verified.
    assert run(root, template) == 0
    assert template.is_file()
    assert "{}: skipped template".format(template) in capsys.readouterr().out
    assert not any((root / "quarantine").iterdir())


def test_contact_parameters_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("TUCK_CARD_MAILTO", raising=False)
    assert "mailto" not in verify_citations.crossref_url("10.1234/example.valid")
    assert "tool=tuckcard" in verify_citations.pubmed_url(12345678)
    assert "email" not in verify_citations.pubmed_url(12345678)
    monkeypatch.setenv("TUCK_CARD_MAILTO", "contact@example.org")
    assert "mailto=contact%40example.org" in verify_citations.crossref_url(
        "10.1234/example.valid"
    )
    assert "email=contact%40example.org" in verify_citations.pubmed_url(12345678)


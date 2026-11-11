"""Environment probe: each fact, and the clean degradation when one fails."""

import json
import urllib.error

import support  # noqa: F401 - puts the scripts folder on sys.path

import env_probe


def fake_probe(ok, detail="probed"):
    return {"ok": ok, "detail": detail}


def test_writable_reports_a_folder_it_can_write(tmp_path):
    target = tmp_path / "new" / "folder"
    result = env_probe.probe_writable(target)
    assert result["ok"] is True
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_writable_says_no_when_the_path_is_a_file(tmp_path):
    target = tmp_path / "file"
    target.write_text("not a folder\n", encoding="utf-8")
    result = env_probe.probe_writable(target)
    assert result["ok"] is False
    assert "cannot create folder" in result["detail"]


def test_a_url_probe_failure_is_a_fact(monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.URLError("network is unreachable")

    monkeypatch.setattr(env_probe.urllib.request, "urlopen", refuse)
    result = env_probe.probe_url("https://example.org/", 1.0)
    assert result["ok"] is False
    assert "network is unreachable" in result["detail"]


def test_an_http_error_is_a_fact(monkeypatch):
    def refuse(request, timeout):
        raise urllib.error.HTTPError("https://example.org/", 503, "busy", {}, None)

    monkeypatch.setattr(env_probe.urllib.request, "urlopen", refuse)
    result = env_probe.probe_url("https://example.org/", 1.0)
    assert result == {"ok": False, "url": "https://example.org/",
                      "detail": "HTTP 503"}


def test_the_report_covers_every_fact(monkeypatch, tmp_path):
    monkeypatch.setattr(env_probe, "probe_url", lambda url, timeout: fake_probe(True))
    monkeypatch.setattr(env_probe, "probe_chromium", lambda: fake_probe(True))
    facts = env_probe.report(tmp_path, 1.0, False, True)
    assert facts["ok"] is True
    assert facts["python"] and facts["platform"]
    for name in ("writable", "crossref", "pubmed", "chromium"):
        assert facts[name]["ok"] is True


def test_a_failed_fact_turns_the_report_false(monkeypatch, tmp_path):
    monkeypatch.setattr(env_probe, "probe_url", lambda url, timeout: fake_probe(False))
    facts = env_probe.report(tmp_path, 1.0, False, False)
    assert facts["ok"] is False
    assert facts["crossref"]["ok"] is False and facts["pubmed"]["ok"] is False
    assert facts["chromium"]["ok"] is None


def test_offline_and_no_chromium_skip_without_failing(monkeypatch, tmp_path):
    def refuse(url, timeout):
        raise AssertionError("offline must not call the network")

    monkeypatch.setattr(env_probe, "probe_url", refuse)
    facts = env_probe.report(tmp_path, 1.0, True, False)
    assert facts["ok"] is True
    assert facts["crossref"] == {"ok": None, "detail": "skipped by --offline"}
    assert facts["pubmed"] == {"ok": None, "detail": "skipped by --offline"}
    assert facts["chromium"] == {"ok": None, "detail": "skipped by --no-chromium"}


def test_the_text_view_names_each_state(monkeypatch, tmp_path):
    monkeypatch.setattr(env_probe, "probe_writable", lambda path: fake_probe(True))
    facts = {
        "python": "3.9.6",
        "platform": "darwin",
        "writable": fake_probe(True),
        "crossref": fake_probe(False, "HTTP 503"),
        "pubmed": {"ok": None, "detail": "skipped"},
        "chromium": fake_probe(True),
        "ok": False,
    }
    lines = env_probe.text_lines(facts).splitlines()
    assert lines[0] == "python 3.9.6 on darwin"
    assert "writable  ok" in lines[1]
    assert "crossref  failed  HTTP 503" in lines[2]
    assert "pubmed    skipped skipped" in lines[3]
    assert "chromium  ok" in lines[4]


def test_the_cli_prints_json_and_exits_zero(capsys, tmp_path):
    code = env_probe.main(["--dir", str(tmp_path), "--offline", "--no-chromium"])
    facts = json.loads(capsys.readouterr().out)
    assert code == 0
    assert facts["writable"]["ok"] is True
    assert facts["crossref"]["ok"] is None
    assert facts["chromium"]["ok"] is None


def test_the_cli_prints_text_when_asked(capsys, tmp_path):
    code = env_probe.main(["--dir", str(tmp_path), "--offline", "--no-chromium",
                           "--text"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("python ")
    assert "crossref  skipped" in out

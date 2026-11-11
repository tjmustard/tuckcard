"""Compile: scope selection, when, overrides, categories and determinism."""

import hashlib

import support
import compile_rules
import validate


def tree(tmp_path):
    knowledge = support.base_knowledge(tmp_path / "knowledge")
    support.write_rule_file(
        knowledge / "rules/age/high-school.yaml",
        "age/high-school",
        [
            support.rule(
                "R-high-school-001",
                "must_not",
                cites=("F-0001",),
                strength="must",
            )
        ],
    )
    support.write_rule_file(
        knowledge / "rules/age/college.yaml",
        "age/college",
        [support.rule("R-college-001", "must_not", cites=("F-0001",))],
    )
    support.write_rule_file(
        knowledge / "rules/context/academics.yaml",
        "context/academics",
        [support.rule("R-academics-001", "avoid", cites=("F-0002",))],
    )
    overlay = tmp_path / "overlay"
    support.write_rule_file(
        overlay / "rules/core.yaml",
        "core",
        [
            support.rule(
                "R-core-L001",
                "avoid",
                cites=("F-0002",),
                overrides=["R-core-002"],
                when={"faith": "neutral"},
            )
        ],
    )
    return knowledge, overlay


def compile_once(deck, knowledge, overlay):
    return compile_rules.main(
        [
            str(deck),
            "--knowledge",
            str(knowledge),
            "--overlay",
            str(overlay),
            "--plugin-version",
            "0.1.0",
        ]
    )


def test_compile_applies_scope_when_and_overrides(tmp_path):
    knowledge, overlay = tree(tmp_path)
    deck = support.write_deck(tmp_path)
    assert compile_once(deck, knowledge, overlay) == 0

    data = support.files.load_yaml(tmp_path / "effective-rules.yaml")
    ids = [rule["id"] for rule in data["rules"]]
    assert ids == [
        "R-self-harm-suicide-001",
        "R-high-school-001",
        "R-academics-001",
        "R-core-001",
        "R-core-004",
        "R-core-L001",
    ]
    assert "R-core-002" not in ids
    assert "R-core-003" not in ids
    assert "R-college-001" not in ids
    assert data["scopes"] == [
        "age/high-school",
        "context/academics",
        "core",
        "safety/self-harm-suicide",
    ]

    by_id = {rule["id"]: rule for rule in data["rules"]}
    assert by_id["R-academics-001"]["categories"] == ["habits"]
    assert by_id["R-core-001"]["provenance"] == {
        "scope": "core",
        "file": "rules/core.yaml",
        "plugin_version": "0.1.0",
    }
    assert by_id["R-core-L001"]["provenance"]["file"] == "overlay/rules/core.yaml"

    assert validate.main([str(deck)]) == 0
    assert not (tmp_path / "effective-rules.yaml").read_text().count("compiled_at")


def test_a_mutual_override_pair_stops_the_compile(tmp_path, capsys):
    knowledge, overlay = tree(tmp_path)
    support.write_rule_file(
        knowledge / "rules/core.yaml",
        "core",
        [
            support.rule("R-core-001", "avoid", cites=("F-0002",), overrides=["R-core-002"]),
            support.rule("R-core-002", "avoid", cites=("F-0002",), overrides=["R-core-001"]),
        ],
    )
    deck = support.write_deck(tmp_path)
    assert compile_once(deck, knowledge, overlay) == 1
    out = capsys.readouterr().out
    assert "override cycle" in out
    assert "R-core-001" in out and "R-core-002" in out
    assert not (tmp_path / "effective-rules.yaml").exists()


def test_compile_is_byte_identical_on_repeat_runs(tmp_path, capsys):
    knowledge, overlay = tree(tmp_path)
    deck = support.write_deck(tmp_path)
    assert compile_once(deck, knowledge, overlay) == 0
    first = hashlib.sha256((tmp_path / "effective-rules.yaml").read_bytes()).hexdigest()
    capsys.readouterr()

    assert compile_once(deck, knowledge, overlay) == 0
    second = hashlib.sha256((tmp_path / "effective-rules.yaml").read_bytes()).hexdigest()
    assert first == second
    assert first in capsys.readouterr().out

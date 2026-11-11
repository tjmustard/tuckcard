"""Rule checks: evidence floor, citation status and override legality."""

import support
import validate_rules


def run(root, *extra):
    return validate_rules.main(
        ["--knowledge", str(root), "--no-default-overlay", *map(str, extra)]
    )


def test_the_kits_own_rule_files_pass():
    assert validate_rules.main([]) == 0


def test_evidence_floor_violation_names_rule_and_reason(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(root / "findings", support.finding("F-0001", grade="C"))
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [support.rule("R-core-001", "do", cites=("F-0001",))],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "R-core-001" in out
    assert "evidence floor" in out
    assert "active A or B" in out


def test_a_provisional_finding_cannot_back_a_rule(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(
        root / "findings",
        support.finding(
            "F-0001", status="provisional", verification={"exists": "fetch"}
        ),
    )
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [support.rule("R-core-001", "avoid", cites=("F-0001",))],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "R-core-001" in out
    assert "provisional" in out


def test_a_contested_finding_cannot_back_a_do_rule(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(root / "findings", support.finding("F-0001", status="contested"))
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [support.rule("R-core-001", "do", cites=("F-0001",))],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "contested" in out
    assert "may not" in out


def test_a_safety_override_is_rejected(tmp_path, capsys):
    root = support.base_knowledge(tmp_path / "knowledge")
    overlay = tmp_path / "overlay"
    support.write_rule_file(
        overlay / "rules/core.yaml",
        "core",
        [
            support.rule(
                "R-core-L001",
                "avoid",
                cites=("F-0002",),
                overrides=["R-self-harm-suicide-001"],
            )
        ],
    )
    assert run(root, "--overlay", overlay) == 1
    out = capsys.readouterr().out
    assert "R-core-L001" in out
    assert "may not override safety rule R-self-harm-suicide-001" in out


def test_a_core_rule_cannot_override_a_context_rule(tmp_path, capsys):
    root = support.base_knowledge(tmp_path / "knowledge")
    support.write_rule_file(
        root / "rules/context/academics.yaml",
        "context/academics",
        [support.rule("R-academics-001", "avoid", cites=("F-0002",))],
    )
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [
            support.rule(
                "R-core-001",
                "do",
                cites=("F-0001",),
                overrides=["R-academics-001"],
            )
        ],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "R-core-001" in out
    assert "higher-precedence scope" in out


def test_a_core_do_rule_accepts_grade_d_guidance(tmp_path):
    root = tmp_path / "knowledge"
    support.write_finding(
        root / "findings",
        support.finding("F-0001", grade="D", scopes=["core"]),
    )
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [support.rule("R-core-001", "do", cites=("F-0001",))],
    )
    assert run(root) == 0


def test_a_contested_finding_can_back_a_must_not_rule(tmp_path):
    for grade in ("A", "B", "D"):
        root = tmp_path / grade / "knowledge"
        support.write_finding(
            root / "findings",
            support.finding("F-0001", status="contested", grade=grade),
        )
        support.write_rule_file(
            root / "rules/core.yaml",
            "core",
            [
                support.rule(
                    "R-core-001", "must_not", strength="must", cites=("F-0001",)
                )
            ],
        )
        assert run(root) == 0, grade


def test_a_contested_finding_cannot_back_a_must_rule(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(
        root / "findings",
        support.finding("F-0001", status="contested", grade="A"),
    )
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [
            support.rule(
                "R-core-001", "must", strength="must", cites=("F-0001",)
            )
        ],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "R-core-001" in out
    assert "contested" in out


def test_a_safety_rule_cannot_override_another_safety_rule(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(
        root / "findings",
        support.finding("F-0001", scopes=["safety/self-harm-suicide"], grade="D"),
    )
    support.write_rule_file(
        root / "rules/safety/self-harm-suicide.yaml",
        "safety/self-harm-suicide",
        [
            support.rule(
                "R-self-harm-suicide-001",
                "must_not",
                strength="must",
                cites=("F-0001",),
            ),
            support.rule(
                "R-self-harm-suicide-002",
                "must_not",
                strength="must",
                cites=("F-0001",),
                overrides=["R-self-harm-suicide-001"],
            ),
        ],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "may not override safety rule R-self-harm-suicide-001" in out


def test_a_mutual_override_pair_is_reported(tmp_path, capsys):
    root = tmp_path / "knowledge"
    support.write_finding(root / "findings", support.finding("F-0001"))
    support.write_rule_file(
        root / "rules/core.yaml",
        "core",
        [
            support.rule("R-core-001", "avoid", cites=("F-0001",), overrides=["R-core-002"]),
            support.rule("R-core-002", "avoid", cites=("F-0001",), overrides=["R-core-001"]),
        ],
    )
    assert run(root) == 1
    out = capsys.readouterr().out
    assert "override cycle" in out
    assert "R-core-001" in out and "R-core-002" in out


def test_the_fixture_tree_passes(tmp_path):
    root = support.base_knowledge(tmp_path / "knowledge")
    assert run(root) == 0

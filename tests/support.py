"""Builders and paths shared by the knowledge-tool tests."""

import copy
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
SCRIPTS = CORE / "scripts"
FIXTURES = ROOT / "tests/fixtures"
RESPONSES = FIXTURES / "network/responses.json"
DECK = FIXTURES / "valid/deck.fixture.yaml"
ALLOWLIST = CORE / "knowledge/sources-allowlist.yaml"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import knowledge_files as files  # noqa: E402


BASE_FINDING = {
    "id": "F-0001",
    "claim": "A short first step makes starting more likely than waiting to feel ready.",
    "direction": "supports",
    "scopes": ["core"],
    "grade": "B",
    "design": "randomized experiment",
    "population": "university students",
    "effect": "more starts in the first-step group",
    "distance": "distal",
    "replication": "unknown",
    "source": {
        "citation": "Rivera (2020). A small start helps. Journal of Examples 1(1):1-10.",
        "title": None,
        "year": None,
        "first_author": None,
        "doi": None,
        "pmid": None,
        "url": None,
    },
    "verification": {
        "exists": "script",
        "metadata_match": [],
        "retraction": "none",
        "support": "abstract",
        "anchor": "participants who began with one small step started more often",
        "checked_on": "2026-11-10",
    },
    "status": "active",
    "related": [],
}

BODY = (
    "**Implication for cards.** Start with one small step.\n\n"
    "**Limits.** One sample, one setting.\n"
)


def merge(base, changes):
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value
    return base


def finding(finding_id, **changes):
    data = copy.deepcopy(BASE_FINDING)
    data["id"] = finding_id
    return merge(data, changes)


def write_finding(directory, data, body=BODY):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "{}.md".format(data["id"])
    files.write_frontmatter(path, data, body)
    return path


def rule(rule_id, rule_type="avoid", cites=("F-0001",), **changes):
    data = {
        "id": rule_id,
        "type": rule_type,
        "strength": "should",
        "applies_to": ["title", "lines", "notes"],
        "when": None,
        "overrides": [],
        "text": "Keep the lines specific and doable.",
        "why": "Specific, doable lines are easier to act on.",
        "cites": list(cites),
        "check": "judge",
        "lint": None,
        "examples": None,
    }
    if rule_type == "format":
        data.pop("cites")
        data["basis"] = "template"
    return merge(data, changes)


def write_rule_file(path, scope, rules, status="active", description="Fixture rules."):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "scope": scope,
        "status": status,
        "description": description,
        "rules": rules,
    }
    path.write_text(files.dump_yaml(data), encoding="utf-8")
    return path


def write_deck(tmp_path):
    deck = tmp_path / "deck.yaml"
    shutil.copy(DECK, deck)
    return deck


def base_knowledge(root, with_safety=True):
    """A small shipped tree: three findings and the rules the tests use."""
    findings = root / "findings"
    rules = root / "rules"
    write_finding(
        findings,
        finding(
            "F-0001",
            source={"doi": "10.1234/example.shipped"},
        ),
    )
    write_finding(findings, finding("F-0002", grade="C"))
    write_finding(
        findings,
        finding(
            "F-0003",
            scopes=["safety/self-harm-suicide"],
            grade="D",
        ),
    )
    write_rule_file(
        rules / "core.yaml",
        "core",
        [
            rule("R-core-001", "do", cites=("F-0001",)),
            rule("R-core-002", cites=("F-0002",)),
            rule(
                "R-core-003",
                cites=("F-0002",),
                when={"substances": "harm_reduction"},
            ),
            rule("R-core-004", cites=("F-0002",), when={"faith": "neutral"}),
        ],
    )
    if with_safety:
        write_rule_file(
            rules / "safety/self-harm-suicide.yaml",
            "safety/self-harm-suicide",
            [
                rule(
                    "R-self-harm-suicide-001",
                    "must_not",
                    cites=("F-0003",),
                    strength="must",
                )
            ],
        )
    return root

"""Every shipped example resolves its basis ids and lints clean.

The examples ship no compiled rules, so each README tells a reader to compile
to a temp path and lint against it. These tests compile the same way and check
the claim the README makes.
"""

import re

import support
import compile_rules
import lint

EXAMPLES = support.CORE / "examples"
DECKS = ("grade-school", "middle-school", "college")


def compile_example(tmp_path, name):
    deck = EXAMPLES / name / "deck.yaml"
    out = tmp_path / "{}-rules.yaml".format(name)
    path, errors, _count = compile_rules.compile_deck(
        deck, support.files.KNOWLEDGE_DIR, [], support.files.plugin_version(None), out)
    assert not errors, (name, errors)
    assert path is not None
    return deck, out


def test_every_example_basis_id_is_in_its_compiled_rules(tmp_path):
    for name in DECKS:
        deck_path, rules_path = compile_example(tmp_path, name)
        deck = support.files.load_yaml(deck_path)
        rules = support.files.load_yaml(rules_path)["rules"]
        known = {rule["id"] for rule in rules}
        missing = [(card["n"], rule_id) for card in deck["cards"]
                   for rule_id in card["basis"] if rule_id not in known]
        assert not missing, (name, missing)


def test_every_example_lints_with_zero_errors(tmp_path, capsys):
    for name in DECKS:
        deck_path, rules_path = compile_example(tmp_path, name)
        code = lint.main([str(deck_path), "--rules", str(rules_path),
                          "--no-default-overlay"])
        text = capsys.readouterr().out
        assert code == 0, text
        match = re.search(r"0 errors, (\d+) warnings", text)
        assert match, text
        readme = (EXAMPLES / name / "README.md").read_text(encoding="utf-8")
        claimed = re.search(r"0 errors and (\d+) warnings?", readme)
        assert claimed, name
        # Without Pillow the fit check is skipped, so the README's count is
        # the one to check only when the fit warnings were produced.
        if "layout fit is skipped" not in text:
            assert int(claimed.group(1)) == int(match.group(1)), (name, text)

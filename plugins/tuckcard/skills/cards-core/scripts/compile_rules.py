#!/usr/bin/env python3
"""Compile a deck's effective rules into the deck folder.

Usage:
    python compile_rules.py <deck.yaml> [--knowledge DIR] [--overlay DIR ...]
        [--plugin-version X.Y.Z] [--out PATH]

The compile merges the applicable scopes from shipped knowledge and
each overlay: core, every safety scope, the deck's age band, and the
contexts its categories map to. A rule switches on when every key in
its `when` matches the deck's policies, age band or sender voice. Then
each kept rule drops the rules it overrides. Context rules gain the
deck categories they govern. Every rule records its scope, file and
plugin version.

The output carries no timestamp, so the same deck and plugin version
give byte-identical bytes. The file is written only when it changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import knowledge_files as files
import validate_rules

MISSING = object()


def policy_value(deck: Dict[str, Any], key: str) -> Any:
    """The deck value a `when` key gates on."""
    recipient = deck.get("recipient")
    if key == "age_band":
        return recipient.get("age_band") if isinstance(recipient, dict) else MISSING
    if key == "voice":
        sender = deck.get("sender")
        return sender.get("voice") if isinstance(sender, dict) else MISSING
    policies = deck.get("policies")
    if isinstance(policies, dict) and key in policies:
        return policies[key]
    return MISSING


def condition_matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        return actual in expected
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in expected.items():
            if actual.get(key) != value:
                return False
        return True
    return actual == expected


def rule_applies(rule: Dict[str, Any], deck: Dict[str, Any]) -> bool:
    when = rule.get("when")
    if when in (None, {}):
        return True
    if not isinstance(when, dict):
        raise ValueError("when is not a mapping")
    for key, expected in when.items():
        actual = policy_value(deck, str(key))
        if actual is MISSING:
            raise ValueError(
                "when key {!r} is not a deck policy, age_band or voice".format(key)
            )
        if not condition_matches(expected, actual):
            return False
    return True


def deck_contexts(deck: Dict[str, Any]) -> List[str]:
    contexts: List[str] = []
    categories = deck.get("categories")
    if not isinstance(categories, list):
        return contexts
    for category in categories:
        if not isinstance(category, dict):
            continue
        named = category.get("contexts")
        if not isinstance(named, list):
            continue
        for context in named:
            if isinstance(context, str) and context not in contexts:
                contexts.append(context)
    return contexts


def categories_for(deck: Dict[str, Any], context: str) -> List[str]:
    keys: List[str] = []
    categories = deck.get("categories")
    if not isinstance(categories, list):
        return keys
    for category in categories:
        if not isinstance(category, dict):
            continue
        if context in (category.get("contexts") or []):
            key = category.get("key")
            if isinstance(key, str):
                keys.append(key)
    return keys


def display_file(path: Path, knowledge: Path, overlays: Sequence[Path]) -> str:
    for overlay in overlays:
        if overlay.is_dir():
            try:
                return "overlay/" + path.relative_to(overlay).as_posix()
            except ValueError:
                pass
    try:
        return path.relative_to(knowledge).as_posix()
    except ValueError:
        return path.name


def compiled_rule(
    rule: Dict[str, Any],
    scope: str,
    source: str,
    version: str,
    categories: Optional[List[str]],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "id": rule.get("id"),
        "scope": scope,
        "type": rule.get("type"),
        "strength": rule.get("strength"),
        "applies_to": rule.get("applies_to"),
        "when": rule.get("when"),
        "overrides": rule.get("overrides") or [],
        "text": rule.get("text"),
        "why": rule.get("why"),
    }
    for key in ("cites", "basis", "lint", "examples"):
        if key in rule:
            entry[key] = rule[key]
    entry["check"] = rule.get("check")
    if categories is not None:
        entry["categories"] = categories
    entry["provenance"] = {
        "scope": scope,
        "file": source,
        "plugin_version": version,
    }
    return entry


def compile_deck(
    deck_path: Path,
    knowledge: Path,
    overlays: Sequence[Path],
    version: str,
    out_path: Optional[Path] = None,
) -> Tuple[Optional[Path], List[str], int]:
    """Write the compiled rules. Returns (path written or None, errors, count)."""
    try:
        deck = files.load_yaml(deck_path)
    except Exception as error:  # noqa: BLE001 - one line
        return None, ["{}: could not read deck: {}".format(deck_path, error)], 0
    if not isinstance(deck, dict):
        return None, ["{}: deck is not a mapping".format(deck_path)], 0

    recipient = deck.get("recipient")
    age_band = recipient.get("age_band") if isinstance(recipient, dict) else None
    if not isinstance(age_band, str):
        return None, ["{}: recipient.age_band is missing".format(deck_path)], 0

    rule_roots = [knowledge / "rules", *[overlay / "rules" for overlay in overlays]]
    documents = validate_rules.collect_documents(rule_roots)
    findings, finding_problems = validate_rules.load_finding_pool(
        [knowledge / "findings", *[overlay / "findings" for overlay in overlays]]
    )
    errors = list(finding_problems)
    errors.extend(validate_rules.check_documents(documents, findings))
    if errors:
        return None, errors, 0

    contexts = deck_contexts(deck)
    wanted_scopes = {"core", "age/{}".format(age_band)}
    for context in contexts:
        wanted_scopes.add("context/{}".format(context))
    for _, data in documents:
        scope = data.get("scope")
        if isinstance(scope, str) and scope.startswith("safety/"):
            wanted_scopes.add(scope)

    kept: List[Dict[str, Any]] = []
    for path, data in documents:
        scope = data.get("scope")
        if scope not in wanted_scopes:
            continue
        rules = data.get("rules")
        if not isinstance(rules, list):
            continue
        source = display_file(path, knowledge, overlays)
        category_keys = None
        if str(scope).startswith("context/"):
            category_keys = categories_for(deck, str(scope).split("/", 1)[1])
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            try:
                applies = rule_applies(rule, deck)
            except ValueError as error:
                errors.append(
                    "{}: {}: {}".format(path, rule.get("id", "?"), error)
                )
                continue
            if not applies:
                continue
            kept.append(compiled_rule(rule, scope, source, version, category_keys))
    if errors:
        return None, errors, 0

    overridden = set()
    for rule in kept:
        for target in rule.get("overrides") or []:
            overridden.add(str(target))
    kept = [rule for rule in kept if str(rule.get("id")) not in overridden]
    kept.sort(
        key=lambda rule: (
            -validate_rules.scope_rank(rule.get("scope")),
            str(rule.get("id")),
        )
    )

    output: Dict[str, Any] = {
        "deck_id": deck.get("id"),
        "age_band": age_band,
        "plugin_version": version,
        "scopes": sorted(wanted_scopes),
        "rules": kept,
    }
    text = files.generated_header("compile_rules.py") + files.dump_yaml(output)
    path = out_path or (deck_path.parent / "effective-rules.yaml")
    files.write_if_changed(path, text)
    return path, [], len(kept)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a deck's effective rules. Exit 1 on any invalid input."
    )
    parser.add_argument("deck", help="deck.yaml to compile for")
    parser.add_argument(
        "--knowledge",
        default=str(files.KNOWLEDGE_DIR),
        help="shipped knowledge folder",
    )
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="overlay knowledge folder (repeatable)",
    )
    parser.add_argument(
        "--no-default-overlay",
        action="store_true",
        help="do not add local/knowledge when it exists",
    )
    parser.add_argument("--plugin-version", help="version to record (default: plugin.json)")
    parser.add_argument("--out", help="output path (default: next to the deck)")
    args = parser.parse_args(argv)

    knowledge = Path(args.knowledge)
    overlays = [Path(raw) for raw in args.overlay]
    if not args.no_default_overlay and not args.overlay:
        local = Path("local/knowledge")
        if local.is_dir():
            overlays.append(local)
    version = files.plugin_version(args.plugin_version)
    path, errors, count = compile_deck(
        Path(args.deck),
        knowledge,
        overlays,
        version,
        Path(args.out) if args.out else None,
    )
    for error in errors:
        print(error)
    if errors or path is None:
        return 1
    print(
        "{}: {} rules, sha256 {}".format(
            path, count, files.sha256_file(path)
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

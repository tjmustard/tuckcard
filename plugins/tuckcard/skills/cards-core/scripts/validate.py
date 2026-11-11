#!/usr/bin/env python3
"""Schema-check one Tuckcard file and report one line per problem.

Usage:
    python validate.py <path> [<path> ...] [--schema NAME]

The schema is chosen from the file name, the folder it lives in, or the
document's own shape, unless --schema names one of the thirteen schemas.
Errors print as: path: /json/pointer: message. Exit status is 1 when any
file fails and 0 when every file passes.

Deck files get three extra checks that JSON Schema cannot express:
each basis rule must appear in the deck's rules snapshot when that file
is available, every mark must have a note, and each mark target must
occur at least as many times as its occurrence number says.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from jsonschema import Draft202012Validator, FormatChecker
from ruamel.yaml import YAML

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

KINDS = (
    "deck",
    "card",
    "finding",
    "rule_file",
    "policies",
    "gap",
    "index",
    "bundle_manifest",
    "layout",
    "marks",
    "theme",
    "preset",
    "fit_report",
)

RULE_ID_RE = re.compile(r"^R-[a-z0-9<>-]+-L?[0-9]{3}$")
FINDING_ID_RE = re.compile(r"^[FL]-[0-9]{4}$")

NAME_TO_KIND = {
    "deck.yaml": "deck",
    "deck.yml": "deck",
    "card.yaml": "card",
    "card.yml": "card",
    "policies.yaml": "policies",
    "policies.yml": "policies",
    "index.yaml": "index",
    "index.yml": "index",
    "manifest.json": "bundle_manifest",
    "layout.json": "layout",
    "marks.json": "marks",
    "theme.json": "theme",
    "preset.json": "preset",
    "fit-report.json": "fit_report",
    "fit_report.json": "fit_report",
}

GAP_FIELDS = {
    "Question": "question",
    "Searches tried": "searches_tried",
    "What turned up": "what_turned_up",
    "Date": "date",
    "Next idea": "next_idea",
}


def normalize(value: Any) -> Any:
    """Turn YAML dates and times into the strings the schemas expect."""
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def load_yaml(path: Path) -> Any:
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as handle:
        return normalize(yaml.load(handle))


def split_frontmatter(text: str) -> Optional[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def parse_gaps(text: str) -> List[Dict[str, str]]:
    """Parse the bullet fields of each '## G-...' section."""
    entries: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    field: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = re.match(r"^##\s+(G-\S+)\s*$", line)
        if heading:
            current = {"id": heading.group(1)}
            entries.append(current)
            field = None
            continue
        bullet = re.match(
            r"^-\s+\*\*(Question|Searches tried|What turned up|Date|Next idea):\*\*\s*(.*)$",
            line,
        )
        if bullet and current is not None:
            field = GAP_FIELDS[bullet.group(1)]
            current[field] = bullet.group(2).strip()
            continue
        if current is not None and field is not None and line.strip():
            if raw.startswith((" ", "\t")):
                current[field] = (current[field] + " " + line.strip()).strip()
    return entries


def load_document(path: Path) -> Dict[str, Any]:
    """Return the parsed data plus a hint of what it is."""
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return {"form": "yaml", "data": load_yaml(path)}
    if suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return {"form": "json", "data": normalize(json.load(handle))}
    if suffix == ".md":
        text = path.read_text(encoding="utf-8")
        frontmatter = split_frontmatter(text)
        if frontmatter is not None:
            yaml = YAML(typ="safe")
            data = normalize(yaml.load(frontmatter))
            return {"form": "frontmatter", "data": data}
        if "# Gaps:" in text or path.parent.name == "gaps":
            return {"form": "gap", "data": parse_gaps(text)}
        return {"form": "markdown", "data": None}
    return {"form": "unknown", "data": None}


def detect_kind(path: Path, document: Dict[str, Any]) -> Optional[str]:
    name = path.name.lower()
    if name in NAME_TO_KIND:
        return NAME_TO_KIND[name]
    if path.parent.name in ("themes", "presets"):
        return "theme" if path.parent.name == "themes" else "preset"

    form = document["form"]
    data = document["data"]

    if form == "gap":
        return "gap"
    if form == "frontmatter":
        if isinstance(data, dict) and FINDING_ID_RE.match(str(data.get("id", ""))):
            return "finding"
        return None
    if form in ("yaml", "json"):
        if not isinstance(data, dict):
            return None
        if "scope" in data and "rules" in data:
            return "rule_file"
        if "keys" in data and "ladder" in data:
            return "policies"
        if "cards" in data and "rules_snapshot" in data:
            return "deck"
        if "approval" in data and "n" in data:
            return "card"
        if set(data) == {"findings"}:
            return "index"
        if "platform" in data and "files" in data and "overlay" in data:
            return "bundle_manifest"
        if "regions" in data and "font_sizes" in data:
            return "layout"
        if "styles" in data and "badge" in data:
            return "marks"
        if "background" in data and "category_palette" in data:
            return "theme"
        if "fonts" in data and "mark_wobble" in data:
            return "preset"
        if "renderer" in data and "hand_edits" in data:
            return "fit_report"
    if form == "markdown" and path.parent.name == "findings":
        return "finding"
    return None


def pointer(path_parts: Sequence[Any], prefix: str = "") -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in path_parts]
    body = "/" + "/".join(escaped) if escaped else ""
    return (prefix + body) if prefix else (body or "/")


def schema_errors(
    data: Any, schema_name: str, prefix: str = ""
) -> List[str]:
    with (SCHEMA_DIR / (schema_name + ".schema.json")).open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(data),
        key=lambda error: list(error.absolute_path),
    )
    return [
        "{}: {}".format(pointer(error.absolute_path, prefix), error.message)
        for error in errors
    ]


def resolve_snapshot(deck_path: Path, filename: str) -> Optional[Path]:
    if not filename:
        return None
    for parent in [deck_path.parent] + list(deck_path.parents):
        candidate = parent / filename
        if candidate.is_file():
            return candidate
    candidate = Path(filename)
    if candidate.is_file():
        return candidate
    return None


def collect_rule_ids(data: Any) -> Set[str]:
    ids: Set[str] = set()
    if isinstance(data, dict):
        rules = data.get("rules")
        if isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                    ids.add(rule["id"])
        else:
            for key in data:
                if isinstance(key, str) and RULE_ID_RE.match(key):
                    ids.add(key)
    elif isinstance(data, list):
        for rule in data:
            if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                ids.add(rule["id"])
            elif isinstance(rule, str) and RULE_ID_RE.match(rule):
                ids.add(rule)
    return {rule_id for rule_id in ids if RULE_ID_RE.match(rule_id)}


def deck_cross_errors(deck_path: Path, deck: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    cards = deck.get("cards")
    if not isinstance(cards, list):
        return errors

    for card_index, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        card_number = card.get("n", card_index + 1)
        lines = card.get("lines")
        if isinstance(lines, list):
            for line_index, line in enumerate(lines):
                if not isinstance(line, dict):
                    continue
                mark = line.get("mark")
                if not isinstance(mark, dict):
                    continue
                if not line.get("note"):
                    errors.append(
                        "{}: card {}: a mark must have a note".format(
                            pointer([card_index, "lines", line_index, "note"], "/cards"),
                            card_number,
                        )
                    )
                target = mark.get("target")
                text = line.get("text")
                if isinstance(target, str) and target and isinstance(text, str):
                    occurrence = mark.get("occurrence", 1)
                    if not isinstance(occurrence, int) or occurrence < 1:
                        occurrence = 1
                    found = text.count(target)
                    if found < occurrence:
                        errors.append(
                            "{}: card {}: target {!r} occurs {} time(s), occurrence is {}".format(
                                pointer(
                                    [card_index, "lines", line_index, "mark", "target"],
                                    "/cards",
                                ),
                                card_number,
                                target,
                                found,
                                occurrence,
                            )
                        )

        basis = card.get("basis")
        if isinstance(basis, list):
            snapshot = deck.get("rules_snapshot")
            filename = snapshot.get("file") if isinstance(snapshot, dict) else None
            snapshot_path = resolve_snapshot(deck_path, filename) if isinstance(filename, str) else None
            if snapshot_path is None:
                continue
            try:
                snapshot_ids = collect_rule_ids(load_yaml(snapshot_path))
            except Exception:
                snapshot_ids = set()
            if not snapshot_ids:
                continue
            for basis_index, rule_id in enumerate(basis):
                if not isinstance(rule_id, str):
                    continue
                if rule_id not in snapshot_ids:
                    errors.append(
                        "{}: card {}: rule {} is not in the rules snapshot".format(
                            pointer([card_index, "basis", basis_index], "/cards"),
                            card_number,
                            rule_id,
                        )
                    )

    return errors


def validate_file(path: Path, schema_name: Optional[str] = None) -> List[str]:
    """Return one line per problem; an empty list means the file passed."""
    try:
        document = load_document(path)
    except Exception as error:  # noqa: BLE001 - the message belongs on one line
        return ["/ : could not read file: {}".format(error)]

    kind = schema_name or detect_kind(path, document)
    if kind is None:
        return [
            "/ : could not pick a schema from the file name, folder or shape; pass --schema"
        ]

    data = document["data"]
    if kind == "gap":
        if not isinstance(data, list):
            return ["/ : could not parse gap entries"]
        if not data:
            return ["/ : no gap entries found"]
        lines: List[str] = []
        for index, entry in enumerate(data):
            lines.extend(schema_errors(entry, "gap", "/entries/{}".format(index)))
        return lines

    if data is None:
        return ["/ : could not parse a document of kind {}".format(kind)]

    lines = schema_errors(data, kind)
    if kind == "deck" and not lines:
        lines.extend(deck_cross_errors(path, data))
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Schema-check Tuckcard files. Exit 1 on any problem."
    )
    parser.add_argument("paths", nargs="+", help="file to check")
    parser.add_argument(
        "--schema",
        choices=KINDS,
        help="schema to use instead of detecting it",
    )
    args = parser.parse_args(argv)

    failures = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.is_file():
            print("{}: / : file not found".format(path))
            failures += 1
            continue
        errors = validate_file(path, args.schema)
        if errors:
            failures += 1
            for error in errors:
                print("{}: {}".format(path, error) if error.startswith("/") else error)
        else:
            kind = args.schema or "detected schema"
            if kind == "detected schema":
                document = load_document(path)
                kind = detect_kind(path, document) or kind
            print("{}: valid ({})".format(path, kind))
        if not errors:
            document = load_document(path)
            if (args.schema or detect_kind(path, document)) == "deck":
                deck = document["data"]
                snapshot = deck.get("rules_snapshot") if isinstance(deck, dict) else None
                filename = snapshot.get("file") if isinstance(snapshot, dict) else None
                if isinstance(filename, str) and resolve_snapshot(path, filename) is None:
                    print(
                        "{}: note: basis check skipped (rules snapshot not found: {})".format(
                            path, filename
                        )
                    )

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

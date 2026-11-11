#!/usr/bin/env python3
"""Promote overlay findings and rules into the shipped knowledge files.

Usage:
    python promote.py (--source DIR | --bundle ZIP) [--knowledge DIR]
        [--responses PATH] [--today YYYY-MM-DD]

The only route from an overlay into the shipped files (SPEC.md section
3). It takes `L-` findings and `L` rule IDs, renumbers them to the next
free `F-` finding ID and shipped rule ID, rewrites every reference in
rules and gap entries, runs the script check, moves passing findings
into knowledge/findings/ and failing ones into knowledge/quarantine/,
and regenerates index.yaml.

This is a maintainer step and normally runs with live network access.
--responses replays recorded HTTP responses for the offline tests.

Nothing is deleted: the overlay copies are left where they are, so the
maintainer can remove them deliberately after reviewing the result. An
incoming finding whose DOI is already shipped or quarantined is refused
by name, which is what stops a second run from duplicating it. A new
finding ID never lands on an existing file.
Exit status is 1 when promotion is refused or a check fails.
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import index
import knowledge_files as files
import validate
import validate_rules
import verify_citations

ID_TOKEN_RE = re.compile(r"[FL]-[0-9]{4}|R-[a-z0-9<>-]+-L?[0-9]{3}")


def locate_knowledge(root: Path) -> Optional[Path]:
    """Accept either a knowledge folder or a folder holding one."""
    if (root / "findings").is_dir() or (root / "rules").is_dir():
        return root
    nested = root / "knowledge"
    if (nested / "findings").is_dir() or (nested / "rules").is_dir():
        return nested
    return None


def safe_extract(bundle: Path, destination: Path) -> None:
    with zipfile.ZipFile(str(bundle)) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not str(target).startswith(str(destination.resolve()) + "/"):
                raise ValueError("bundle member escapes the target: {}".format(member.filename))
        archive.extractall(str(destination))


def source_findings(source: Path) -> List[Tuple[Path, Dict[str, Any], str]]:
    findings = []
    for path in files.finding_paths(source / "findings"):
        data, body = files.read_frontmatter(path)
        findings.append((path, data, body))
    return findings


def existing_ids(directories: Sequence[Path]) -> List[int]:
    """Every shipped or quarantined F- number, by file name and by id."""
    numbers: List[int] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in files.finding_paths(directory):
            match = re.match(r"^F-([0-9]{4})\.md$", path.name)
            if match:
                numbers.append(int(match.group(1)))
            try:
                data, _ = files.read_frontmatter(path)
            except Exception:  # noqa: BLE001 - the pool is checked elsewhere
                continue
            match = re.match(r"^F-([0-9]{4})$", str(data.get("id", "")))
            if match:
                numbers.append(int(match.group(1)))
    return numbers


def existing_dois(directories: Sequence[Path]) -> Dict[str, str]:
    """Map each source DOI already in the pool to the finding id holding it."""
    held: Dict[str, str] = {}
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in files.finding_paths(directory):
            try:
                data, _ = files.read_frontmatter(path)
            except Exception:  # noqa: BLE001 - the pool is checked elsewhere
                continue
            source = data.get("source")
            doi = source.get("doi") if isinstance(source, dict) else None
            if isinstance(doi, str) and doi.strip():
                held.setdefault(doi.strip().casefold(), str(data.get("id", path.name)))
    return held


def rewrite_text(text: str, finding_map: Dict[str, str], rule_map: Dict[str, str]) -> str:
    def replace(match: "re.Match[str]") -> str:
        token = match.group(0)
        return finding_map.get(token) or rule_map.get(token) or token

    return ID_TOKEN_RE.sub(replace, text)


def rewrite_rule(
    rule: Dict[str, Any],
    finding_map: Dict[str, str],
    rule_map: Dict[str, str],
) -> None:
    overrides = rule.get("overrides")
    if isinstance(overrides, list):
        rule["overrides"] = [rule_map.get(str(item), str(item)) for item in overrides]
    cites = rule.get("cites")
    if isinstance(cites, list):
        rule["cites"] = [finding_map.get(str(item), str(item)) for item in cites]
    for key in ("text", "why"):
        if isinstance(rule.get(key), str):
            rule[key] = rewrite_text(rule[key], finding_map, rule_map)
    examples = rule.get("examples")
    if isinstance(examples, dict):
        for key in ("bad", "good"):
            if isinstance(examples.get(key), str):
                examples[key] = rewrite_text(examples[key], finding_map, rule_map)


def rule_segment(scope: str) -> str:
    return str(scope).rsplit("/", 1)[-1]


def next_rule_numbers(documents: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """The next free number per scope, across all loaded rule documents."""
    highest: Dict[str, int] = {}
    for document in documents:
        rules = document.get("rules")
        if not isinstance(rules, list):
            continue
        for rule in rules:
            rule_id = str(rule.get("id", ""))
            match = re.match(r"^R-[a-z0-9<>-]+-L?([0-9]{3})$", rule_id)
            if not match:
                continue
            scope = str(document.get("scope", ""))
            number = int(match.group(1))
            highest[scope] = max(highest.get(scope, 0), number)
    return highest


def promote(
    source: Path,
    knowledge: Path,
    responses: Optional[Path] = None,
    today: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Run a promotion. Returns (summary lines, errors)."""
    source = locate_knowledge(source) or source
    findings_dir = knowledge / "findings"
    quarantine_dir = knowledge / "quarantine"
    rules_dir = knowledge / "rules"
    gaps_dir = knowledge / "gaps"
    summary: List[str] = []
    errors: List[str] = []

    try:
        incoming = source_findings(source)
    except Exception as error:  # noqa: BLE001 - one line
        return summary, ["could not read overlay findings: {}".format(error)]
    if not incoming:
        errors.append("no findings in {}".format(source / "findings"))
    for path, data, _ in incoming:
        finding_id = str(data.get("id", ""))
        if not finding_id.startswith("L-"):
            errors.append(
                "{}: {} is not an overlay L- finding; only L- IDs are promoted".format(
                    path, finding_id or "(no id)"
                )
            )
    if errors:
        return summary, errors

    # Verification, without writing yet.
    if responses:
        transport: Any = verify_citations.RecordedTransport(
            verify_citations.recorded_mapping(responses)
        )
    else:
        transport = verify_citations.LiveTransport()
    domains, allowlist_error = verify_citations.load_allowlist(
        knowledge / "sources-allowlist.yaml"
    )

    held_dois = existing_dois([findings_dir, quarantine_dir])
    seen_incoming: Dict[str, str] = {}
    results = []
    for path, data, body in incoming:
        result = verify_citations.verify_finding(
            data, transport, domains, allowlist_error, today
        )
        updated = verify_citations.apply_checked(data, result)
        record = data.get("source") if isinstance(data.get("source"), dict) else {}
        doi = record.get("doi")
        if isinstance(doi, str) and doi.strip():
            key = doi.strip().casefold()
            holder = held_dois.get(key) or seen_incoming.get(key)
            if holder:
                errors.append(
                    "{}: DOI {} is already held by {}; refusing to promote a duplicate".format(
                        path, doi, holder
                    )
                )
            else:
                seen_incoming[key] = str(data.get("id"))
        if result["ok"] and updated.get("status") not in ("active", "contested"):
            errors.append(
                "{}: {} is {}; only active or contested findings may ship "
                "(SPEC.md section 3, invariant 1)".format(
                    path, data.get("id"), updated.get("status")
                )
            )
        results.append((path, data, body, result, updated))
    if errors:
        return summary, errors

    # Finding IDs: the next free F- number, skipping every id already in
    # the shipped pool or in quarantine before each allocation.
    used = set(existing_ids([findings_dir, quarantine_dir]))
    next_number = 1
    finding_map: Dict[str, str] = {}
    for path, data, _, _, _ in results:
        while next_number in used:
            next_number += 1
        finding_map[str(data["id"])] = "F-{:04d}".format(next_number)
        used.add(next_number)
        next_number += 1

    # Rule documents: shipped plus overlay, kept as text for validation.
    source_rule_docs: List[Tuple[Path, Dict[str, Any]]] = []
    if (source / "rules").is_dir():
        for path in files.rule_paths(source / "rules"):
            try:
                document = files.load_yaml(path)
            except Exception as error:  # noqa: BLE001 - one line
                errors.append("{}: could not read rule file: {}".format(path, error))
                continue
            if not isinstance(document, dict):
                errors.append("{}: rule file is not a mapping".format(path))
                continue
            source_rule_docs.append((path, document))
    target_rule_docs: List[Tuple[Path, Dict[str, Any]]] = []
    if rules_dir.is_dir():
        for path in files.rule_paths(rules_dir):
            try:
                document = files.load_yaml(path)
            except Exception as error:  # noqa: BLE001 - one line
                errors.append("{}: could not read rule file: {}".format(path, error))
                continue
            if not isinstance(document, dict):
                errors.append("{}: rule file is not a mapping".format(path))
                continue
            target_rule_docs.append((path, document))
    if errors:
        return summary, errors

    highest = next_rule_numbers([document for _, document in target_rule_docs])
    rule_map: Dict[str, str] = {}
    for path, document in source_rule_docs:
        scope = document.get("scope")
        segment = rule_segment(scope)
        for rule in document.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule.get("id", ""))
            if not re.search(r"-L[0-9]{3}$", rule_id):
                errors.append(
                    "{}: {} is not an overlay rule ID; only L rule IDs are promoted".format(
                        path, rule_id or "(no id)"
                    )
                )
                continue
            if rule_id in rule_map:
                errors.append(
                    "{}: rule {} appears more than once in the overlay".format(
                        path, rule_id
                    )
                )
                continue
            highest[scope] = highest.get(scope, 0) + 1
            rule_map[rule_id] = "R-{}-{:03d}".format(segment, highest[scope])
    if errors:
        return summary, errors

    # Rewrite references in the shipped and incoming rules.
    for _, document in target_rule_docs + source_rule_docs:
        for rule in document.get("rules") or []:
            if isinstance(rule, dict):
                rewrite_rule(rule, finding_map, rule_map)

    # Rule file text: start from the shipped file when one exists, so its
    # comments and key order survive, then append the promoted rules.
    target_by_scope: Dict[str, Tuple[Path, Any]] = {}
    for path, document in target_rule_docs:
        scope = document.get("scope")
        if scope in target_by_scope:
            errors.append(
                "{}: scope {} is also declared in {}".format(
                    path, scope, target_by_scope[scope][0]
                )
            )
            continue
        yaml = files.yaml_out()
        with path.open("r", encoding="utf-8") as handle:
            target_by_scope[scope] = (path, yaml.load(handle))
    if errors:
        return summary, errors

    for _, roundtrip in target_by_scope.values():
        for rule in roundtrip.get("rules") or []:
            if isinstance(rule, dict):
                rewrite_rule(rule, finding_map, rule_map)

    for path, document in source_rule_docs:
        scope = document.get("scope")
        if scope in target_by_scope:
            target_path, target_data = target_by_scope[scope]
        else:
            target_path = rules_dir / "{}.yaml".format(scope)
            target_data = {
                "scope": scope,
                "status": document.get("status", "active"),
                "description": document.get("description", "Promoted from the overlay."),
                "rules": [],
            }
            target_by_scope[scope] = (target_path, target_data)
        for rule in document.get("rules") or []:
            if isinstance(rule, dict):
                rule["id"] = rule_map.get(str(rule.get("id")), rule.get("id"))
                target_data.setdefault("rules", []).append(copy.deepcopy(rule))

    # The promoted rule documents as plain data for validation and output.
    final_rule_docs: List[Tuple[Path, Dict[str, Any]]] = []
    rule_texts: Dict[Path, str] = {}
    for scope, (path, roundtrip) in target_by_scope.items():
        from io import StringIO

        stream = StringIO()
        files.yaml_out().dump(roundtrip, stream)
        text = stream.getvalue()
        rule_texts[path] = text
        final_rule_docs.append((path, files.yaml_loads(text)))

    # Findings as they will be written.
    final_findings: Dict[str, Dict[str, Any]] = {}
    for existing in files.finding_paths(findings_dir):
        try:
            data, _ = files.read_frontmatter(existing)
        except Exception:  # noqa: BLE001 - validation will report it
            continue
        if isinstance(data.get("id"), str):
            final_findings[data["id"]] = data

    written_findings = []
    for path, data, body, result, updated in results:
        updated["id"] = finding_map[str(data["id"])]
        if result["ok"]:
            destination = findings_dir / "{}.md".format(updated["id"])
            written_findings.append((destination, updated, body))
            final_findings[updated["id"]] = updated
            summary.append(
                "{}: {} -> {} (checked, shipped)".format(
                    path, data.get("id"), updated["id"]
                )
            )
        else:
            updated["status"] = "quarantined"
            updated["quarantine_reason"] = "; ".join(result["reasons"])
            destination = quarantine_dir / "{}.md".format(updated["id"])
            written_findings.append((destination, updated, body))
            summary.append(
                "{}: {} -> {} (quarantined: {})".format(
                    path, data.get("id"), updated["id"], updated["quarantine_reason"]
                )
            )

    for destination, updated, _ in written_findings:
        if destination.exists():
            errors.append(
                "{}: already exists; refusing to overwrite a finding".format(
                    destination
                )
            )
        schema_errors = validate.schema_errors(updated, "finding")
        for line in schema_errors:
            errors.append("{}: {}".format(destination, line))
    if errors:
        return summary, errors

    rule_errors = validate_rules.check_documents(final_rule_docs, final_findings)
    if rule_errors:
        return summary, rule_errors

    # Rewrite references in gap entries.
    gap_texts: Dict[Path, str] = {}
    if gaps_dir.is_dir():
        for path in sorted(gaps_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            rewritten = rewrite_text(text, finding_map, rule_map)
            if rewritten != text:
                gap_texts[path] = rewritten

    # All checks passed: write.
    for destination, updated, body in written_findings:
        files.write_frontmatter(destination, updated, body)
    for path, text in rule_texts.items():
        files.write_if_changed(path, text)
    for path, text in gap_texts.items():
        path.write_text(text, encoding="utf-8")
        summary.append("{}: references rewritten".format(path))

    changed, count, index_problems = index.regenerate(findings_dir)
    for problem in index_problems:
        errors.append(problem)
    if index_problems:
        return summary, errors
    summary.append(
        "{}: {} ({} findings)".format(
            findings_dir / "index.yaml", "wrote" if changed else "unchanged", count
        )
    )
    summary.append(
        "overlay files were left in place; remove them once you have reviewed the result"
    )
    return summary, errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote overlay findings and rules into shipped knowledge."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", help="overlay knowledge folder or its parent")
    group.add_argument("--bundle", help="bundle zip holding a knowledge folder")
    parser.add_argument(
        "--knowledge",
        default=str(files.KNOWLEDGE_DIR),
        help="shipped knowledge folder",
    )
    parser.add_argument(
        "--responses",
        help="recorded responses JSON file or folder; no network is used",
    )
    parser.add_argument("--today", help="date to record as checked_on")
    args = parser.parse_args(argv)

    knowledge = Path(args.knowledge)
    responses = Path(args.responses) if args.responses else None
    temporary: Optional[tempfile.TemporaryDirectory[str]] = None
    try:
        if args.bundle:
            temporary = tempfile.TemporaryDirectory(prefix="tuckcard-promote-")
            safe_extract(Path(args.bundle), Path(temporary.name))
            source = Path(temporary.name)
        else:
            source = Path(args.source)
            if not source.is_dir():
                print("source not found: {}".format(source))
                return 1
        summary, errors = promote(source, knowledge, responses, args.today)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print("promotion failed: {}".format(error))
        return 1
    finally:
        if temporary is not None:
            temporary.cleanup()

    for line in summary:
        print(line)
    for error in errors:
        print("error: {}".format(error))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

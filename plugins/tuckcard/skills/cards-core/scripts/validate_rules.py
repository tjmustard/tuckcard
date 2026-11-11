#!/usr/bin/env python3
"""Check rule files: schema, cited findings, evidence floor and overrides.

Usage:
    python validate_rules.py [<rule.yaml> ...]
        [--knowledge DIR] [--overlay DIR ...]

With no paths, every rule file under the shipped knowledge folder and
each overlay is checked. Rule templates (`_TEMPLATE.yaml`) are skipped:
they are scaffolds, not rules. Policies files are not rule files.

Checks, from SPEC.md section 4:
- every rule file and rule passes rule_file.schema.json
- every cited finding exists in the pool and is live: provisional and
  quarantined can back nothing, contested only avoid and must_not
- the evidence floor: do needs an active A, B or D finding (D is
  guidance from a public-health or professional body, whatever the
  rule's scope); avoid needs an active or contested finding; must
  needs an active A, B or D finding; must_not needs an active or
  contested A, B or D finding; format cites none
- an override names a rule that exists, is lower in precedence
  (safety > age band > context > core), and never targets a safety
  rule; overrides that form a cycle are reported, not resolved.

Exit status is 1 on any problem and 0 when every rule passes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import knowledge_files as files
import validate

SCOPE_RANK = {"safety": 5, "age": 3, "context": 2, "core": 1}
FLOOR_GRADES = {
    "do": {"A", "B", "D"},
    "avoid": set(),
    "must": {"A", "B", "D"},
    "must_not": {"A", "B", "D"},
}
CONTESTS_ALLOWED = {"avoid", "must_not"}
# A contested finding can forbid a behaviour, never require one
# (SPEC.md section 3: contested backs "only avoid and must_not rules").
CONTESTED_FLOOR_TYPES = {"must_not"}


def scope_rank(scope: Any) -> int:
    base = str(scope).split("/")[0]
    return SCOPE_RANK.get(base, 0)


def is_overlay_rule(rule_id: str) -> bool:
    return "-L" in rule_id


def load_finding_pool(dirs: Iterable[Path]) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Map finding ID to its data across every folder given."""
    pool: Dict[str, Dict[str, Any]] = {}
    problems: List[str] = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        for path in files.finding_paths(directory):
            try:
                data, _ = files.read_frontmatter(path)
            except Exception as error:  # noqa: BLE001 - one line is enough
                problems.append("{}: could not read finding: {}".format(path, error))
                continue
            finding_id = data.get("id")
            if not isinstance(finding_id, str):
                problems.append("{}: finding has no id".format(path))
                continue
            if finding_id in pool:
                problems.append(
                    "{}: id {} is also used by another finding".format(path, finding_id)
                )
                continue
            pool[finding_id] = data
    return pool, problems


def index_rules(
    documents: Sequence[Tuple[Path, Dict[str, Any]]],
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Map rule ID to {rule, scope, path} and report duplicate IDs."""
    index: Dict[str, Dict[str, Any]] = {}
    problems: List[str] = []
    for path, data in documents:
        scope = data.get("scope")
        rules = data.get("rules")
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str):
                continue
            if rule_id in index:
                problems.append(
                    "{}: rule {} is also declared in {}".format(
                        path, rule_id, index[rule_id]["path"]
                    )
                )
                continue
            index[rule_id] = {"rule": rule, "scope": scope, "path": path}
    return index, problems


def citation_errors(
    rule: Dict[str, Any],
    scope: Any,
    findings: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Status rules and the evidence floor for one rule."""
    rule_type = rule.get("type")
    rule_id = rule.get("id")
    errors: List[str] = []

    if rule_type == "format":
        return errors

    cites = rule.get("cites")
    if not isinstance(cites, list) or not cites:
        return ["{}: {} must cite at least one finding".format(rule_id, rule_type)]

    allowed_grades = set(FLOOR_GRADES.get(str(rule_type), set()))

    live: List[Dict[str, Any]] = []
    for finding_id in cites:
        finding = findings.get(str(finding_id))
        if finding is None:
            errors.append(
                "{}: cites {}, which is not in the finding pool".format(
                    rule_id, finding_id
                )
            )
            continue
        status = finding.get("status")
        if status in ("provisional", "quarantined"):
            errors.append(
                "{}: cites {}, which is {} and can back nothing".format(
                    rule_id, finding_id, status
                )
            )
            continue
        if status == "contested" and rule_type not in CONTESTS_ALLOWED:
            errors.append(
                "{}: cites contested finding {}, but a {} rule may not".format(
                    rule_id, finding_id, rule_type
                )
            )
            continue
        if status in ("active", "contested"):
            live.append(finding)

    if rule_type == "avoid":
        if not live:
            errors.append(
                "{}: evidence floor: avoid needs an active or contested finding".format(
                    rule_id
                )
            )
        return errors

    accepted = {"active"}
    if rule_type in CONTESTED_FLOOR_TYPES:
        accepted.add("contested")
    matching = [
        finding
        for finding in live
        if finding.get("status") in accepted
        and finding.get("grade") in allowed_grades
    ]
    if not matching:
        cited = sorted(
            "{}/{}".format(finding.get("grade"), finding.get("status"))
            for finding in live
        )
        errors.append(
            "{}: evidence floor: {} needs {} {} finding; cited are {}".format(
                rule_id,
                rule_type,
                "an active or contested" if "contested" in accepted else "an active",
                " or ".join(sorted(allowed_grades)) or "(none)",
                ", ".join(cited) if cited else "none",
            )
        )
    return errors


def override_errors(
    rule: Dict[str, Any],
    scope: Any,
    rule_index: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Precedence and the absolute safety rule for one rule's overrides."""
    errors: List[str] = []
    rule_id = rule.get("id")
    overrides = rule.get("overrides")
    if not isinstance(overrides, list):
        return errors
    source_rank = scope_rank(scope)
    for target_id in overrides:
        target_id = str(target_id)
        if target_id == rule_id:
            errors.append("{}: overrides itself".format(rule_id))
            continue
        target = rule_index.get(target_id)
        if target is None:
            errors.append(
                "{}: overrides {}, which no loaded rule file declares".format(
                    rule_id, target_id
                )
            )
            continue
        if not is_overlay_rule(rule_id) and is_overlay_rule(target_id):
            errors.append(
                "{}: a shipped rule may not override overlay rule {}".format(
                    rule_id, target_id
                )
            )
            continue
        target_scope = target.get("scope")
        target_rank = scope_rank(target_scope)
        if str(target_scope).split("/")[0] == "safety":
            errors.append(
                "{}: may not override safety rule {}; nothing overrides safety".format(
                    rule_id, target_id
                )
            )
            continue
        if source_rank < target_rank:
            errors.append(
                "{}: overrides {}, which is a higher-precedence scope".format(
                    rule_id, target_id
                )
            )
    return errors


def override_cycles(
    rule_index: Dict[str, Dict[str, Any]],
    wanted: Optional[set] = None,
) -> List[List[str]]:
    """Every group of rules that override each other in a loop."""
    graph: Dict[str, List[str]] = {}
    for rule_id, entry in rule_index.items():
        if wanted is not None and str(entry["path"].resolve()) not in wanted:
            continue
        targets = entry["rule"].get("overrides")
        graph[rule_id] = (
            [str(target) for target in targets if str(target) in rule_index]
            if isinstance(targets, list)
            else []
        )
    cycles: List[List[str]] = []
    seen = set()
    for start in sorted(graph):
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for target in graph.get(node, []):
                if target in path:
                    cycle = path[path.index(target):]
                    key = tuple(sorted(cycle))
                    if key not in seen:
                        seen.add(key)
                        cycles.append(cycle)
                else:
                    stack.append((target, path + [target]))
    return cycles


def check_documents(
    documents: Sequence[Tuple[Path, Dict[str, Any]]],
    findings: Dict[str, Dict[str, Any]],
    check_paths: Optional[Sequence[Path]] = None,
) -> List[str]:
    """Every problem in a set of loaded rule documents.

    Every document joins the rule index so an override can name a rule
    from another file, but only members of check_paths are reported on
    when that list is given.
    """
    problems: List[str] = []
    rule_index, index_problems = index_rules(documents)
    problems.extend(index_problems)
    wanted = (
        {str(path.resolve()) for path in check_paths}
        if check_paths is not None
        else None
    )
    for cycle in override_cycles(rule_index, wanted):
        loop = cycle + [cycle[0]]
        problems.append(
            "rules {} form an override cycle: {}".format(
                " and ".join(cycle), " -> ".join(loop)
            )
        )
    for path, data in documents:
        if wanted is not None and str(path.resolve()) not in wanted:
            continue
        schema_errors = validate.schema_errors(data, "rule_file")
        for line in schema_errors:
            problems.append("{}: {}".format(path, line))
        if schema_errors:
            continue
        scope = data.get("scope")
        rules = data.get("rules")
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rule_id = rule.get("id", "?")
            for message in citation_errors(rule, scope, findings):
                problems.append("{}: {}".format(path, message))
            for message in override_errors(rule, scope, rule_index):
                problems.append("{}: {}".format(path, message))
    return problems


def collect_documents(
    roots: Sequence[Path],
) -> List[Tuple[Path, Dict[str, Any]]]:
    documents: List[Tuple[Path, Dict[str, Any]]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in files.rule_paths(root):
            try:
                data = files.load_yaml(path)
            except Exception as error:  # noqa: BLE001 - report one line
                documents.append((path, {"__load_error__": str(error)}))
                continue
            if not isinstance(data, dict):
                documents.append((path, {"__load_error__": "not a mapping"}))
                continue
            documents.append((path, data))
    return documents


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check rule schema, citations, evidence floor and overrides."
    )
    parser.add_argument("paths", nargs="*", help="rule files to check")
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
    args = parser.parse_args(argv)

    knowledge = Path(args.knowledge)
    overlays = [Path(raw) for raw in args.overlay]
    if not args.no_default_overlay and not args.overlay:
        local = Path("local/knowledge")
        if local.is_dir():
            overlays.append(local)

    documents = collect_documents([knowledge / "rules", *[o / "rules" for o in overlays]])
    check_paths: Optional[List[Path]] = None
    load_problems = []
    if args.paths:
        check_paths = [Path(raw) for raw in args.paths]
        present = {str(path.resolve()) for path, _ in documents}
        for path in check_paths:
            if str(path.resolve()) not in present:
                if path.is_file():
                    try:
                        data = files.load_yaml(path)
                    except Exception as error:  # noqa: BLE001 - one line
                        load_problems.append(
                            "{}: could not read rule file: {}".format(path, error)
                        )
                        continue
                    if isinstance(data, dict):
                        documents.append((path, data))
                    else:
                        load_problems.append(
                            "{}: could not read rule file: not a mapping".format(path)
                        )
                else:
                    load_problems.append("{}: file not found".format(path))

    usable = []
    for path, data in documents:
        if "__load_error__" in data:
            if check_paths is None or str(path.resolve()) in {
                str(item.resolve()) for item in check_paths
            }:
                load_problems.append(
                    "{}: could not read rule file: {}".format(path, data["__load_error__"])
                )
        else:
            usable.append((path, data))

    findings, finding_problems = load_finding_pool(
        [knowledge / "findings", *[o / "findings" for o in overlays]]
    )
    problems = load_problems + finding_problems
    problems.extend(check_documents(usable, findings, check_paths))
    for problem in problems:
        print(problem)
    if problems:
        return 1
    checked = [
        (path, data)
        for path, data in usable
        if check_paths is None
        or str(path.resolve()) in {str(item.resolve()) for item in check_paths}
    ]
    rule_count = sum(
        len(data.get("rules") or [])
        for _, data in checked
        if isinstance(data.get("rules"), list)
    )
    print(
        "{} rule files, {} rules: ok".format(len(checked), rule_count)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

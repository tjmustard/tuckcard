#!/usr/bin/env python3
"""Regenerate knowledge/findings/index.yaml from the finding files.

Usage:
    python index.py [<finding.md> ...] [--findings DIR] [--out PATH]

With no paths, every finding in --findings (default
knowledge/findings/) is read. Each entry carries the ID, a one-line
claim, scopes, grade, direction and status, sorted by ID. The output is
written only when its bytes change, so a second run on the same input
touches nothing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import knowledge_files as files
import validate

REQUIRED = ("id", "claim", "scopes", "grade", "direction", "status")


def finding_entries(paths: Sequence[Path]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Build the index entries, and one problem line per unreadable file."""
    entries: List[Dict[str, Any]] = []
    problems: List[str] = []
    seen = {}
    for path in paths:
        try:
            data, _ = files.read_frontmatter(path)
        except Exception as error:  # noqa: BLE001 - report it as one line
            problems.append("{}: could not read finding: {}".format(path, error))
            continue
        missing = [key for key in REQUIRED if key not in data]
        if missing:
            problems.append(
                "{}: missing {}".format(path, ", ".join(missing))
            )
            continue
        finding_id = str(data["id"])
        if not files.FINDING_ID_RE.match(finding_id):
            problems.append(
                "{}: id {!r} is not F-NNNN or L-NNNN".format(path, finding_id)
            )
            continue
        if finding_id in seen:
            problems.append(
                "{}: id {} is also used by {}".format(path, finding_id, seen[finding_id])
            )
            continue
        seen[finding_id] = path
        entries.append(
            {
                "id": finding_id,
                "claim": files.claim_one_line(data["claim"]),
                "scopes": data["scopes"],
                "grade": data["grade"],
                "direction": data["direction"],
                "status": data["status"],
            }
        )
    entries.sort(key=lambda entry: entry["id"])
    return entries, problems


def render(entries: List[Dict[str, Any]]) -> str:
    return files.generated_header("index.py") + files.dump_yaml({"findings": entries})


def regenerate(
    findings_dir: Path,
    out_path: Optional[Path] = None,
    paths: Optional[Sequence[Path]] = None,
) -> Tuple[bool, int, List[str]]:
    """Write the index. Returns (changed, entry count, problems)."""
    if paths is None:
        paths = files.finding_paths(findings_dir)
    entries, problems = finding_entries(paths)
    if problems:
        return False, len(entries), problems
    data = {"findings": entries}
    schema_errors = validate.schema_errors(data, "index")
    if schema_errors:
        return False, len(entries), ["index: " + line for line in schema_errors]
    out = out_path or (findings_dir / "index.yaml")
    return files.write_if_changed(out, render(entries)), len(entries), []


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate knowledge/findings/index.yaml. Exit 1 on a bad finding."
    )
    parser.add_argument("paths", nargs="*", help="finding files to index")
    parser.add_argument(
        "--findings",
        default=str(files.FINDINGS_DIR),
        help="folder to read when no paths are given",
    )
    parser.add_argument("--out", help="index path (default: <findings>/index.yaml)")
    args = parser.parse_args(argv)

    findings_dir = Path(args.findings)
    paths = [Path(raw) for raw in args.paths] if args.paths else None
    out_path = Path(args.out) if args.out else None
    changed, count, problems = regenerate(findings_dir, out_path, paths)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    out = out_path or (findings_dir / "index.yaml")
    print(
        "{}: {} ({} findings)".format(
            out, "wrote" if changed else "unchanged", count
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

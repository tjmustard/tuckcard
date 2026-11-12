#!/usr/bin/env python3
"""Scan example decks for terms from a private list kept outside the repo.

Usage:
    python tools/pii_scan.py [paths ...] --terms <path outside the repo> [--json]

With no paths, the shipped examples tree is scanned. A path may be a folder,
which is searched recursively, or a file. The terms file holds one term per
line; blank lines and lines starting with '#' are ignored, and matching is
case-insensitive on whole words, so a multi-word term matches as a phrase.

Only the tool lives in the repo. The terms file is the maintainer's own and is
never copied, bundled or named in a workflow. Exit 1 when any term is found,
2 when the terms file cannot be read, 0 when the scan is clean.

A term is reported as <path>:<line>: <term>, without the surrounding line, so a
terminal scrollback does not repeat the private detail. --json prints the same
hits as objects.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "plugins/tuckcard/skills/cards-core/examples"


def load_terms(path: Path) -> List[str]:
    """Read the private terms file. Raises OSError or ValueError."""
    terms = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    if not terms:
        raise ValueError("{}: no terms".format(path))
    return terms


def term_pattern(term: str) -> "re.Pattern[str]":
    """Whole-word, case-insensitive, with inner spaces matched as a phrase."""
    body = r"\s+".join(re.escape(part) for part in term.split())
    return re.compile(r"(?<!\w){}(?!\w)".format(body), re.IGNORECASE)


def target_files(paths: Sequence[Path]) -> List[Path]:
    files: List[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def scan_file(path: Path, patterns: Sequence["re.Pattern[str]"],
              terms: Sequence[str]) -> List[Dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    hits: List[Dict[str, object]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for term, pattern in zip(terms, patterns):
            if pattern.search(line):
                hits.append({"path": str(path), "line": number, "term": term})
    return hits


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan example decks for terms from a private list. Exit 1 on a hit."
    )
    parser.add_argument("paths", nargs="*", help="files or folders to scan")
    parser.add_argument("--terms", required=True,
                        help="term list outside the repo, one term per line")
    parser.add_argument("--json", action="store_true", help="print hits as JSON")
    args = parser.parse_args(argv)

    try:
        terms = load_terms(Path(args.terms))
    except (OSError, ValueError) as error:
        print("could not read terms: {}".format(error))
        return 2
    patterns = [term_pattern(term) for term in terms]

    paths = [Path(raw) for raw in args.paths] or [EXAMPLES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        print("no such path: {}".format(", ".join(missing)))
        return 2

    hits: List[Dict[str, object]] = []
    for path in target_files(paths):
        hits.extend(scan_file(path, patterns, terms))

    if args.json:
        print(json.dumps({"hits": hits, "terms": len(terms)}, indent=2))
    else:
        for hit in hits:
            print("{}:{}: {}".format(hit["path"], hit["line"], hit["term"]))
        print("{} terms, {} hits in {} files".format(
            len(terms), len(hits), len(target_files(paths))))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())

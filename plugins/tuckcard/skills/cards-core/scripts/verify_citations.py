#!/usr/bin/env python3
"""Check that each finding's source exists, matches and is not retracted.

Usage:
    python verify_citations.py [<finding.md> ...]
        [--knowledge DIR] [--responses PATH] [--today YYYY-MM-DD] [--no-move]

DOIs are resolved through the Crossref REST API and PMIDs through
PubMed. A source record is compared with every metadata field the
finding stores: title (whitespace and case ignored), year (exact) and
first author (trimmed and case-folded). Retractions and corrections
are read from Crossref's `update-to` and `updated-by` lists, which
carry publisher and Retraction Watch records. A guidance document with
no DOI or PMID is resolved by URL, its domain is checked against
knowledge/sources-allowlist.yaml, and source.title is compared with
the page title when it is present.

A finding that fails any check is moved to knowledge/quarantine/ with
a quarantine_reason naming the check, the expected value and the value
found. Nothing is deleted. Findings that pass keep their place and
have their verification block updated.

--responses PATH replays recorded HTTP responses from a JSON file (or
from responses.json inside a directory) and never touches the network.
That is how the tests and the default pytest run stay offline. With no
--responses, the script uses the live network.

Exit status is 1 when any finding was quarantined, 0 otherwise.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

import knowledge_files as files
import validate

CROSSREF_WORK = "https://api.crossref.org/works/"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "tuckcard-verify/0.1 (knowledge citation check)"

RETRACTION_SEVERITY = {
    "none": 0,
    "correction": 1,
    "concern": 2,
    "retracted": 3,
}
CROSSREF_TYPES = {
    "retraction": "retracted",
    "retracted": "retracted",
    "expression_of_concern": "concern",
    "expression-of-concern": "concern",
    "correction": "correction",
    "erratum": "correction",
}
METADATA_FIELDS = ("title", "year", "first_author")


class VerifyError(Exception):
    """A check could not be completed; the message goes in the reason."""


class Response(NamedTuple):
    status: int
    body: Any


class RecordedTransport:
    """Serve exactly the responses in a recorded JSON mapping."""

    def __init__(self, mapping: Dict[str, Any]) -> None:
        self.mapping = mapping

    def get(self, url: str) -> Response:
        entry = self.mapping.get(url)
        if entry is None:
            raise VerifyError("no recorded response for {}".format(url))
        if isinstance(entry, dict):
            status = entry.get("status", 200)
            body = entry.get("body", "")
        else:
            status = 200
            body = entry
        return Response(int(status), body)


class LiveTransport:
    """Fetch over the network. Used when --responses is not given."""

    def get(self, url: str) -> Response:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as handle:
                return Response(int(handle.status), handle.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            return Response(int(error.code), error.read().decode("utf-8", "replace"))
        except urllib.error.URLError as error:
            raise VerifyError("network error: {}".format(error.reason))
        except OSError as error:
            raise VerifyError("network error: {}".format(error))


def recorded_mapping(path: Path) -> Dict[str, Any]:
    target = path / "responses.json" if path.is_dir() else path
    with target.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise VerifyError("recorded responses must be a JSON object keyed by URL")
    return data


def crossref_url(doi: str) -> str:
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi).strip())
    return CROSSREF_WORK + urllib.parse.quote(doi, safe="")


def pubmed_url(pmid: Any) -> str:
    return "{}?db=pubmed&id={}&retmode=json".format(PUBMED_ESUMMARY, pmid)


def json_body(response: Response, label: str) -> Any:
    if response.status != 200:
        raise VerifyError("HTTP {}".format(response.status))
    body = response.body
    if isinstance(body, (dict, list)):
        return body
    try:
        return json.loads(body)
    except (TypeError, ValueError):
        raise VerifyError("{} returned a body that is not JSON".format(label))


def first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value


def crossref_year(message: Dict[str, Any]) -> Optional[int]:
    for key in ("issued", "published-print", "published-online", "published"):
        parts = message.get(key)
        if not isinstance(parts, dict):
            continue
        date_parts = parts.get("date-parts")
        if (
            isinstance(date_parts, list)
            and date_parts
            and isinstance(date_parts[0], list)
            and date_parts[0]
            and isinstance(date_parts[0][0], int)
        ):
            return date_parts[0][0]
    return None


def crossref_retraction(message: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """The worst update type on a Crossref record, and where it came from."""
    worst = "none"
    detail: Optional[str] = None
    for key in ("update-to", "updated-by"):
        entries = message.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            kind = CROSSREF_TYPES.get(str(entry.get("type", "")).lower())
            if kind is None:
                continue
            if RETRACTION_SEVERITY[kind] > RETRACTION_SEVERITY[worst]:
                worst = kind
                source = entry.get("source") or "unknown source"
                detail = "Crossref {} {} from {}".format(key, entry.get("type"), source)
    return worst, detail


def crossref_metadata(body: Any) -> Tuple[Dict[str, Any], str, Optional[str]]:
    if not isinstance(body, dict) or not isinstance(body.get("message"), dict):
        raise VerifyError("Crossref returned no message")
    message = body["message"]
    author = first(message.get("author"))
    family = None
    if isinstance(author, dict):
        family = author.get("family") or author.get("name")
    metadata = {
        "title": first(message.get("title")),
        "year": crossref_year(message),
        "first_author": family,
    }
    retraction, detail = crossref_retraction(message)
    return metadata, retraction, detail


def pubmed_family(name: Any) -> Optional[str]:
    if not isinstance(name, str) or not name.strip():
        return None
    parts = name.split()
    if len(parts) > 1 and re.match(r"^[A-Z]{1,3}$", parts[-1]):
        parts = parts[:-1]
    return " ".join(parts)


def pubmed_metadata(body: Any, pmid: Any) -> Tuple[Dict[str, Any], str, Optional[str]]:
    if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
        raise VerifyError("PubMed returned no result")
    result = body["result"]
    record = result.get(str(pmid))
    if not isinstance(record, dict):
        raise VerifyError("PubMed returned no record for PMID {}".format(pmid))
    year = None
    match = re.search(r"\b(1[89][0-9]{2}|20[0-9]{2})\b", str(record.get("pubdate", "")))
    if match:
        year = int(match.group(1))
    authors = record.get("authors")
    author = first(authors)
    family = pubmed_family(author.get("name")) if isinstance(author, dict) else None
    metadata = {
        "title": record.get("title"),
        "year": year,
        "first_author": family,
    }
    pubtypes = [str(item).lower() for item in (record.get("pubtype") or [])]
    retraction = "none"
    detail = None
    if any("retracted publication" in item for item in pubtypes):
        retraction = "retracted"
        detail = "PubMed publication type Retracted Publication"
    elif any("expression of concern" in item for item in pubtypes):
        retraction = "concern"
        detail = "PubMed publication type Expression of Concern"
    elif any(item == "correction" for item in pubtypes):
        retraction = "correction"
        detail = "PubMed publication type Correction"
    return metadata, retraction, detail


def normalize_title(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value))
    return " ".join(text.split()).casefold()


def normalize_author(value: Any) -> str:
    return str(value).strip().casefold()


def value_matches(field: str, expected: Any, found: Any) -> bool:
    if found is None:
        return False
    if field == "title":
        return normalize_title(expected) == normalize_title(found)
    if field == "first_author":
        return normalize_author(expected) == normalize_author(found)
    return expected == found


class TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


def page_title(body: Any) -> str:
    parser = TitleParser()
    parser.feed(body if isinstance(body, str) else str(body))
    parser.close()
    return " ".join("".join(parser.parts).split())


def load_allowlist(path: Path) -> Tuple[Optional[List[str]], Optional[str]]:
    if not path.is_file():
        return None, "sources allowlist not found: {}".format(path)
    try:
        data = files.load_yaml(path)
    except Exception as error:  # noqa: BLE001 - one line
        return None, "sources allowlist unreadable: {}".format(error)
    domains = data.get("domains") if isinstance(data, dict) else None
    if not isinstance(domains, list) or not domains:
        return None, "sources allowlist has no domains: {}".format(path)
    return [str(domain).lower() for domain in domains], None


def domain_allowed(host: str, domains: Sequence[str]) -> bool:
    host = host.lower().strip(".")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def verify_finding(
    data: Dict[str, Any],
    transport: Any,
    domains: Optional[Sequence[str]],
    allowlist_error: Optional[str],
    today: Optional[str] = None,
) -> Dict[str, Any]:
    """Run every check for one finding. Changing nothing on disk."""
    reasons: List[str] = []
    notes: List[str] = []
    compared: List[str] = []
    source = data.get("source") if isinstance(data.get("source"), dict) else {}
    verification = data.get("verification") if isinstance(data.get("verification"), dict) else {}
    retraction = str(verification.get("retraction") or "none")
    detail = None
    resolved = False
    primary: Optional[Tuple[str, Dict[str, Any]]] = None

    doi = source.get("doi")
    pmid = source.get("pmid")
    url = source.get("url")

    if doi:
        try:
            response = transport.get(crossref_url(str(doi)))
            metadata, found_retraction, found_detail = crossref_metadata(
                json_body(response, "Crossref")
            )
            resolved = True
            primary = ("Crossref", metadata)
            if RETRACTION_SEVERITY[found_retraction] > RETRACTION_SEVERITY[retraction]:
                retraction = found_retraction
                detail = found_detail
        except VerifyError as error:
            reasons.append("DOI {} did not resolve ({})".format(doi, error))

    if pmid:
        try:
            response = transport.get(pubmed_url(pmid))
            metadata, found_retraction, found_detail = pubmed_metadata(
                json_body(response, "PubMed"), pmid
            )
            resolved = True
            if primary is None:
                primary = ("PubMed", metadata)
            if RETRACTION_SEVERITY[found_retraction] > RETRACTION_SEVERITY[retraction]:
                retraction = found_retraction
                detail = found_detail
        except VerifyError as error:
            reasons.append("PMID {} did not resolve ({})".format(pmid, error))

    if not doi and not pmid:
        if not url:
            reasons.append("no DOI, PMID or URL to verify")
        elif allowlist_error:
            reasons.append(allowlist_error)
        else:
            host = urllib.parse.urlparse(str(url)).hostname
            if not host:
                reasons.append("URL {} has no host".format(url))
            elif not domain_allowed(host, domains or []):
                reasons.append(
                    "URL domain {!r} is not on knowledge/sources-allowlist.yaml".format(host)
                )
            else:
                try:
                    response = transport.get(str(url))
                    if response.status != 200:
                        raise VerifyError("HTTP {}".format(response.status))
                    resolved = True
                    expected_title = source.get("title")
                    if expected_title is None:
                        notes.append(
                            "title comparison skipped: source.title is absent"
                        )
                    else:
                        compared.append("title")
                        found = page_title(response.body)
                        if not value_matches("title", expected_title, found):
                            reasons.append(
                                "metadata mismatch: title expected {!r}, found {!r} (page)".format(
                                    expected_title, found
                                )
                            )
                except VerifyError as error:
                    reasons.append("URL {} did not resolve ({})".format(url, error))

    if primary is not None:
        label, metadata = primary
        for field in ("title", "year", "first_author"):
            expected = source.get(field)
            if expected is None:
                continue
            compared.append(field)
            found = metadata.get(field)
            if not value_matches(field, expected, found):
                reasons.append(
                    "metadata mismatch: {} expected {!r}, found {!r} ({})".format(
                        field, expected, found, label
                    )
                )

    if retraction in ("retracted", "concern"):
        reasons.append(
            "source is {} ({})".format(retraction, detail or "source record")
        )

    checked = {
        "exists": "script" if resolved or reasons else "none",
        "metadata_match": [field for field in METADATA_FIELDS if field in compared],
        "retraction": retraction,
        "checked_on": today or datetime.date.today().isoformat(),
    }
    if not resolved and not reasons:
        reasons.append("the source could not be resolved")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "checked": checked,
        "notes": notes,
    }


def apply_checked(data: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    updated = copy.deepcopy(data)
    verification = updated.setdefault("verification", {})
    if not isinstance(verification, dict):
        verification = {}
        updated["verification"] = verification
    verification.update(result["checked"])
    return updated


def quarantine_file(
    path: Path,
    data: Dict[str, Any],
    body: str,
    result: Dict[str, Any],
    quarantine_dir: Path,
    reason: Optional[str] = None,
) -> Path:
    """Write the updated finding into quarantine and remove the original."""
    updated = apply_checked(data, result)
    updated["status"] = "quarantined"
    updated["quarantine_reason"] = reason or "; ".join(result["reasons"])
    errors = validate.schema_errors(updated, "finding")
    if errors:
        raise VerifyError(
            "quarantined finding would not validate: {}".format("; ".join(errors))
        )
    if path.parent.resolve() == quarantine_dir.resolve():
        target = path
    else:
        target = files.unique_path(quarantine_dir, path.name)
    files.write_frontmatter(target, updated, body)
    if target.resolve() != path.resolve():
        path.unlink()
    return target


def check_path(
    path: Path,
    transport: Any,
    domains: Optional[Sequence[str]],
    allowlist_error: Optional[str],
    quarantine_dir: Path,
    today: Optional[str],
    move: bool = True,
) -> Tuple[bool, List[str]]:
    """Check one file. Returns (passed, output lines)."""
    try:
        data, body = files.read_frontmatter(path)
    except Exception as error:  # noqa: BLE001 - one line
        return False, ["{}: could not read finding: {}".format(path, error)]
    result = verify_finding(data, transport, domains, allowlist_error, today)
    if result["ok"]:
        updated = apply_checked(data, result)
        files.write_frontmatter(path, updated, body)
        line = "{}: ok ({}; metadata {}; retraction {})".format(
            path,
            result["checked"]["exists"],
            ", ".join(result["checked"]["metadata_match"]) or "none present",
            result["checked"]["retraction"],
        )
        return True, [line] + ["  note: " + note for note in result["notes"]]
    reason = "; ".join(result["reasons"])
    if not move:
        return False, ["{}: would quarantine: {}".format(path, reason)]
    try:
        target = quarantine_file(path, data, body, result, quarantine_dir)
    except VerifyError as error:
        return False, ["{}: quarantine failed: {}".format(path, error)]
    return False, [
        "{}: quarantine: {}".format(path, reason),
        "  moved to {}".format(target),
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check finding sources. Exit 1 when a finding is quarantined."
    )
    parser.add_argument("paths", nargs="*", help="finding files to check")
    parser.add_argument(
        "--knowledge",
        default=str(files.KNOWLEDGE_DIR),
        help="knowledge folder holding findings, quarantine and the allowlist",
    )
    parser.add_argument(
        "--responses",
        help="recorded responses JSON file or folder; no network is used",
    )
    parser.add_argument("--today", help="date to record as checked_on")
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="report what would be quarantined without moving files",
    )
    args = parser.parse_args(argv)

    knowledge = Path(args.knowledge)
    findings_dir = knowledge / "findings"
    quarantine_dir = knowledge / "quarantine"
    paths = (
        [Path(raw) for raw in args.paths]
        if args.paths
        else files.finding_paths(findings_dir)
    )
    if not paths:
        print("no findings to check in {}".format(findings_dir))
        return 0

    if args.responses:
        try:
            transport: Any = RecordedTransport(recorded_mapping(Path(args.responses)))
        except (OSError, ValueError, VerifyError) as error:
            print("could not read recorded responses: {}".format(error))
            return 1
    else:
        transport = LiveTransport()

    domains, allowlist_error = load_allowlist(knowledge / "sources-allowlist.yaml")
    failures = 0
    for path in paths:
        passed, lines = check_path(
            path,
            transport,
            domains,
            allowlist_error,
            quarantine_dir,
            args.today,
            move=not args.no_move,
        )
        for line in lines:
            print(line)
        if not passed:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

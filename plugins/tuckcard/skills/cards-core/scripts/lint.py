#!/usr/bin/env python3
"""Lint a Tuckcard deck the way the skills' steps call for.

Usage:
    python lint.py <deck.yaml> [--rules PATH] [--knowledge DIR]
        [--overlay DIR ...] [--findings DIR ...] [--cards N,N]
        [--no-default-overlay] [--json]

Reads the deck and its compiled ``effective-rules.yaml`` and reports what it
can decide without a judgment call:

- schema and cross-file validity (delegated to ``validate.py``)
- the ``lint`` pattern of every compiled rule with ``check: lint`` or ``both``
- format limits and reading targets from the deck's age-band file
- fit against the deck's layout, when Pillow is installed
- help resources: every URL or phone number on a card must match a verified
  grade-D finding exactly; a number matches when its digits equal one printed
  in the finding's claim or anchor, with a single leading 1 read as the US
  country code, and 911 and 988 are always read as phone numbers
- visibility: a card naming a confirmed personal detail should be private
- repetition: duplicate titles and lines, and lines reused from the examples
- hand edits: cards whose content matches neither approval hash

Exit 1 when there is at least one error, 0 otherwise. Warnings and skipped
checks never fail the run; a skipped check is reported with its reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import knowledge_files as files
import validate

URL_RE = re.compile(r"https?://[^\s<>\"']+")
# A number as printed, separators included. The span starts at a digit that is
# not glued to a word, so an identifier or a URL path is not a phone reference.
NUMBER_SPAN_RE = re.compile(r"(?<![\w])\+?\d[\d().\- ]*")
# Bare short codes are phone references wherever they stand. D-035 names the
# list; do not widen it to every three-digit number, which would make a year or
# a score a phone number.
SHORT_CODES = {"911", "988"}
SHORT_CODE_RE = re.compile(r"(?<![\w])(?:911|988)(?![\w])")
NUMBER_SEPARATOR_RE = re.compile(r"[\s.\-()]")
WORD_RE = re.compile(r"[A-Za-z']+")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")
TEMPLATE_NAMES = {"_TEMPLATE.yaml", "_TEMPLATE.md"}


def clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def line_text(line: Dict[str, Any]) -> str:
    return clean_text(line.get("text"))


def card_texts(card: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(field, text) for every writer-visible piece of the card."""
    pieces: List[Tuple[str, str]] = [("title", clean_text(card.get("title")))]
    lines = card.get("lines")
    if isinstance(lines, list):
        for line in lines:
            if not isinstance(line, dict):
                continue
            pieces.append(("lines", line_text(line)))
            pieces.append(("notes", clean_text(line.get("note"))))
    return [(field, text) for field, text in pieces if text]


def joined_text(card: Dict[str, Any]) -> str:
    return " ".join(text for _, text in card_texts(card))


def finding(level: str, check: str, message: str,
            card: Optional[int] = None, field: Optional[str] = None,
            rule: Optional[str] = None, why: Optional[str] = None) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"level": level, "check": check, "message": message}
    if card is not None:
        entry["card"] = card
    if field is not None:
        entry["field"] = field
    if rule is not None:
        entry["rule"] = rule
    if why:
        entry["why"] = why
    return entry


# ---------------------------------------------------------------- schema


def check_schema(deck_path: Path) -> List[Dict[str, Any]]:
    return [finding("error", "schema", problem)
            for problem in validate.validate_file(deck_path)]


# ---------------------------------------------------------------- rules


def rule_regex(rule: Dict[str, Any]) -> Tuple[Optional["re.Pattern"], Optional[str]]:
    spec = rule.get("lint")
    if not isinstance(spec, dict) or not spec.get("pattern"):
        return None, "rule {}: check includes lint but lint.pattern is missing".format(
            rule.get("id"))
    flags = 0
    for letter in str(spec.get("flags") or ""):
        flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}.get(letter, 0)
    try:
        return re.compile(str(spec["pattern"]), flags), None
    except re.error as error:
        return None, "rule {}: lint.pattern does not compile: {}".format(
            rule.get("id"), error)


def card_in_rule_scope(rule: Dict[str, Any], card: Dict[str, Any]) -> bool:
    categories = rule.get("categories")
    if isinstance(categories, list) and categories:
        return card.get("category") in categories
    if isinstance(categories, list):
        return False
    return True


def check_rules(rules: Iterable[Dict[str, Any]], cards: Sequence[Dict[str, Any]],
                selected: Optional[set]) -> Tuple[List[Dict[str, Any]], List[str]]:
    findings: List[Dict[str, Any]] = []
    notes: List[str] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("check") not in ("lint", "both"):
            continue
        regex, problem = rule_regex(rule)
        if problem:
            notes.append(problem)
            continue
        level = "error" if rule.get("strength") == "must" else "warning"
        applies = rule.get("applies_to")
        fields = applies if isinstance(applies, list) and applies else ["title", "lines", "notes"]
        for card in cards:
            number = card.get("n")
            if selected is not None and number not in selected:
                continue
            if not card_in_rule_scope(rule, card):
                continue
            for field, text in card_texts(card):
                if field not in fields:
                    continue
                match = regex.search(text)
                if match:
                    findings.append(finding(
                        level, "rules",
                        "matches {!r}: {}".format(match.group(0), rule.get("text") or ""),
                        card=number, field=field, rule=rule.get("id"),
                        why=rule.get("why")))
    return findings, notes


# ---------------------------------------------------------------- format


def age_defaults(band: str, knowledge: Path,
                 overlays: Sequence[Path]) -> Tuple[Dict[str, Any], Optional[Path]]:
    """The age-band file's defaults. An overlay's file wins over the shipped one."""
    for root in [overlay / "rules" for overlay in overlays] + [knowledge / "rules"]:
        path = root / "age" / "{}.yaml".format(band)
        if path.is_file():
            data = files.load_yaml(path)
            if isinstance(data, dict) and isinstance(data.get("defaults"), dict):
                return data["defaults"], path
            return {}, path
    return {}, None


def defaults_get(defaults: Dict[str, Any], group: str, key: str) -> Any:
    section = defaults.get(group)
    return section.get(key) if isinstance(section, dict) else None


def check_format(cards: Sequence[Dict[str, Any]], defaults: Dict[str, Any],
                 selected: Optional[set]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    max_title = defaults_get(defaults, "card", "max_title_words")
    max_lines = defaults_get(defaults, "card", "max_lines")
    max_words = defaults_get(defaults, "card", "max_words_per_line")
    for card in cards:
        if selected is not None and card.get("n") not in selected:
            continue
        title = clean_text(card.get("title"))
        if isinstance(max_title, int) and len(title.split()) > max_title:
            findings.append(finding(
                "warning", "format",
                "title is {} words, the band's limit is {}".format(
                    len(title.split()), max_title),
                card=card.get("n"), field="title"))
        lines = card.get("lines")
        if not isinstance(lines, list):
            continue
        if isinstance(max_lines, int) and len(lines) > max_lines:
            findings.append(finding(
                "warning", "format",
                "card has {} lines, the band's limit is {}".format(
                    len(lines), max_lines),
                card=card.get("n")))
        if isinstance(max_words, int):
            for line in lines:
                if not isinstance(line, dict):
                    continue
                count = len(line_text(line).split())
                if count > max_words:
                    findings.append(finding(
                        "warning", "format",
                        "line is {} words, the band's limit is {}".format(
                            count, max_words),
                        card=card.get("n"), field="lines"))
    return findings


# ---------------------------------------------------------------- reading


def syllables(word: str) -> int:
    """A vowel-group count, after dropping a silent final e.

    It is an estimate: readability formulas disagree on unusual words, and the
    lint report names the word so a person can overrule it.
    """
    letters = re.sub(r"[^a-z]", "", word.lower())
    if not letters:
        return 0
    count = len(re.findall(r"[aeiouy]+", letters))
    if letters.endswith("e") and count > 1 and not letters.endswith(("le", "ee")):
        count -= 1
    return max(1, count)


def words_of(text: str) -> List[str]:
    return WORD_RE.findall(text)


def flesch_kincaid_grade(text: str) -> Optional[float]:
    words = words_of(text)
    if not words:
        return None
    sentences = max(1, len([part for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]))
    syllables_total = sum(syllables(word) for word in words)
    words_per_sentence = len(words) / sentences
    syllables_per_word = syllables_total / len(words)
    return 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59


def load_familiarity(value: Any, age_path: Optional[Path]) -> Tuple[Optional[set], Optional[str]]:
    if not isinstance(value, str) or not value:
        return None, None
    path = Path(value)
    if not path.is_absolute() and age_path is not None:
        path = age_path.parent / path
    if not path.is_file():
        return None, "familiarity list {} is missing".format(value)
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            words.add(line)
    return words, None


def check_reading(cards: Sequence[Dict[str, Any]], defaults: Dict[str, Any],
                  age_path: Optional[Path],
                  selected: Optional[set]) -> Tuple[List[Dict[str, Any]], List[str]]:
    findings: List[Dict[str, Any]] = []
    notes: List[str] = []
    max_syllables = defaults_get(defaults, "reading", "max_avg_syllables_per_word")
    familiarity_words, problem = load_familiarity(
        defaults_get(defaults, "reading", "familiarity_list"), age_path)
    if problem:
        notes.append(problem)
    fk_limit = defaults_get(defaults, "reading", "deck_fk_grade_warning")

    deck_text: List[str] = []
    for card in cards:
        text = joined_text(card)
        deck_text.append(text)
        if selected is not None and card.get("n") not in selected:
            continue
        words = words_of(text)
        if isinstance(max_syllables, (int, float)) and max_syllables and words:
            average = sum(syllables(word) for word in words) / len(words)
            if average > float(max_syllables):
                findings.append(finding(
                    "warning", "reading",
                    "average {:.2f} syllables per word, the band's limit is {}".format(
                        average, max_syllables),
                    card=card.get("n")))
        if familiarity_words is not None and words:
            unknown = sorted({word.lower() for word in words
                              if word.lower() not in familiarity_words})
            if unknown:
                findings.append(finding(
                    "warning", "reading",
                    "words outside the band's familiarity list: {}".format(
                        ", ".join(unknown)),
                    card=card.get("n")))
    if isinstance(fk_limit, (int, float)):
        grade = flesch_kincaid_grade(" ".join(deck_text))
        if grade is not None and grade > float(fk_limit):
            findings.append(finding(
                "warning", "reading",
                "deck reads at grade {:.1f}; the band warns above {}".format(
                    grade, fk_limit)))
    if max_syllables is None and familiarity_words is None:
        notes.append("reading targets are not set for this age band")
    return findings, notes


# ---------------------------------------------------------------- help


def is_phone_token(token: str, digits: str) -> bool:
    """True when a printed number is a phone reference.

    A short code is one. A number of eight digits or more is one, which keeps
    the ten- and eleven-digit behaviour. A seven-digit number is one only when
    it carries a separator, so 555-0100 counts while 2026 and a 3-2 score do
    not. D-035.
    """
    if digits in SHORT_CODES:
        return True
    if len(digits) >= 8:
        return True
    return len(digits) == 7 and bool(NUMBER_SEPARATOR_RE.search(token))


def phone_tokens(text: str) -> List[str]:
    """The digit strings of the phone references in text.

    Each printed number is trimmed of trailing separators before its digits are
    counted. A span that holds two short codes separated only by spaces, such
    as "988 911", is split when the span as a whole is not a phone number.
    """
    found: List[str] = []
    for match in NUMBER_SPAN_RE.finditer(text):
        token = match.group(0).rstrip(" ().-")
        digits = re.sub(r"\D", "", token)
        if is_phone_token(token, digits):
            found.append(digits)
        else:
            found.extend(SHORT_CODE_RE.findall(token))
    return found


def digit_forms(digits: str) -> set:
    """The forms one printed number may take.

    A single leading 1 is the US country code, so 800-273-8255 and
    1-800-273-8255 are the same number. Nothing else is stripped, so a partial
    number never equals a complete one. D-035.
    """
    forms = {digits} if digits else set()
    if len(digits) == 11 and digits.startswith("1"):
        forms.add(digits[1:])
    return forms


def resource_numbers(text: str) -> set:
    """Every number printed in a resource's claim or anchor, in all its forms."""
    numbers: set = set()
    for match in NUMBER_SPAN_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0).rstrip(" ().-"))
        numbers |= digit_forms(digits)
    return numbers


def verified_help(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Active grade-D findings with a URL check, the resources a card may name."""
    resources: List[Dict[str, Any]] = []
    for data in findings:
        source = data.get("source") if isinstance(data.get("source"), dict) else {}
        verification = data.get("verification") if isinstance(data.get("verification"), dict) else {}
        url = clean_text(source.get("url"))
        if not url or data.get("status") != "active" or data.get("grade") != "D":
            continue
        if verification.get("exists") not in ("fetch", "script"):
            continue
        spoken = " ".join([clean_text(data.get("claim")),
                           clean_text(verification.get("anchor"))])
        resources.append({
            "id": str(data.get("id") or ""),
            "url": url,
            "numbers": resource_numbers(spoken),
        })
    return resources


def load_findings(directories: Sequence[Path]) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name in TEMPLATE_NAMES:
                continue
            try:
                data, _ = files.read_frontmatter(path)
            except Exception:  # noqa: BLE001 - a broken finding is another tool's error
                continue
            if isinstance(data, dict):
                pool.append(files.normalize(data))
    return pool


def card_help_refs(card: Dict[str, Any]) -> List[Tuple[str, str]]:
    """(kind, value) for each URL and phone number on the card."""
    refs: List[Tuple[str, str]] = []
    text = joined_text(card)
    for match in URL_RE.finditer(text):
        refs.append(("url", match.group(0).rstrip(".,;:)")))
    for digits in phone_tokens(URL_RE.sub(" ", text)):
        refs.append(("phone", digits))
    return refs


def check_help(cards: Sequence[Dict[str, Any]],
               resources: Sequence[Dict[str, Any]],
               selected: Optional[set]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    urls = {resource["url"] for resource in resources}
    numbers: set = set()
    for resource in resources:
        numbers |= set(resource.get("numbers") or ())
    for card in cards:
        if selected is not None and card.get("n") not in selected:
            continue
        for kind, value in card_help_refs(card):
            matched = value in urls if kind == "url" else bool(
                digit_forms(value) & numbers)
            if matched:
                continue
            findings.append(finding(
                "error", "help",
                "{} does not match a verified help resource exactly".format(
                    "URL " + value if kind == "url" else "phone number " + value),
                card=card.get("n")))
    return findings


# ---------------------------------------------------------------- visibility


def check_visibility(cards: Sequence[Dict[str, Any]], deck: Dict[str, Any],
                     selected: Optional[set]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    details = deck.get("personal_details")
    if not isinstance(details, list):
        return findings
    confirmed = [clean_text(item.get("text")).lower()
                 for item in details if isinstance(item, dict) and item.get("confirmed")
                 and clean_text(item.get("text"))]
    if not confirmed:
        return findings
    for card in cards:
        if selected is not None and card.get("n") not in selected:
            continue
        if card.get("visibility") == "private":
            continue
        text = joined_text(card).lower()
        named = [detail for detail in confirmed if detail in text]
        if named:
            findings.append(finding(
                "warning", "visibility",
                "names a confirmed personal detail but is marked public",
                card=card.get("n")))
    return findings


# ---------------------------------------------------------------- repetition


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip(" .!?")


def example_lines(examples: Path, skip: Optional[Path] = None) -> Dict[str, str]:
    """Normalized example line to the example deck's name."""
    seen: Dict[str, str] = {}
    if not examples.is_dir():
        return seen
    skipped = skip.resolve() if skip is not None else None
    for path in sorted(examples.rglob("*.yaml")):
        if skipped is not None and path.resolve() == skipped:
            continue
        try:
            deck = files.load_yaml(path)
        except Exception:  # noqa: BLE001 - an unreadable example is not this deck's error
            continue
        cards = deck.get("cards") if isinstance(deck, dict) else None
        if not isinstance(cards, list):
            continue
        for card in cards:
            lines = card.get("lines") if isinstance(card, dict) else None
            if not isinstance(lines, list):
                continue
            for line in lines:
                if not isinstance(line, dict):
                    continue
                text = normalize_line(line_text(line))
                if text:
                    seen.setdefault(text, path.parent.name)
    return seen


def check_repetition(cards: Sequence[Dict[str, Any]], examples: Dict[str, str],
                     selected: Optional[set]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    titles: Dict[str, int] = {}
    lines: Dict[str, int] = {}
    for card in cards:
        number = card.get("n")
        title = normalize_line(clean_text(card.get("title")))
        if title:
            if title in titles:
                findings.append(finding(
                    "warning", "repetition",
                    "title repeats card {}".format(titles[title]),
                    card=number, field="title"))
            else:
                titles[title] = number
        raw_lines = card.get("lines")
        if not isinstance(raw_lines, list):
            continue
        for line in raw_lines:
            if not isinstance(line, dict):
                continue
            text = normalize_line(line_text(line))
            if not text:
                continue
            if text in lines:
                findings.append(finding(
                    "warning", "repetition",
                    "line repeats card {}".format(lines[text]),
                    card=number, field="lines"))
            else:
                lines[text] = number
            if text in examples and (selected is None or number in selected):
                findings.append(finding(
                    "warning", "repetition",
                    "line is reused verbatim from examples/{}".format(examples[text]),
                    card=number, field="lines"))
    return findings


# ---------------------------------------------------------------- hand edits


def card_content(card: Dict[str, Any]) -> Dict[str, Any]:
    """The covered fields of SPEC.md section 6's approval hash."""
    lines: List[Dict[str, Any]] = []
    raw_lines = card.get("lines")
    if isinstance(raw_lines, list):
        for line in raw_lines:
            if not isinstance(line, dict):
                continue
            mark = line.get("mark")
            mark_data = None
            if isinstance(mark, dict):
                mark_data = {
                    "target": mark.get("target"),
                    "occurrence": mark.get("occurrence", 1),
                }
                if "style" in mark:
                    mark_data["style"] = mark["style"]
            lines.append({"text": line.get("text"), "mark": mark_data,
                          "note": line.get("note")})
    return {
        "title": card.get("title"),
        "lines": lines,
        "category": card.get("category"),
        "visibility": card.get("visibility"),
    }


def card_hash(card: Dict[str, Any]) -> str:
    payload = json.dumps(card_content(card), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def strip_hash(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return value[7:] if value.startswith("sha256:") else value


def check_hand_edits(cards: Sequence[Dict[str, Any]],
                     selected: Optional[set]) -> Tuple[List[Dict[str, Any]], List[int]]:
    findings: List[Dict[str, Any]] = []
    edited: List[int] = []
    for card in cards:
        approval = card.get("approval")
        if not isinstance(approval, dict):
            continue
        digest = card_hash(card)
        known = {strip_hash(approval.get("approved_hash")),
                 strip_hash(approval.get("linted_hash"))}
        if digest in known:
            continue
        edited.append(card.get("n"))
        if selected is None or card.get("n") in selected:
            findings.append(finding(
                "warning", "hand-edit",
                "content matches neither approval hash; edited since approval",
                card=card.get("n")))
    return findings, edited


# ---------------------------------------------------------------- fit


def check_fit(deck: Dict[str, Any], cards: Sequence[Dict[str, Any]],
              selected: Optional[set]) -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        import render_core  # noqa: PLC0415
    except Exception:  # noqa: BLE001 - Pillow or the shared module is missing
        return [], ["layout fit is skipped: the renderer needs Pillow"]
    findings: List[Dict[str, Any]] = []
    try:
        style = render_core.style_from_deck(deck)
    except Exception as error:  # noqa: BLE001
        return [], ["layout fit is skipped: {}".format(error)]
    for card in cards:
        if selected is not None and card.get("n") not in selected:
            continue
        try:
            plan = render_core.build_plan(card, style)
        except Exception as error:  # noqa: BLE001
            findings.append(finding(
                "error", "fit", "could not build a render plan: {}".format(error),
                card=card.get("n")))
            continue
        report = plan.get("report") or {}
        if report.get("failed"):
            findings.append(finding(
                "error", "fit", "does not fit the {} layout at the font floors".format(
                    deck.get("style", {}).get("layout")),
                card=card.get("n")))
        elif report.get("shrunk"):
            findings.append(finding(
                "warning", "fit", "shrunk to fit the {} layout".format(
                    deck.get("style", {}).get("layout")),
                card=card.get("n")))
    return findings, []


# ---------------------------------------------------------------- main


def parse_cards(value: Optional[str]) -> Optional[set]:
    if not value:
        return None
    numbers = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            numbers.add(int(part))
        except ValueError:
            raise SystemExit("--cards wants card numbers, got {!r}".format(part))
    return numbers or None


def lint_deck(deck_path: Path, rules_path: Optional[Path], knowledge: Path,
              overlays: Sequence[Path], extra_findings: Sequence[Path],
              selected: Optional[set]) -> Dict[str, Any]:
    deck = files.load_yaml(deck_path)
    if not isinstance(deck, dict):
        raise SystemExit("{}: deck is not a mapping".format(deck_path))

    effective: Dict[str, Any] = {}
    if rules_path is None or not rules_path.is_file():
        raise SystemExit("{}: no rules snapshot; run compile_rules.py first".format(
            rules_path or deck_path.parent / "effective-rules.yaml"))
    loaded = files.load_yaml(rules_path)
    if isinstance(loaded, dict):
        effective = loaded
    rules = effective.get("rules") if isinstance(effective.get("rules"), list) else []

    cards = [card for card in (deck.get("cards") or []) if isinstance(card, dict)]
    recipient = deck.get("recipient") if isinstance(deck.get("recipient"), dict) else {}
    band = recipient.get("age_band") if isinstance(recipient.get("age_band"), str) else ""

    findings: List[Dict[str, Any]] = []
    notes: List[str] = []
    findings.extend(check_schema(deck_path))

    produced, rule_notes = check_rules(rules, cards, selected)
    findings.extend(produced)
    notes.extend(rule_notes)

    defaults, age_path = age_defaults(band, knowledge, overlays)
    findings.extend(check_format(cards, defaults, selected))
    produced, reading_notes = check_reading(cards, defaults, age_path, selected)
    findings.extend(produced)
    notes.extend(reading_notes)

    finding_dirs = [knowledge / "findings"] + [overlay / "findings" for overlay in overlays]
    finding_dirs.extend(extra_findings)
    resources = verified_help(load_findings(finding_dirs))
    findings.extend(check_help(cards, resources, selected))
    findings.extend(check_visibility(cards, deck, selected))
    findings.extend(check_repetition(
        cards, example_lines(files.CORE_DIR / "examples", deck_path), selected))
    produced, edited = check_hand_edits(cards, selected)
    findings.extend(produced)
    produced, fit_notes = check_fit(deck, cards, selected)
    findings.extend(produced)
    notes.extend(fit_notes)

    findings.sort(key=lambda item: (
        item.get("card") is not None,
        item.get("card") or 0, item["check"], item.get("field") or "", item["message"],
    ))
    errors = sum(1 for item in findings if item["level"] == "error")
    warnings = len(findings) - errors
    return {
        "deck_id": deck.get("id"),
        "deck_status": deck.get("status"),
        "cards_checked": len([card for card in cards
                              if selected is None or card.get("n") in selected]),
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "notes": notes,
        "hand_edited": edited,
    }


def show(report: Dict[str, Any]) -> None:
    for item in report["findings"]:
        where = "card {}".format(item["card"]) if "card" in item else "deck"
        if "field" in item:
            where += " {}".format(item["field"])
        rule = " [{}]".format(item["rule"]) if item.get("rule") else ""
        print("{}: {}: {}{}".format(item["level"], where, item["message"], rule))
        if item.get("why"):
            print("  why: {}".format(item["why"]))
    for note in report["notes"]:
        print("note: {}".format(note))
    print("{}: {} cards, {} errors, {} warnings".format(
        report["deck_id"], report["cards_checked"],
        report["errors"], report["warnings"]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint a Tuckcard deck against its compiled rules. Exit 1 on errors."
    )
    parser.add_argument("deck", help="path to deck.yaml")
    parser.add_argument("--rules", help="compiled rules file (default: the deck's snapshot)")
    parser.add_argument("--knowledge", default=str(files.KNOWLEDGE_DIR),
                        help="shipped knowledge folder")
    parser.add_argument("--overlay", action="append", default=[],
                        help="overlay knowledge folder (repeatable)")
    parser.add_argument("--findings", action="append", default=[],
                        help="extra findings folder (repeatable)")
    parser.add_argument("--cards", help="comma-separated card numbers to lint")
    parser.add_argument("--no-default-overlay", action="store_true",
                        help="do not add local/knowledge when it exists")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    deck_path = Path(args.deck)
    overlays = [Path(raw) for raw in args.overlay]
    if not args.no_default_overlay and not args.overlay:
        local = Path("local/knowledge")
        if local.is_dir():
            overlays.append(local)
    rules_path = Path(args.rules) if args.rules else None
    if rules_path is None:
        try:
            deck = files.load_yaml(deck_path)
        except Exception:  # noqa: BLE001 - lint_deck reports the real problem
            deck = {}
        snapshot = deck.get("rules_snapshot") if isinstance(deck, dict) else None
        filename = snapshot.get("file") if isinstance(snapshot, dict) else None
        rules_path = deck_path.parent / (filename if isinstance(filename, str)
                                         else "effective-rules.yaml")
    report = lint_deck(
        deck_path, rules_path, Path(args.knowledge), overlays,
        [Path(raw) for raw in args.findings], parse_cards(args.cards),
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        show(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

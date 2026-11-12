"""Generate THIRD_PARTY.md and fail on a copyleft or unknown license.

    python tools/third_party.py            # write THIRD_PARTY.md
    python tools/third_party.py --check    # exit 1 when the file is stale

The file covers the shipped fonts, the Python dependencies pinned in
requirements.txt and requirements-dev.txt, and the word-familiarity list.
Each dependency's license is read from the installed distribution and checked
against ALLOWED. A copyleft license fails, and so does a license that is not
on the list: unfamiliar is not the same as permissive. To allow a new one, add
it to ALLOWED with the reason it belongs, in the same change.

The output carries no timestamp and every table is sorted, so the same pins
and the same installed metadata give the same bytes.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
FONTS = CORE / "fonts"
KNOWLEDGE = CORE / "knowledge"
REQUIREMENTS = (ROOT / "requirements.txt", ROOT / "requirements-dev.txt")
OUT = ROOT / "THIRD_PARTY.md"

HEADER = "<!-- generated, don't edit: run python tools/third_party.py -->"

# Permissive licenses this project accepts, with the reason each is listed.
ALLOWED: Dict[str, str] = {
    "MIT": "permissive; attribution only",
    "MIT-0": "permissive; no attribution condition",
    "MIT-CMU": "Pillow's MIT variant; permissive, attribution only",
    "HPND": "historical permissive license; attribution only",
    "BSD-2-Clause": "permissive; attribution only",
    "BSD-3-Clause": "permissive; attribution only",
    "Apache-2.0": "permissive; attribution and patent grant",
    "PSF-2.0": "Python Software Foundation license; permissive",
    "ISC": "permissive; attribution only",
    "Unlicense": "public domain dedication",
    "CC0-1.0": "public domain dedication",
    "Zlib": "permissive; attribution only",
}

# License families that would oblige a fork to publish its source, or that a
# permissive-only inventory cannot carry. Checked before ALLOWED so the error
# names the problem plainly.
COPYLEFT_PREFIXES = (
    "AGPL-", "GPL-", "LGPL-", "MPL-", "EPL-", "CDDL-", "OSL-", "EUPL-",
    "CC-BY-SA", "SSPL-",
)

# Common spellings in the legacy License field or a classifier, mapped to the
# identifier the allowlist uses. Anything not here is unknown, not guessed.
SPELLINGS = {
    "mit license": "MIT",
    "mit": "MIT",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "bsd license": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "isc license": "ISC",
    "isc": "ISC",
    "python software foundation license": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
}

PIN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*([^\s;#]+)")


class ThirdPartyError(Exception):
    """A license problem, reported as one line by main."""


@dataclass(frozen=True)
class Pin:
    name: str
    version: str
    source: str


@dataclass(frozen=True)
class Dependency:
    name: str
    version: str
    license: str
    source: str


@dataclass(frozen=True)
class FontRow:
    family: str
    files: int
    license: str
    license_file: str


def pinned_requirements(paths: Sequence[Path]) -> List[Pin]:
    """The ``name==version`` pins in the given files, sorted by name."""
    found: Dict[str, Pin] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise ThirdPartyError("{}: could not read requirements: {}".format(
                path, " ".join(str(error).split())))
        for line in text.splitlines():
            match = PIN.match(line)
            if not match:
                continue
            name, version = match.group(1), match.group(2)
            key = name.lower()
            if key in found and found[key].version != version:
                raise ThirdPartyError(
                    "{}: {} is pinned to {} here and {} in {}".format(
                        path, name, version, found[key].version, found[key].source))
            found.setdefault(key, Pin(name, version, path.name))
    if not found:
        raise ThirdPartyError("no pinned dependencies found in {}".format(
            ", ".join(path.name for path in paths)))
    return [found[key] for key in sorted(found)]


def license_label(name: str, info: Mapping[str, object]) -> str:
    """The license identifier a distribution declares, normalised."""
    expression = str(info.get("License-Expression") or "").strip()
    if expression:
        return expression
    declared = str(info.get("License") or "").strip()
    if declared:
        key = " ".join(declared.split()).lower()
        if key in SPELLINGS:
            return SPELLINGS[key]
        if len(declared) <= 40 and "\n" not in declared:
            return declared
    classifiers = info.get("Classifier") or []
    if isinstance(classifiers, str):
        classifiers = [classifiers]
    for classifier in classifiers:
        prefix = "License :: OSI Approved :: "
        if str(classifier).startswith(prefix):
            tail = str(classifier)[len(prefix):]
            key = " ".join(tail.split()).lower()
            if key in SPELLINGS:
                return SPELLINGS[key]
            return tail
    raise ThirdPartyError(
        "{}: no license in its installed metadata, so it cannot be allowed "
        "by name".format(name))


def check_license(name: str, license_id: str) -> None:
    """Raise unless the license is explicitly allowed and not copyleft."""
    for prefix in COPYLEFT_PREFIXES:
        if license_id.upper().startswith(prefix):
            raise ThirdPartyError(
                "{}: {} is a copyleft license; this project ships only "
                "permissive dependencies".format(name, license_id))
    if license_id not in ALLOWED:
        raise ThirdPartyError(
            "{}: {} is not on the allowed license list; add it to ALLOWED "
            "in tools/third_party.py with the reason it belongs, or replace "
            "the dependency".format(name, license_id))


def _metadata_view(distribution) -> Dict[str, object]:
    """The metadata fields this tool reads, with every classifier kept."""
    info = distribution.metadata
    return {
        "License-Expression": info.get("License-Expression"),
        "License": info.get("License"),
        "Classifier": info.get_all("Classifier") or [],
    }


def resolve(pins: Iterable[Pin], lookup=None) -> List[Dependency]:
    """Read each pin's installed version and license and check the license."""
    lookup = lookup or metadata.distribution
    rows: List[Dependency] = []
    for pin in pins:
        try:
            distribution = lookup(pin.name)
        except metadata.PackageNotFoundError:
            raise ThirdPartyError(
                "{} is pinned but not installed; run python -m pip install "
                "-r {}".format(pin.name, pin.source))
        version = distribution.version
        if version != pin.version:
            raise ThirdPartyError(
                "{} is installed at {} but pinned to {} in {}; install the "
                "pinned version before generating".format(
                    pin.name, version, pin.version, pin.source))
        license_id = license_label(pin.name, _metadata_view(distribution))
        check_license(pin.name, license_id)
        rows.append(Dependency(pin.name, version, license_id, pin.source))
    return rows


def font_rows(fonts: Path = FONTS) -> List[FontRow]:
    """One row per shipped font family, checked for its OFL license file."""
    if not fonts.is_dir():
        raise ThirdPartyError("{}: no fonts folder".format(fonts))
    rows: List[FontRow] = []
    for folder in sorted(path for path in fonts.iterdir() if path.is_dir()):
        ofl = folder / "OFL.txt"
        files = sorted(folder.glob("*.ttf"))
        if not ofl.is_file():
            raise ThirdPartyError("{}: missing OFL.txt".format(folder.name))
        text = ofl.read_text(encoding="utf-8", errors="replace")
        if "SIL OPEN FONT LICENSE" not in text or "Version 1.1" not in text:
            raise ThirdPartyError(
                "{}: OFL.txt does not name the SIL Open Font License 1.1".format(
                    folder.name))
        if not files:
            raise ThirdPartyError("{}: no font file".format(folder.name))
        try:
            shown = ofl.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            shown = ofl.as_posix()
        rows.append(FontRow(folder.name, len(files), "SIL OFL 1.1", shown))
    return rows


def familiarity_entries(knowledge: Path = KNOWLEDGE) -> List[str]:
    """Age bands that name a familiarity list, or the note that none ships."""
    pattern = re.compile(r"^\s*familiarity_list:\s*(.+?)\s*$")
    named: Dict[str, List[str]] = {}
    age = knowledge / "rules" / "age"
    for path in sorted(age.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match and match.group(1) not in ("null", "~", "None"):
                named.setdefault(match.group(1), []).append(path.stem)
    if not named:
        return [
            "No word-familiarity list is shipped. Every age band sets "
            "`familiarity_list: null`, so lint measures syllables and grade "
            "but does not check word familiarity.",
            "",
            "If one is added later it needs its own license file and an entry "
            "here, and it must be permissive.",
        ]
    lines = ["| File | Named by |", "| --- | --- |"]
    for value, bands in sorted(named.items()):
        lines.append("| `{}` | {} |".format(value, ", ".join(sorted(bands))))
    return lines


def render(root: Path = ROOT, lookup=None) -> str:
    """The whole THIRD_PARTY.md as one string, deterministic for its inputs."""
    requirements = tuple(root / path.name for path in REQUIREMENTS)
    pins = pinned_requirements(requirements)
    dependencies = resolve(pins, lookup)
    fonts = font_rows(root / FONTS.relative_to(ROOT))
    lines = [
        HEADER,
        "",
        "# Third-party notices",
        "",
        "Tuckcard's own code, skills, docs, findings, rules, examples and layout "
        "prototypes are MIT; see `LICENSE`. This file lists everything else that "
        "ships or is installed for the tools, and the license each one carries.",
        "",
        "## Fonts",
        "",
        "All nine shipped font families are under the SIL Open Font License 1.1, "
        "and each folder carries its own `OFL.txt`.",
        "",
        "| Family | Font files | License | License file |",
        "| --- | ---: | --- | --- |",
    ]
    for row in fonts:
        lines.append("| {} | {} | {} | `{}` |".format(
            row.family, row.files, row.license, row.license_file))
    lines += [
        "",
        "## Python dependencies",
        "",
        "Each version below is the pin in the named requirements file. Each "
        "license was read from the installed distribution and checked against "
        "the allowed list; the check fails on a copyleft or unknown license.",
        "",
        "| Package | Version | License | Pinned in |",
        "| --- | --- | --- | --- |",
    ]
    for row in dependencies:
        lines.append("| {} | {} | {} | `{}` |".format(
            row.name, row.version, row.license, row.source))
    lines += [
        "",
        "## Node dependencies",
        "",
        "None. The repository has no `package.json`.",
        "",
        "## Word-familiarity list",
        "",
    ]
    lines += familiarity_entries(root / KNOWLEDGE.relative_to(ROOT))
    lines += [
        "",
        "## Allowed licenses",
        "",
        "An unfamiliar license is not treated as a pass. Each of these was added "
        "deliberately:",
        "",
    ]
    for license_id in sorted(ALLOWED):
        lines.append("- `{}`: {}".format(license_id, ALLOWED[license_id]))
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate THIRD_PARTY.md, or check that it is current.")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 when THIRD_PARTY.md would change")
    parser.add_argument("--out", default=str(OUT), help="output path")
    args = parser.parse_args(argv)
    out = Path(args.out)
    try:
        text = render()
    except ThirdPartyError as error:
        print("third_party: {}".format(error), file=sys.stderr)
        return 1
    if args.check:
        try:
            current = out.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != text:
            print("third_party: {} is stale; run python tools/third_party.py".format(
                out), file=sys.stderr)
            return 1
        print("third_party: {} is current".format(out))
        return 0
    out.write_text(text, encoding="utf-8")
    print("third_party: wrote {}".format(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

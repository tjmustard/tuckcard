#!/usr/bin/env python3
"""Build a Tuckcard bundle: the section 6 tree, a manifest, one zip.

Usage:
    python bundle.py <deck.yaml> --out PATH [--overlay DIR ...]
        [--platform claude.ai|claude-code] [--created ISO8601]
        [--renders DIR]

The source is a deck file plus zero or more overlay folders laid out like
``local/`` in Claude Code: ``knowledge/findings``, ``knowledge/rules``,
``knowledge/gaps``, ``themes`` and ``presets``. Only overlay knowledge goes
into the bundle; shipped knowledge belongs to the plugin, not the deck.

The bundle is a plain zip with ``manifest.json`` at its root and the files
listed in the manifest hashed by sha256. Entry order and timestamps are
fixed, so the same inputs and the same ``--created`` value give the same
bytes. Re-bundling an unzipped copy gives the same manifest fields.

Every copied file must resolve inside the deck's folder or an overlay
folder, and nothing outside the bundle tree is written.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import knowledge_files as files
import validate

DECK_DIR = "deck"
OVERLAY_LAYOUT = (
    ("knowledge/findings", "*.md", ("_TEMPLATE.md",)),
    ("knowledge/rules", "**/*.yaml", ("_TEMPLATE.yaml",)),
    ("knowledge/gaps", "*.md", ("_TEMPLATE.md",)),
    ("themes", "*.json", ()),
    ("presets", "*.json", ()),
)
COUNT_KEYS = {
    "knowledge/findings": "findings",
    "knowledge/rules": "rules",
    "knowledge/gaps": "gaps",
    "themes": "themes",
    "presets": "presets",
}
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class BundleError(Exception):
    """A refusal that belongs on one line."""


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_created(value: Optional[str]) -> str:
    if value is None:
        return utc_now()
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BundleError("--created is not an ISO 8601 date-time: {!r}".format(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc).replace(
        microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_copy(source: Path, destination: Path, roots: Sequence[Path]) -> None:
    """Copy only a file that resolves inside one of the allowed roots."""
    resolved = source.resolve()
    if not any(resolved == root.resolve() or root.resolve() in resolved.parents
               for root in roots):
        raise BundleError("{} is outside the deck and overlay folders".format(source))
    if not resolved.is_file():
        raise BundleError("{} is not a file".format(source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(resolved.read_bytes())


def overlay_files(overlay: Path) -> List[Tuple[str, Path]]:
    """Bundle-relative path and source for each overlay file, sorted."""
    found: List[Tuple[str, Path]] = []
    for folder, pattern, ignored in OVERLAY_LAYOUT:
        root = overlay / folder
        if not root.is_dir():
            continue
        for source in sorted(root.glob(pattern)):
            if not source.is_file() or source.name in ignored or source.name.startswith("."):
                continue
            relative = source.relative_to(overlay).as_posix()
            found.append((relative, source))
    found.sort(key=lambda item: item[0])
    return found


def build_tree(deck_path: Path, overlays: Sequence[Path], renders: Optional[Path],
               staging: Path) -> Tuple[Dict[str, Any], List[Dict[str, str]], Dict[str, int]]:
    """Copy the files into ``staging`` and return deck, file list and counts."""
    try:
        deck = files.load_yaml(deck_path)
    except Exception as error:  # noqa: BLE001 - one line
        raise BundleError("{}: could not read deck: {}".format(deck_path, error))
    if not isinstance(deck, dict):
        raise BundleError("{}: deck is not a mapping".format(deck_path))

    roots: List[Path] = [deck_path.parent] + [overlay for overlay in overlays]
    written: Dict[str, Path] = {}

    def place(relative: str, source: Path) -> None:
        if relative in written:
            raise BundleError("{} comes from both {} and {}".format(
                relative, written[relative], source))
        written[relative] = source
        safe_copy(source, staging / relative, roots)

    place(DECK_DIR + "/deck.yaml", deck_path)

    snapshot = deck.get("rules_snapshot")
    filename = snapshot.get("file") if isinstance(snapshot, dict) else None
    if not isinstance(filename, str) or not filename:
        raise BundleError("deck.rules_snapshot.file is missing")
    rules_path = deck_path.parent / filename
    if not rules_path.is_file():
        raise BundleError("rules snapshot {} is missing".format(rules_path))
    place(DECK_DIR + "/" + filename, rules_path)

    review = deck_path.parent / "review.md"
    if review.is_file():
        place(DECK_DIR + "/review.md", review)

    counts = {key: 0 for key in COUNT_KEYS.values()}
    for overlay in overlays:
        for relative, source in overlay_files(overlay):
            place(relative, source)
            folder = relative.rsplit("/", 1)[0]
            if folder in COUNT_KEYS:
                counts[COUNT_KEYS[folder]] += 1

    if renders is not None:
        if not renders.is_dir():
            raise BundleError("--renders {} is not a folder".format(renders))
        roots = roots + [renders]
        for source in sorted(renders.rglob("*")):
            if not source.is_file() or source.name.startswith("."):
                continue
            place("renders/" + source.relative_to(renders).as_posix(), source)

    manifest_files: List[Dict[str, str]] = []
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            relative = path.relative_to(staging).as_posix()
            manifest_files.append(
                {"path": relative, "sha256": files.sha256_bytes(path.read_bytes())}
            )
    return deck, manifest_files, counts


def manifest_for(deck: Dict[str, Any], manifest_files: List[Dict[str, str]],
                 counts: Dict[str, int], created: str, platform: str) -> Dict[str, Any]:
    details = deck.get("personal_details")
    return {
        "schema_version": 1,
        "plugin_version": deck.get("plugin_version"),
        "created": created,
        "platform": platform,
        "deck_id": deck.get("id"),
        "deck_status": deck.get("status"),
        "contains_personal_details": bool(details),
        "overlay": {
            "findings": counts["findings"],
            "rules": counts["rules"],
            "gaps": counts["gaps"],
            "themes": counts["themes"],
            "presets": counts["presets"],
        },
        "files": manifest_files,
    }


def write_zip(staging: Path, out_path: Path) -> None:
    entries = sorted(path for path in staging.rglob("*") if path.is_file())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out_path), "w", zipfile.ZIP_DEFLATED) as archive:
        for path in entries:
            relative = path.relative_to(staging).as_posix()
            info = zipfile.ZipInfo(relative, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def bundle(deck_path: Path, out: Path, overlays: Sequence[Path],
           platform: str, created: str, renders: Optional[Path]) -> Tuple[Path, Dict[str, Any]]:
    problems = validate.validate_file(deck_path)
    if problems:
        raise BundleError("deck failed validation:\n" + "\n".join(problems))
    with tempfile.TemporaryDirectory(prefix="tuckcard-bundle-") as folder:
        staging = Path(folder)
        deck, manifest_files, counts = build_tree(deck_path, overlays, renders, staging)
        manifest = manifest_for(deck, manifest_files, counts, created, platform)
        problems = validate.schema_errors(manifest, "bundle_manifest")
        if problems:
            raise BundleError("manifest failed validation:\n" + "\n".join(problems))
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if out.suffix != ".zip" or out.is_dir():
            out = out / "{}.tuckcard.zip".format(deck.get("id"))
        write_zip(staging, out)
    return out, manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a .tuckcard.zip bundle from a deck and its overlays."
    )
    parser.add_argument("deck", help="path to deck.yaml")
    parser.add_argument("--out", required=True,
                        help="zip path, or a folder to write <deck-id>.tuckcard.zip into")
    parser.add_argument("--overlay", action="append", default=[],
                        help="overlay folder laid out like local/; repeatable")
    parser.add_argument("--platform", choices=("claude.ai", "claude-code"),
                        default="claude.ai")
    parser.add_argument("--created", help="ISO 8601 date-time for the manifest")
    parser.add_argument("--renders", help="folder of renders to include")
    args = parser.parse_args(argv)

    try:
        created = parse_created(args.created)
        path, manifest = bundle(
            Path(args.deck), Path(args.out), [Path(item) for item in args.overlay],
            args.platform, created, Path(args.renders) if args.renders else None,
        )
    except BundleError as error:
        print("bundle: {}".format(error), file=sys.stderr)
        return 1
    print("{}: {} files, {} bytes".format(
        path, len(manifest["files"]), path.stat().st_size))
    print("deck {} ({}), overlay findings {} rules {} gaps {} themes {} presets {}".format(
        manifest["deck_id"], manifest["deck_status"],
        manifest["overlay"]["findings"], manifest["overlay"]["rules"],
        manifest["overlay"]["gaps"], manifest["overlay"]["themes"],
        manifest["overlay"]["presets"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

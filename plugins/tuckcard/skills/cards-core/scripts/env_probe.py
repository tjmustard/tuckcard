#!/usr/bin/env python3
"""Report what this machine can do, for a skill to act on.

Usage:
    python env_probe.py [--dir PATH] [--timeout SECONDS] [--offline]
        [--no-chromium] [--text]

Prints JSON by default so a skill can read it: whether files can be written
in the given folder, whether the Crossref and PubMed APIs answer, and whether
a Chromium browser launches. Each fact carries ``ok`` (true, false, or null
when skipped) and a one-line ``detail``.

A failed probe is a fact, not an error: the report is still printed and the
exit status stays 0. The script is also the one place a skill asks "which
platform am I on", so it never assumes a network or a browser.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

CROSSREF_URL = "https://api.crossref.org/works?rows=0"
PUBMED_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=pubmed&retmode=json"
TIMEOUT_DEFAULT = 5.0


def probe_writable(directory: Path) -> Dict[str, Any]:
    """Write and remove a small file, the same permission a render needs."""
    existed = directory.is_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return {"ok": False, "path": str(directory),
                "detail": "cannot create folder: {}".format(error)}
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w", prefix=".env_probe-", dir=str(directory), delete=False
        )
        name = Path(handle.name)
        try:
            handle.write("tuckcard")
        finally:
            handle.close()
        name.unlink()
    except OSError as error:
        return {"ok": False, "path": str(directory),
                "detail": "cannot write: {}".format(error)}
    if existed:
        detail = "wrote and removed a small file"
    else:
        detail = "created {} and wrote a small file".format(directory)
    return {"ok": True, "path": str(directory), "detail": detail}


def probe_url(url: str, timeout: float) -> Dict[str, Any]:
    """Ask a public API for bytes. Any answer from the server counts."""
    request = urllib.request.Request(url, headers={"User-Agent": "tuckcard-env-probe"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1024)
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as error:
        return {"ok": False, "url": url, "detail": "HTTP {}".format(error.code)}
    except Exception as error:  # noqa: BLE001 - the reason belongs on one line
        return {"ok": False, "url": url, "detail": "{}: {}".format(
            type(error).__name__, error)}
    return {"ok": True, "url": url, "detail": "HTTP {}".format(status)}


def probe_chromium() -> Dict[str, Any]:
    """Launch and close a browser. A missing package or browser is a fact."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "detail": "playwright is not installed ({})".format(
            type(error).__name__)}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                version = browser.version
            finally:
                browser.close()
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "detail": "chromium did not launch: {}: {}".format(
            type(error).__name__, error)}
    return {"ok": True, "detail": "chromium {}".format(version)}


def report(directory: Path, timeout: float, offline: bool,
           chromium: bool) -> Dict[str, Any]:
    facts: Dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.system().lower(),
        "writable": probe_writable(directory),
    }
    if offline:
        skipped = {"ok": None, "detail": "skipped by --offline"}
        facts["crossref"] = dict(skipped)
        facts["pubmed"] = dict(skipped)
    else:
        facts["crossref"] = probe_url(CROSSREF_URL, timeout)
        facts["pubmed"] = probe_url(PUBMED_URL, timeout)
    if chromium:
        facts["chromium"] = probe_chromium()
    else:
        facts["chromium"] = {"ok": None, "detail": "skipped by --no-chromium"}
    facts["ok"] = all(value["ok"] is not False for value in facts.values()
                      if isinstance(value, dict))
    return facts


def text_lines(facts: Dict[str, Any]) -> str:
    lines = ["python {} on {}".format(facts["python"], facts["platform"])]
    for name in ("writable", "crossref", "pubmed", "chromium"):
        value = facts[name]
        state = "ok" if value["ok"] is True else (
            "skipped" if value["ok"] is None else "failed")
        lines.append("{:<9} {:<7} {}".format(name, state, value["detail"]))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report writability, API reachability and browser launch."
    )
    parser.add_argument("--dir", default=".", help="folder to test for writing")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_DEFAULT)
    parser.add_argument("--offline", action="store_true",
                        help="skip the Crossref and PubMed checks")
    parser.add_argument("--no-chromium", action="store_true",
                        help="skip the browser check")
    parser.add_argument("--text", action="store_true",
                        help="print one line per fact instead of JSON")
    args = parser.parse_args(argv)

    facts = report(Path(args.dir), args.timeout, args.offline, not args.no_chromium)
    if args.text:
        print(text_lines(facts))
    else:
        print(json.dumps(facts, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Tuckcard platform probe (P2). Standard library only.

Answers the questions in SPEC.md Appendix C and writes probe-report.md to the working directory.
"""
import datetime
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import warnings

warnings.simplefilter("ignore")  # keep the report clean of library deprecation notices

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SKILLS_ROOT = os.path.dirname(SKILL_DIR)
rows = []  # (question, result, settles)


def add(question, result, settles=""):
    rows.append((question, str(result), settles))


def run(cmd, timeout=90):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()[-400:]
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def fetch(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tuckcard-probe/0.0.1 (mailto:none)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(2000)
            return f"reachable (HTTP {r.status}, {len(body)} bytes read)"
    except Exception as e:  # noqa: BLE001
        return f"not reachable ({type(e).__name__}: {str(e)[:120]})"


# 1. Python and mount points
add("Python version", platform.python_version(), "")
add("OS", f"{platform.system()} {platform.release()} ({platform.machine()})", "")
add("Where this skill is mounted", SKILL_DIR, "Path resolution in scripts")
add("Skills root (parent folder)", SKILLS_ROOT, "Path resolution in scripts")
add("Working directory", os.getcwd(), "Where outputs go")
try:
    listing = sorted(os.listdir(SKILLS_ROOT))[:20]
except Exception as e:  # noqa: BLE001
    listing = f"cannot list ({type(e).__name__})"
add("Folders next to this skill", listing, "Assumption H")

# 2. Sibling-skill file access
marker = os.path.join(SKILLS_ROOT, "tuckcard-probe-sibling", "marker.txt")
try:
    with open(marker) as f:
        add("A skill can read a sibling skill's files?", "yes: " + f.read().strip()[:60], "Assumption H")
except Exception as e:  # noqa: BLE001
    add("A skill can read a sibling skill's files?", f"no ({type(e).__name__}: {e})", "Assumption H")

# 3. Write access
def can_write(folder):
    try:
        path = os.path.join(folder, ".tuckcard-probe-write-test")
        with open(path, "w") as f:
            f.write("x")
        os.remove(path)
        return "yes"
    except Exception as e:  # noqa: BLE001
        return f"no ({type(e).__name__})"

add("Skill folder writable?", can_write(SKILL_DIR), "Overlay model (expect no on claude.ai)")
add("Working directory writable?", can_write(os.getcwd()), "Outputs and bundles")

# 4. Preinstalled packages
for mod in ["PIL", "ruamel.yaml", "yaml", "jsonschema", "playwright"]:
    try:
        m = importlib.import_module(mod)
        add(f"Package {mod} importable?", f"yes ({getattr(m, '__version__', 'version unknown')})", "Script dependencies")
    except Exception as e:  # noqa: BLE001
        add(f"Package {mod} importable?", f"no ({type(e).__name__})", "Script dependencies")

# 5. pip install into a temporary folder (no system changes)
tmp = tempfile.mkdtemp(prefix="tuckcard-probe-")
code, out = run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                 "--target", tmp, "ruamel.yaml"], timeout=120)
add("pip install works? (ruamel.yaml into a temp folder)", "yes" if code == 0 else f"no (exit {code}: {out[-160:]})",
    "Script dependencies")
shutil.rmtree(tmp, ignore_errors=True)

# 6. Chromium
browsers = {b: shutil.which(b) for b in ["chromium", "chromium-browser", "google-chrome", "chrome", "headless_shell"]}
found = {k: v for k, v in browsers.items() if v}
add("Chromium-family binary on PATH?", found or "none found", "Rendering path on claude.ai")
launch = "not attempted (playwright not importable)"
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    try:
        with sync_playwright() as p:
            kwargs = {}
            if found:
                kwargs["executable_path"] = next(iter(found.values()))
            b = p.chromium.launch(**kwargs)
            pg = b.new_page()
            pg.set_content("<p>ok</p>")
            launch = "yes" if pg.inner_text("p") == "ok" else "launched but page failed"
            b.close()
    except Exception as e:  # noqa: BLE001
        launch = f"no ({type(e).__name__}: {str(e)[:140]})"
except Exception:  # noqa: BLE001
    pass
add("Chromium launches via Playwright?", launch, "Rendering path on claude.ai")

# 7. Network
add("Crossref reachable from code?",
    fetch("https://api.crossref.org/works/10.1111/j.1467-9280.2009.02370.x"), "Verification path")
add("PubMed (E-utilities) reachable from code?",
    fetch("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=19493324&retmode=json"),
    "Verification path")
add("PyPI reachable from code?", fetch("https://pypi.org/simple/ruamel-yaml/"), "Script dependencies")
add("Google Fonts reachable from code?", fetch("https://fonts.googleapis.com/css2?family=Caveat"), "Font embedding")

# 8. Frontmatter
add("Standard frontmatter accepted on upload?",
    "yes, if this skill uploaded and ran (it uses name, description and license)", "Assumption F")

# Report
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lines = [f"# Tuckcard platform probe report", "", f"Run: {stamp}", "",
         "| Question | Result | Settles |", "|---|---|---|"]
for q, r, s in rows:
    r = r.replace("|", "/").replace("\n", " ")
    lines.append(f"| {q} | {r} | {s} |")
lines += ["", "Copy the relevant rows into SPEC.md Appendix C with today's date.", "",
          "```json", json.dumps({q: r for q, r, _ in rows}, indent=1), "```"]
report = "\n".join(lines)
print(report)
try:
    with open(os.path.join(os.getcwd(), "probe-report.md"), "w") as f:
        f.write(report + "\n")
except Exception as e:  # noqa: BLE001
    print(f"\n(could not write probe-report.md: {e})")

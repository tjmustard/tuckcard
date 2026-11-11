"""Every YAML and Markdown template the seed kit ships must pass validation."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins/tuckcard/skills/cards-core"
VALIDATE = CORE / "scripts/validate.py"


def kit_files():
    files = sorted((CORE / "knowledge/rules").rglob("*.yaml"))
    files.append(CORE / "knowledge/findings/_TEMPLATE.md")
    files.append(CORE / "knowledge/gaps/_TEMPLATE.md")
    return files


def test_kit_files_all_pass():
    files = kit_files()
    assert len(files) == 26
    result = subprocess.run(
        [sys.executable, str(VALIDATE), *map(str, files)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    valid_lines = [line for line in result.stdout.splitlines() if ": valid (" in line]
    assert len(valid_lines) == len(files)

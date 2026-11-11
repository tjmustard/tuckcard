---
name: tuckcard-probe
description: Run the Tuckcard platform probe and report what this sandbox can do. Use only when the user asks to run the Tuckcard probe.
license: MIT
---

# Tuckcard platform probe

1. Run `python3 scripts/probe.py` from this skill's folder. It uses only the standard library and takes about a minute.
2. It prints a Markdown report and also writes `probe-report.md` to the current working directory. Give the user the report file to download.
3. Show the user the summary table from the report, unedited. Don't interpret results beyond what the report says.
4. Don't change anything outside the working directory and a temporary folder.

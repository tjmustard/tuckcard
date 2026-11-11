# Platform probe (P2)

A throwaway two-skill plugin that reports what a claude.ai skill sandbox can do, so the build doesn't rest on guesses. It answers the questions in `SPEC.md` Appendix C. Run it before bootstrap.

## Run it on claude.ai (paid plan)

1. Make sure code execution is on in your claude.ai settings.
2. Zip this folder so `.claude-plugin/` and `skills/` are at the top level of the zip:
   ```
   cd tools/probe-plugin && zip -r ../tuckcard-probe.zip .claude-plugin skills
   ```
3. In claude.ai, open Customize > Plugins and upload the zip as a custom plugin.
4. Start a new chat and say: "Run the Tuckcard probe."
5. Download `probe-report.md` and copy its rows into `SPEC.md` Appendix C with the date.
6. Run it once more in Claude Code (`python3 skills/tuckcard-probe/scripts/probe.py`) for comparison; the Claude Code results go in the same table, labeled.
7. Remove the probe plugin from claude.ai when you're done.

## What it checks

- Python version and where skills are mounted
- Whether one skill can read another skill's files (assumption H)
- Whether the skill folder and working directory are writable
- Whether Pillow, ruamel.yaml, PyYAML, jsonschema and Playwright are importable, and whether `pip install` works
- Whether a Chromium-family browser exists and launches
- Whether Crossref, PubMed, PyPI and Google Fonts are reachable from code
- Whether the standard frontmatter (`name`, `description`, `license`) was accepted (assumption F)

If the upload as a plugin fails, try uploading `skills/tuckcard-probe` alone as a skill ZIP under Customize > Skills; then the sibling test will report "no" by design, and record that the plugin upload failed.

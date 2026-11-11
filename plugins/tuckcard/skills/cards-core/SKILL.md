---
name: cards-core
description: Shared knowledge, schemas, templates and scripts for the Tuckcard skills. Not for direct use; other Tuckcard skills load files from it.
---

# cards-core

This skill is a library. Don't run it on its own. If a user invokes it directly, tell them to start with `cards-new` (or attach a Tuckcard bundle) and stop.

## What's here

| Path | What it holds |
|---|---|
| `ROUNDS.md` | The approval protocol and crisis stop used by every skill that runs rounds |
| `knowledge/RESEARCH-GUIDE.md` | How to research a scope |
| `knowledge/findings/` | Shipped findings; `index.yaml` is generated, read it first |
| `knowledge/quarantine/` | Findings that failed verification, with reasons |
| `knowledge/gaps/` | Questions with no usable evidence yet |
| `knowledge/rules/` | `core.yaml`, `policies.yaml`, `safety/`, `age/`, `context/` |
| `knowledge/sources-allowlist.yaml` | Domains accepted for guidance documents without a DOI |
| `schemas/` | JSON Schemas for every file type |
| `templates/` | `stacked/`, `notebook/`, `index/`: card HTML, CSS and `layout.json` |
| `marks.json`, `themes/`, `presets/`, `fonts/` | Rendering assets |
| `scripts/` | `env_probe`, `validate`, `verify_citations`, `index`, `validate_rules`, `compile_rules`, `lint`, `bundle`, `promote`, `migrate`, renderers |
| `examples/` | Four fictional example decks |

## How other skills use it

- Resolve this folder relative to the calling skill (`../cards-core/`). If that fails on the current platform, check `SPEC.md` Appendix C (platform facts) and the build notes; the fallback build copies `cards-core` into each skill.
- Run scripts with the files they need as arguments. Never write into this folder at runtime; write to the deck working directory or the overlay (`local/` in Claude Code, the bundle on claude.ai).
- Read `knowledge/findings/index.yaml` before opening individual findings, to keep context small.

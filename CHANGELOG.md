# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.0.0](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The hand-written seed kit at the repo root, copied without content changes: `SPEC.md`, `BOOTSTRAP.md`, `CLAUDE.md`, the seed `README.md`, `.gitignore`, the `local/` overlay folders, the seven skill drafts with `ROUNDS.md`, `RESEARCH-GUIDE.md`, the knowledge templates and rule stubs, `reference/layouts/` (14 files) and `tools/probe-plugin/` (6 files). The seed-kit commit adds 66 files.
- Marketplace and plugin manifests. `.claude-plugin/marketplace.json` declares marketplace `tuckcard` with one plugin sourced from `./plugins/tuckcard`. `plugins/tuckcard/.claude-plugin/plugin.json` declares `tuckcard` 0.1.0, MIT, author TJ Mustard. `claude plugin validate` reported Validation passed at exit 0 for both. In an isolated config, the marketplace added from the local repo and `claude plugin install tuckcard@tuckcard` succeeded.
- Nine SIL OFL 1.1 font families under `plugins/tuckcard/skills/cards-core/fonts/`: 31 files, of which 22 are font files and 9 are `OFL.txt`. Every license file names the SIL Open Font License 1.1.

  | Family | Font files | Primary file sha256 |
  | --- | ---: | --- |
  | archivo-black | 1 | `dd9a89a019b4849f66ab75455fe7bdf931311042cbb0f0f97acc061539703180` |
  | atkinson-hyperlegible | 4 | `7fb917c89019896d0b52ee84b7cbb3304c18cb90b19a62f5e32712bd23e97669` (Regular) |
  | caveat | 1 | `0bdb6b660482d31531b3945849fba5916b3ef8695da7024a9e6b9ee3c4157988` |
  | fraunces | 2 | `177ff6c0f14e5550a3c624247cd1189611d4eb65d000b14944c63d967958abbb` |
  | liberation-sans | 4 | `76d04c18ea243f426b7de1f3ad208e927008f961dc5945e5aad352d0dfde8ee8` (Regular) |
  | liberation-serif | 4 | `058ea80864aef09a23f45cbec2bb5400bc3dfbdea01c3f10538a21fcb497fb74` (Regular) |
  | literata | 2 | `b41138c9373112f32abb589cc22e8674b06ed4048b0c513be922bdd26f274440` |
  | shantell-sans | 2 | `d98a7913853f78d71aa0b86daf66b5eddb5a3266c07bfd51ef70632b88c41084` |
  | source-serif-4 | 2 | `97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b` |

  Sources: Google Fonts at commit `5bb28733cec313b63fbd415b574b5ae35c8aa8b8` for seven families, and liberation-fonts 2.1.5 for Liberation Serif and Liberation Sans. `DECISIONS.md` D-003 records the exact URLs.
- `.github/workflows/ci.yml`: parses both manifests as JSON, checks nine font families each have a font file and `OFL.txt`, and fails on a committed `deck.yaml` outside `examples/`, a `*.tuckcard.zip`, or a file under `renders/` or `out/`. The three checks pass locally.
- `.github/workflows/weekly-recheck.yml`: scheduled weekly and on demand. It reports that no shipped findings exist yet and that no check ran, and it exits 1 rather than claim a pass if findings appear before the check script exists.
- `CHANGELOG.md` and `DECISIONS.md` at the repo root, on the person's instruction of 2026-11-11 02:57Z.

### Changed

- `LICENSE` copyright line restored to the seed kit's "Copyright (c) 2026 TJ Mustard", pending the person's word on which name is canonical. The manifests use the same name. `DECISIONS.md` D-005 records it and supersedes D-002.

### Fixed

- `.github/workflows/ci.yml` now matches `renders/` and `out/` at any depth, not only at the repo root, so a force-committed `local/renders/page1.png` or `local/out/x.pdf` fails. Proved by force-adding both files: the step printed both paths and exited 1; after `git rm --cached` it exited 0.
- `CHANGELOG.md` now says the seed-kit commit adds 66 files, the measured count; the tree holds 67 because `LICENSE` predates that commit. `DECISIONS.md` D-003 now describes the liberation-fonts 2.1.5 release accurately: no Assets entries, with binaries attached as file links in the release notes. The decision, URL and files are unchanged. The M0 review raised both wording nits.

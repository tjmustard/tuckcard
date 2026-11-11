# Decisions

A numbered, append-only register of conscious deviations from `SPEC.md` or from the seed kit, with the reason for each. Entries are never renumbered, rewritten or removed. A later entry can supersede an earlier one, and the later entry says so. If a milestone makes no deviation, its section says so. No entry is invented.

## M0: skeleton

### D-001: Add `CHANGELOG.md` and `DECISIONS.md` to the repo root

**Deviation.** The directory tree in SPEC.md section 2 names neither file.

**Decision.** Both files start at M0, on the person's instruction of 2026-11-11 02:57Z (operator row `qitem-20261111025652-10637eacb5991aa7`).

**Why.** The person asked for a changelog that records what changed with evidence, and for a register that records conscious deviations and why. Keeping both at the repo root makes them visible to contributors.

### D-002: Keep the committed LICENSE copyright name over the seed kit's copy

**Deviation.** The committed `LICENSE` says "Thomas Mustard". The seed kit's copy says "TJ Mustard".

**Decision.** The committed file stays unchanged. The manifests use Thomas Mustard as author and marketplace owner, and the brief's "author per the repo" is read as that same name.

**Why.** The committed file is the repository's existing legal record, and the M0 brief directs keeping it. Deciding which name is canonical belongs to the person, not to this milestone. The question is reported to the lead.

### D-003: Font sources and versions

**Deviation.** None from the source list in SPEC.md sections 8 and 10 and the BOOTSTRAP M0 note, which name Google Fonts and liberationfonts/liberation-fonts. Two choices within that list are recorded here because they affect reproducibility.

**Decision.** The seven Google Fonts families are pinned to Google Fonts commit `5bb28733cec313b63fbd415b574b5ae35c8aa8b8`, downloaded from `https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/<family>/`. Liberation Serif and Liberation Sans come from liberation-fonts 2.1.5, from the binary tarball linked in that release's notes: `https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz`. Variable font files ship where the family publishes one: Source Serif 4, Shantell Sans, Fraunces, Literata and Caveat. Static files ship for Archivo Black, Atkinson Hyperlegible (Regular, Bold, Italic, BoldItalic) and Liberation (Regular, Bold, Italic, BoldItalic).

**Why.** A pinned commit makes the downloaded bytes reproducible and auditable. The liberation-fonts repository tree holds only `.sfd` sources, and its GitHub releases carry no uploaded assets, so the project's published binary tarball is the original project's own build. Shipping the files each family actually publishes avoids generating missing styles ourselves.

### D-004: `weekly-recheck.yml` reports that it has nothing to check until M5

**Deviation.** SPEC.md section 3, invariant 1 says CI runs the citation existence and retraction check on every push and weekly. That check script (`verify_citations.py`) starts at M2, and shipped findings start at M5, so the weekly check cannot run at M0.

**Decision.** The scheduled workflow is created now. While no `F-*.md` files exist, it prints that there is nothing to re-check and that no check ran, then exits 0. If findings exist before the script does, it exits 1 rather than report a pass.

**Why.** The schedule should exist before findings arrive, and a placeholder that claims a pass would be a false signal. Exiting 1 on unexpected findings keeps the gap visible.

### D-005: Restore the seed kit's LICENSE copyright line

**Supersedes.** D-002.

**Deviation.** D-002 kept the committed "Thomas Mustard" copyright line. The lead, from the operator, directs restoring the seed kit's line instead.

**Decision.** `LICENSE` now reads "Copyright (c) 2026 TJ Mustard", the seed kit's line. The marketplace owner and the plugin author use the same name. The canonical name stays open for the person to set.

**Why.** The seed kit's line is the project's own record of authorship. The earlier committed line was not this milestone's to harmonize, and an agent should not settle a name the person has not. The line is restored pending the person's word.

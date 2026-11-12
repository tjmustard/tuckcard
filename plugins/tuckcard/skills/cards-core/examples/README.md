# Example decks

Built in M6 (grade school, middle school, college) and M7 (high school), per SPEC.md Sections 9 and 10. Each example:
- is fully de-specified and fictional (`example: true` in its deck file)
- has a README listing the lint fixes applied when it was brought up to the v1 rules
- is a style reference for `cards-draft`, which never reuses an example line verbatim

No mapping from real details to fictional ones is stored anywhere in the repository. Terms from the maintainer's private list are never committed.

## Checking an example

Each example's README has the two commands that compile its rules and lint it. Run them from the example's folder.

## Scanning for private terms

The scan reads a term list that stays outside the repository. It never bundles the list and no workflow names a path to it:

```
python tools/pii_scan.py --terms <path outside the repo>
```

Run from the repo root. With no path argument the scan walks this examples folder; pass a folder or files to scan something else. A folder is searched recursively. Term matching is case-insensitive on whole words, so a multi-word term matches as a phrase. The scan exits 0 when clean, 1 when it finds a term, and 2 when the term list or a target cannot be read. Each hit prints the file, the line number and the term, without repeating the line.

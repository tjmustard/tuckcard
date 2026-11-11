# Layout prototypes

Original Tuckcard designs (MIT), made during planning on 2026-11-10. They are the visual source for the three production layouts built in M3. They are prototypes, not production code: one hard-coded sample card, inline styles, no auto-fit.

| Layout | Files | One-line description |
|---|---|---|
| `stacked` (default) | `stacked-light.*`, `stacked-dark.*` | Heavy sans title, big watermark number, left-aligned serif lines, each note tucked under its line with ↳, hand-drawn swash marks |
| `notebook` | `notebook-light.*`, `notebook-dark.*` | Margin rule, serif title with a highlighted key word, highlighter marks with numbered badges, handwritten notes in one right-hand column |
| `index` | `index-light.*`, `index-dark.*` | Colored header band with the title, plain statement with underlined marks and numbered badges, numbered "Try this" list at the bottom |

All three use the casual style preset. The professional preset (Liberation Serif and Sans, crisp marks, square corners) and the `mono` theme are built in M3.

## Files

- `*.html`: standalone pages. Fonts load from Google Fonts, so view them online. The card is 480 × 480 CSS px, which is 5 × 5 in at 96 px/in.
- `*.png`: the same cards rendered at 2× with the same fonts, for viewing offline.
- `generate.py`: writes the HTML from one card's data and, where Playwright and Chromium are installed, renders the PNGs. It shows the structure each layout needs from the card data (title, lines, mark target, note).

## Fonts used

All SIL OFL 1.1: Archivo Black, Source Serif 4, Shantell Sans (`stacked`); Fraunces, Literata, Caveat (`notebook`); Atkinson Hyperlegible (`index`, and the small labels in all three).

## Known issues for M3 to fix

1. **Vertical balance.** All three leave empty space at the bottom with this card's amount of text. Production layouts should distribute or center the body within the card's regions.
2. **`stacked` swash placement.** The swash under a marked word can collide with the note line directly beneath it. Leave clearance between the mark and the note.
3. **`notebook` row alignment.** Notes are aligned to grid rows, so a two-line note can drift from its line. Align each note to the baseline of the line it belongs to.
4. **`notebook` capacity.** The notes column narrows the text. Set `layout.json` widths and font floors so typical five-line cards fit.
5. **`index` capacity.** The "Try this" list holds about four short notes. Longer notes need the shrink steps and floors in `layout.json`.
6. **Contrast and grayscale.** The dark-theme highlighter and the light-theme tint need the WCAG and grayscale checks from SPEC Section 5 (`cards-restyle`).

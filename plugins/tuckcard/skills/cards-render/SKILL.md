---
name: cards-render
description: Render an approved Tuckcard deck to a print sheet, PDF, lock screens and single-card PNGs, with a fit report. Use when the user wants files to print or use as wallpapers.
---

# cards-render

Prerequisite: deck `status` is `reviewed` or `rendered`. If it isn't, say which skill to run first. Rendering never blocks on hand edits; it flags them.

## 1. Choose the path

Run `python ../cards-core/scripts/env_probe.py`.
- **Chromium launches (Claude Code):** `render_playwright.py` for the vector print PDF, lock screens and PNGs, plus `build_print_sheet.py` for the HTML sheet.
- **No Chromium (claude.ai):** `build_print_sheet.py` for the HTML sheet, and `render_pillow.py` for lock screens, PNGs and a 300 dpi raster PDF.

Ask for the year if the deck is weekly and the user hasn't said (default: the upcoming year). It only affects the week-of dates on the index pages.

## 2. Pre-flight

- Compare each card's content to its hashes. Cards matching neither `approved_hash` nor `linted_hash` were edited by hand: record `approved_by: hand-edit`, render them, and list them.
- Leave `visibility: private` cards out of fridge-facing and lock-screen outputs.
- Resolve the style: deck `style.layout`, `style.preset`, theme per output (print: `color` and `mono`; lock screens: `dark`; single PNGs: `color`) unless the deck overrides, plus any token overrides.

## 3. Render and check

1. Render every requested output.
2. Read the fit report. Any card that failed to fit even at the font floors goes back to `cards-draft`; don't deliver around it silently.
3. Build a contact sheet of every print page and a sample of lock screens, and look at it. Check for clipped text, overlapping notes, marks off their targets, and the lock-screen safe band.

## 4. Deliver

- Files: print sheet (HTML), PDF (color and B&W), lock-screen zips per format, single PNGs, named `<deck-id>-<format>-<n>.png`.
- Tell the user, in a line each:
  - print at 100% / Actual size so cards come out at 5 inches
  - on claude.ai, the PDF is a raster; printing the HTML sheet from a browser gives the crispest result
  - any cards shrunk, failed, edited by hand, or left out for visibility
- Set `status: rendered`. On claude.ai, emit the updated bundle and remind the user to keep it private.

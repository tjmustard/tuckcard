---
name: cards-restyle
description: Change a Tuckcard deck's layout, style preset, theme, colors, fonts or spacing, previewing one card before re-rendering. Use for a different look, a black-and-white or dark version, or a more professional style.
---

# cards-restyle

Prerequisite: a deck with approved cards. Restyling never changes card content, so approvals stay valid. Follow `../cards-core/ROUNDS.md` for the preview round.

## 1. What to change

Ask what the user wants, in their words, and map it to:
- **Layout:** `stacked`, `notebook`, `index`.
- **Style preset:** `casual` or `professional` (fonts, corners, crisp vs. hand-drawn marks).
- **Theme:** `color`, `mono`, `dark`, or a custom theme.
- **Category colors.**
- **Fonts:** from the shipped set, or one the user supplies. Ask about its license first; it must allow embedding (OFL or similar). On claude.ai the font file must be attached to the conversation.
- **Layout tokens:** corner radius, spacing, mark stroke weight, mark wobble (`0` = clean geometric marks).

## 2. Checks before previewing

- Contrast: text against background meets WCAG ratios for normal and large text.
- Grayscale: category colors stay distinguishable when converted to grayscale, so a B&W print doesn't turn every accent into the same gray. If they don't, say so and suggest the `mono` theme for print.
- **Layout switch:** rerun the fit check for the whole deck in the new layout. List cards that no longer fit; they go back to `cards-draft` before rendering.

## 3. Preview

Render one representative card (the longest card in the deck, by default) in each affected layout, preset and theme combination. Show it and get approval.

## 4. Save and hand off

- Write the style into the deck's `style` block (`layout`, `preset`, `theme`, `tokens`). A reusable custom theme or preset goes to the overlay: `local/themes/` or `local/presets/` in Claude Code, the bundle on claude.ai.
- Validate with `python ../cards-core/scripts/validate.py`.
- Hand off to `cards-render`. On claude.ai, emit the bundle.

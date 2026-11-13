# Tuckcard docs

Two guides, for two different jobs.

## Extending the plugin

One page per extension recipe in `SPEC.md` section 8. Each says where the file goes at the level that fits it (deck, overlay or fork), how to check it and how to see the result.

| Page | What it covers |
| --- | --- |
| [Add a theme](extending/new-theme.md) | Colours. One JSON file, usable from `local/themes/` or the bundle. |
| [Add a preset](extending/new-preset.md) | Type and shape. Fonts, mark wobble, corners, spacing. |
| [Add a context](extending/new-context.md) | A domain's rules: athletics, academics, a new one. Overlay or fork. |
| [Add an age band](extending/new-age-band.md) | Reading and format limits, and the policy ladder's omit floor. |
| [Add a category](extending/new-category.md) | A deck's own grouping, its colour and the contexts it maps to. |
| [Add a mark style](extending/new-mark-style.md) | A shape drawn under a marked word. Fork-level. |
| [Add a layout](extending/new-layout.md) | Card geometry and the planners in both engines. Fork-level. |

The theme and preset pages are the two that need no code and no fork: a user can add one inside their own overlay, in Claude Code or on claude.ai.

## Editing by hand

[Edit a deck by hand](editing-by-hand.md) says what is safe to edit, which files are generated, what to run after an edit, and what happens to a card's approval when its words change.

## Elsewhere

- `SPEC.md` is the design, and the source of truth when a guide and the code disagree.
- `DECISIONS.md` records every deviation from the spec and why.
- `CHANGELOG.md` records what changed, with evidence.
- [`RESEARCH-GUIDE.md`](../plugins/tuckcard/skills/cards-core/knowledge/RESEARCH-GUIDE.md) is the only description of how research is done.

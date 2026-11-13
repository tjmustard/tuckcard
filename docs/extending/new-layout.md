# Add a layout

A layout sets structure: where the title, the lines and the notes sit on the card, at what sizes, and how far they may shrink. The three shipped layouts are `stacked`, `notebook` and `index`.

A new layout is a fork-level change. It is more work than a theme or preset because both engines must agree on it, and a layout is not supported until the parity check passes for it.

## What a layout is made of

| Piece | Where | What it does |
| --- | --- | --- |
| Geometry | `templates/<name>/layout.json` | Card size, the header, title and body regions in inches, font sizes, shrink steps, font floors, line heights, gaps, the default mark style. |
| Page | `templates/<name>/card.html` | The single-card page Playwright loads. |
| Styles | `templates/<name>/card.css` | The browser-side styles for the layout. |
| Planners | `render_core.py`, `templates/shared/card.js` | One planning function per engine, which turns a card and a style into positioned rows, marks and a measured fit. |

The JSON file is checked against `schemas/layout.schema.json`, so copy one:

```sh
mkdir plugins/tuckcard/skills/cards-core/templates/banner
cp plugins/tuckcard/skills/cards-core/templates/stacked/layout.json \
  plugins/tuckcard/skills/cards-core/templates/banner/layout.json
cp plugins/tuckcard/skills/cards-core/templates/stacked/card.html \
  plugins/tuckcard/skills/cards-core/templates/banner/card.html
cp plugins/tuckcard/skills/cards-core/templates/stacked/card.css \
  plugins/tuckcard/skills/cards-core/templates/banner/card.css
```

Then edit `layout.json`: the regions in inches, the font sizes, the shrink steps from the largest size down, the floors below which a card does not shrink, and the line heights and gaps. `card.html` loads the folder's own `card.css` and the shared engine, and the page is the same for every layout, so a new layout usually changes nothing there.

## The Python planner

`render_core.plan_card` chooses a planner by name:

```python
builder = {"stacked": _plan_stacked, "notebook": _plan_notebook, "index": _plan_index}[layout]
```

Add `_plan_banner` and add it to that mapping. The planner returns the same plan shape as the others: a list of text rows with their positions and widths, the marks, and the measured height, which is what the fit report reads. The Pillow renderer draws any plan, so once the planner is right both renderers can draw it.

## The JavaScript planner

`templates/shared/card.js` has one planning function per layout, and `planCard` calls it. Add the same geometry there. The two planners must produce the same plan for the same card, because the parity check compares them run for run, line break for line break.

Do not measure with a different method on each side. Both engines measure text with the same rules: the same font files, the same sizes, the same tracking and reserve. Copy the existing planner's measurement rather than writing new arithmetic.

## The deck schema

`schemas/deck.schema.json` lists the three shipped layouts in `style.layout`:

```json
"layout": {"enum": ["stacked", "notebook", "index"]}
```

Add your layout's name to that list, or `validate.py` will reject the deck. That enum is the one shipped restriction that a fork has to extend, and the note is recorded with `DECISIONS.md` D-038.

## Prove it with the parity check

Add the layout to `LAYOUTS` in `tools/parity/run.py`, then run:

```sh
python tools/parity/run.py
```

The check renders every layout, preset and theme combination, compares the plans exactly and the pixels within a threshold, and covers each token at its default and its extreme. A layout is not finished until it passes. If the pixels differ by more than the threshold while the plans match, that is a rendering difference; if the plans differ, the two planners disagree.

## What else notices

- `cards-restyle` offers the layouts it knows, so name the new one there if the skill should offer it.
- The print sheet runs the shared JavaScript engine, so it picks up the new layout without a change of its own.
- The fit report records the layout per card, and the render summary opens with the layout, preset and theme it drew.

## Ask Claude to do it

This is a code change, so ask for it as one: say what the card should look like, put the geometry you have in the issue, and expect the parity check to be the test that settles it.

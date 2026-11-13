# Add a preset

A preset is one JSON file that sets type and shape: which font fills each role in each layout, whether marks are hand-drawn or straight, and how round the corners are. A theme sets colour and a layout sets structure. Changing the preset changes no card text, so approvals stay valid.

## Where the file goes

| Level | Path | Survives plugin updates |
| --- | --- | --- |
| Overlay, Claude Code | `local/presets/<name>.json` | Yes |
| Overlay, claude.ai | `presets/<name>.json` at the unpacked bundle root | Yes |
| Fork | `plugins/tuckcard/skills/cards-core/presets/<name>.json` | No, you merge updates yourself |

An overlay preset wins over a shipped preset of the same name. See `DECISIONS.md` D-038.

## Copy a shipped preset and edit it

```sh
cp plugins/tuckcard/skills/cards-core/presets/casual.json local/presets/warm.json
```

Set `"name": "warm"` to match the file name, then edit:

| Field | What it sets |
| --- | --- |
| `fonts` | One entry per layout (`stacked`, `notebook`, `index`), each naming a `title`, `lines` and `notes` family. Each family must be one of the nine shipped fonts. |
| `mark_wobble` | How far hand-drawn marks stray from the line. `0` draws clean geometric marks. |
| `corner_radius` | Card corner radius in pixels. |
| `mark_styles` | Optional remap from a mark style name to another shape, so a swash can be drawn as a straight underline. The card data does not change. |
| `tokens` | `mark_stroke` (mark line width), `spacing` (a multiplier on line and note gaps), and `title_weight`, `lines_weight`, `notes_weight`. |

A deck's `style.tokens` overrides the preset's tokens for that deck only. `mark_wobble` can be set there too, which turns wobble down without editing the preset.

The file is checked against `schemas/preset.schema.json`. Extra keys are allowed.

## Validate the file

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py local/presets/warm.json
```

Success prints `local/presets/warm.json: valid (preset)`.

## Point a deck at it and render

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_pillow.py \
  --deck local/decks/my-deck/deck.yaml --out renders/my-deck --format png
```

The deck's `style.preset` must be `warm`. Render commands add `local/` as an overlay by default when it exists, so no flag is needed. You should see the fit report summary, then one `<deck-id>-single-NN.png` per card and `fit-report.json`. Changing a font changes the measured line widths, so read the fit report: a card that fitted before can need a smaller size or a rewrite.

If the preset cannot be found, the render stops and the message names every path it tried, both your overlay and the shipped folder.

Run the other renderer on the same deck:

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_playwright.py \
  --deck local/decks/my-deck/deck.yaml --out renders/my-deck-web --format png
```

Both engines read the same preset and plan, so the same card should break lines at the same places. The parity check compares the shipped combinations only; for your own preset, render it with both engines and compare a card side by side.

## Flags

- `--overlay DIR` adds an overlay folder explicitly. It is repeatable, and the first one given wins.
- `--no-default-overlay` leaves `local/` out, so a run cannot pick up a local preset by accident.
- `--overlay` works on `render_pillow.py`, `render_playwright.py` and `build_print_sheet.py`, and `lint.py` passes its overlay to the fit check.

## On claude.ai

A custom preset travels in the deck bundle. Unpack the bundle and the root already holds `themes/` and `presets/`. From that root, pass the root itself as the overlay:

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_pillow.py \
  --deck deck/deck.yaml --out renders/ --overlay . --format png
```

`local/` is a Claude Code convention. On claude.ai the overlay is the unpacked bundle root, so name it with `--overlay`.

## Fonts

The nine shipped families are Archivo Black, Source Serif 4, Shantell Sans, Fraunces, Literata, Caveat, Atkinson Hyperlegible, Liberation Serif and Liberation Sans. All are under the SIL Open Font License 1.1, each with its license file.

In this version a preset can only name those nine. The Pillow renderer holds one table of families, `FONT_FILES` in `render_core.py`, and a name outside it stops the render with `unknown font family`. Using a different font therefore needs a fork: add the font files and an `OFL.txt` under `fonts/<family>/`, add the family to `FONT_FILES`, and add it to `THIRD_PARTY.md` by rerunning `python tools/third_party.py`. The font must allow embedding. The limit is recorded as D-039 in `DECISIONS.md`, settled at the M8 gate: 0.1.0 ships the nine families, and the fork path above is how a user adds their own.

## In a fork

Putting the preset in `cards-core/presets/` makes it a shipped default for everyone using your fork, and you merge upstream changes to that folder by hand. Add it there and rerun the parity check:

```sh
python tools/parity/run.py
```

## Ask Claude to do it

`cards-restyle` does this work for you. It asks what should change, checks contrast and grayscale, previews the longest card, and saves a reusable preset to `local/presets/`.

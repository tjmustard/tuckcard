# Add a theme

A theme is one JSON file that sets colour. A preset sets type and shape, and a layout sets structure. The three are independent, and changing any of them changes no card text, so approvals stay valid.

## Where the file goes

| Level | Path | Survives plugin updates |
| --- | --- | --- |
| Overlay, Claude Code | `local/themes/<name>.json` | Yes |
| Overlay, claude.ai | `themes/<name>.json` at the unpacked bundle root | Yes |
| Fork | `plugins/tuckcard/skills/cards-core/themes/<name>.json` | No, you merge updates yourself |

An overlay theme wins over a shipped theme of the same name, so `local/themes/color.json` replaces the shipped `color` without editing the plugin. The precedence is recorded in `DECISIONS.md` D-038.

## Copy a shipped theme and edit it

```sh
cp plugins/tuckcard/skills/cards-core/themes/color.json local/themes/mint.json
```

Set `"name": "mint"` to match the file name, then edit the colours:

| Field | What it sets |
| --- | --- |
| `background` | Card background. |
| `ink` | Body text. |
| `muted` | Secondary text: notes, header labels. |
| `category_palette` | One colour per category colour name. The shipped keys are `orange`, `teal`, `blue`, `green`, `purple`, `red`, `pink` and `amber`, and a deck's categories pick from them. |
| `mark_colors` | One colour per mark style: `swash`, `highlight`, `underline`, `badge`. A value is a literal colour, another key in the same file, `$category` for the card's category colour, or `$tint`. |
| `tint` | The soft wash behind a highlight mark. |
| `rule`, `on_accent` | Ruled lines, and the text and badge colour drawn on a category colour. |

The file is checked against `schemas/theme.schema.json`. Extra keys are allowed, so a theme can carry a colour the shipped ones do not use.

## Validate the file

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py local/themes/mint.json
```

The folder name, `themes/` or `presets/`, is how the checker knows which schema to use. Success prints `local/themes/mint.json: valid (theme)`.

## Point a deck at it and render

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_pillow.py \
  --deck local/decks/my-deck/deck.yaml --out renders/my-deck --format png
```

The deck's `style.theme` must be `mint`. Render commands add `local/` as an overlay by default when it exists, so no flag is needed. You should see the fit report summary, then one `<deck-id>-single-NN.png` per card and `fit-report.json`. The card background in those images is `#eafff4` if that is what the theme says.

If the theme cannot be found, the render stops and the message names every path it tried, both your overlay and the shipped folder.

Run the other renderer on the same deck:

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_playwright.py \
  --deck local/decks/my-deck/deck.yaml --out renders/my-deck-web --format png
```

Both engines read the same theme file and the same plan, so a card should look the same in each. The parity check compares the shipped combinations only; for your own theme, render it with both engines and compare a card side by side.

## Flags

- `--overlay DIR` adds an overlay folder explicitly. It is repeatable, and the first one given wins.
- `--no-default-overlay` leaves `local/` out, so a run cannot pick up a local theme by accident.
- `--overlay` works on `render_pillow.py`, `render_playwright.py` and `build_print_sheet.py`, and `lint.py` passes its overlay to the fit check.

## On claude.ai

A custom theme travels in the deck bundle. Unpack the bundle and the root already holds `themes/` and `presets/`. From that root, pass the root itself as the overlay:

```sh
python plugins/tuckcard/skills/cards-core/scripts/render_pillow.py \
  --deck deck/deck.yaml --out renders/ --overlay . --format png
```

`local/` is a Claude Code convention. On claude.ai the overlay is the unpacked bundle root, so name it with `--overlay`.

## In a fork

Putting the theme in `cards-core/themes/` makes it a shipped default for everyone using your fork. That changes what the parity check covers, so add it there and rerun:

```sh
python tools/parity/run.py
```

A fork also merges upstream changes to `cards-core/` by hand. The overlay avoids that, which is why it is the recommended place for a theme you just want to use.

## Ask Claude to do it

`cards-restyle` does this work for you. It asks what should change, checks contrast and how the colours read in grayscale, previews the longest card, and writes the theme file.

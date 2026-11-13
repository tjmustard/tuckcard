# Add a mark style

A mark points at a word inside a card line, and the renderer draws something under or behind it. A mark style is one entry in `marks.json` that says what to draw. Cards only name a style; changing the shape changes every card that uses it, with no card edit and no approval change.

## Where the file goes

| Level | Path | Survives plugin updates |
| --- | --- | --- |
| Overlay | none | |
| Fork | `plugins/tuckcard/skills/cards-core/marks.json` | No |

`marks.json` is read from the plugin, not from an overlay, because both engines must agree on it exactly. A new mark style is therefore a fork-level change, alongside a new layout.

## The file

```json
{
  "styles": {
    "swash": {"shape": "cubic", "params": {"points": 6, "amplitude_px": 1.2, "stroke_width": 2.4, "offset_px": 4, "height_px": 4}},
    "highlight": {"shape": "highlight", "params": {"top": 0.52, "bottom": 0.92, "inset_px": 2, "amplitude_px": 1.4, "points": 6}},
    "underline": {"shape": "line", "params": {"stroke_width": 2.2, "offset_px": 4, "amplitude_px": 0}}
  },
  "badge": {"shape": "badge", "params": {"diameter_px": 15, "font_size": 10, "gap_px": 2, "lift_px": 5}}
}
```

`styles` holds the mark shapes. `badge` is the numbered circle drawn in the card header, and it is not a mark style.

## Add a style

Add an entry under `styles`. Its `shape` must be one of `cubic`, `line` or `highlight`, because those are the three shapes both renderers implement: a cubic path, a straight line and a filled band. The `params` that shape understands:

| Shape | Params |
| --- | --- |
| `cubic` | `points` (number of curve samples), `amplitude_px` (how far the line strays), `stroke_width`, `offset_px` (distance below the text), `height_px` |
| `line` | `stroke_width`, `offset_px`, `amplitude_px` (`0` draws a straight line) |
| `highlight` | `top` and `bottom` as fractions of the line height, `inset_px`, `amplitude_px`, `points` |

A style named `wave`, for example:

```json
"wave": {"shape": "cubic", "params": {"points": 10, "amplitude_px": 3.2, "stroke_width": 2.0, "offset_px": 5, "height_px": 6}}
```

Then name it in a card: `mark: {target: Try, style: wave}`. A card that names no style uses the layout's default.

A shape name the code does not know draws nothing, and nothing fails. If a mark is missing from the render, check the `shape` value first.

## A preset can remap it

A preset's `mark_styles` maps one style name to another. The `professional` preset draws a hand-drawn swash as a straight underline that way:

```json
"mark_styles": {"swash": "underline"}
```

That is a preset-level change, so an overlay preset can do it without touching `marks.json`.

## Check both engines

Both renderers read this file and build the same plan, so a style has to look the same in Pillow and in Chromium. Run the parity check:

```sh
python tools/parity/run.py
```

It covers the shipped combinations and every card in the fixture, including its marks. A style that behaves differently between engines fails there.

## Ask Claude to do it

`cards-restyle` can change which style a card uses and remap styles in a preset. A new shape in `marks.json` is a code change, so it belongs in a pull request rather than in a deck.

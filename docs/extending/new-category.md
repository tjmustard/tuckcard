# Add a category

A category groups cards. It carries the label drawn on the card, the colour the card's accent uses, and the contexts that govern what may be written in it. Categories belong to a deck, not to the plugin: they are the deck's own `categories` list.

## Add one to a deck

```yaml
categories:
  - key: practice
    label: Practice
    color: teal
    contexts:
      - athletics
      - personal-growth
```

| Field | What it does |
| --- | --- |
| `key` | The value each card's `category` must carry. Lowercase letters, digits and dashes. |
| `label` | The word or words drawn in the card header. |
| `color` | A key in the theme's `category_palette`, such as `teal` or `orange`. |
| `contexts` | Context names whose rules apply to cards in this category. An empty list is allowed. |

The four fields are exactly what the schema allows. Validate the deck:

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py local/decks/my-deck/deck.yaml
```

That checks each category's shape, that every card's `category` is a declared key, and that each policy value is allowed by the band. It does not check the colour name or the context names, so those two are worth a second look.

## Colour

The `color` value is looked up in the deck's theme, in `category_palette`. A name the theme does not have falls back to the palette's `orange`, then to the theme's `ink`, so a typo shows up as every card in that category turning orange rather than as an error.

Shipped themes carry `orange`, `teal`, `blue`, `green`, `purple`, `red`, `pink` and `amber`. To use a colour those names do not describe, add the key to the theme's `category_palette`: see [new-theme.md](new-theme.md).

## Contexts

`contexts` is how a category borrows rules. A card in `practice` compiles the rules from `context/athletics` and `context/personal-growth` along with the deck's age band and the safety rules. A context name with no rule file simply adds nothing, so the compile is quiet about a typo.

```sh
python plugins/tuckcard/skills/cards-core/scripts/compile_rules.py local/decks/my-deck/deck.yaml
```

Open `effective-rules.yaml` and check the `scopes` list. If a context you mapped is missing from it, the category is where to look.

## Then write cards in it

A new category starts empty. Ask `cards-draft` for cards in it, or write them yourself and then run `cards-review`. Each card names the category in its `category` field, and the key must match one of the deck's categories exactly.

## Coverage

The intake's coverage check looks at the contexts the deck's categories map to, and a scope with no rules, or only rules citing provisional findings, is a reason to run research. Adding a category that maps to a context nobody has written yet is an honest gap, recorded in `knowledge/gaps/`, not a silent hole.

## Ask Claude to do it

`cards-new` sets up the categories during intake. `cards-draft` writes into them, one category per approval round.

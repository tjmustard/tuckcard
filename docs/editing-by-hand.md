# Edit a deck by hand

A deck is plain files, and you can edit them. The skills help, but nothing requires going through one. This page says what is safe to edit, what is generated, and how to check your edit afterwards.

## Safe to edit

| File | What it is | Check it with |
| --- | --- | --- |
| `deck/deck.yaml` or `local/decks/<deck>/deck.yaml` | The deck: recipient, policies, categories, style, cards, approvals. | `validate.py` |
| `themes/<name>.json`, `presets/<name>.json` | A style. Yours live in `local/themes/` and `local/presets/`. | `validate.py` |
| `templates/<layout>/layout.json` | Layout geometry. Fork-level. | `validate.py` |
| `knowledge/findings/*.md` | Findings, in your overlay. | `verify_citations.py` |
| `knowledge/rules/**/*.yaml` | Rules, in your overlay. | `validate_rules.py` |
| `marks.json` | Mark shapes. Fork-level. | `validate.py` |

Shipped knowledge in the plugin is read-only in practice: edits there are lost at the next plugin update. Your own findings, rules, themes and presets belong in the overlay, which is `local/` in Claude Code and the unpacked bundle on claude.ai.

## Generated, don't edit

| File | Written by |
| --- | --- |
| `index.yaml` | `index.py` |
| `effective-rules.yaml` | `compile_rules.py` |
| `fit-report.json` | the renderers |
| `manifest.json` inside a bundle | `bundle.py` |
| `THIRD_PARTY.md` | `tools/third_party.py` |

Each of these carries a header saying where it came from, in the language's own comment form. A change you make to one is either overwritten or, in a manifest, shows up as a hash mismatch. Change the input and regenerate instead.

## After any edit, validate

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py \
  local/decks/my-deck/deck.yaml
```

It prints one line per file, either `valid (deck)` or the schema errors. A rule file, a finding, a theme, a preset and a layout file are all recognised the same way:

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py local/themes/mint.json
python plugins/tuckcard/skills/cards-core/scripts/validate.py \
  local/knowledge/rules/context/my-domain.yaml
```

Then the checks that read across files:

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate_rules.py
python plugins/tuckcard/skills/cards-core/scripts/compile_rules.py \
  local/decks/my-deck/deck.yaml
python plugins/tuckcard/skills/cards-core/scripts/lint.py \
  local/decks/my-deck/deck.yaml --rules local/decks/my-deck/effective-rules.yaml
```

`validate_rules.py` checks rule schema, citations, the evidence floor and overrides. `compile_rules.py` writes the deck's `effective-rules.yaml` again; run it after any rule or category edit. `lint.py` checks the cards against the deck's own compiled rules, so run it after any card or rule change.

## What happens to approvals

A card keeps two hashes: `approved_hash`, the copy as the person approved it, and `linted_hash`, the copy as it last passed lint. The hash covers the title, the lines (text, mark, note), the category and the visibility. It does not cover the card number, the rules cited or the approval record itself.

When you edit a card's words, the card matches neither hash. Then:

- `lint.py` warns that the content matches neither approval hash and was edited since approval. It is a warning, not an error, so you can keep working.
- The render scripts compare each card against both hashes. A mismatch goes in the fit report's `hand_edits` list, with the note "Edited by hand, not linted since. Run cards-review on these cards to clear the flag."
- The `cards-render` skill records `approved_by: hand-edit` in the deck for the cards the fit report names. No render script writes the deck.
- The renderer never blocks. A hand-edited deck still renders, so you can see the change you made.

To clear the flag, run `cards-review` on the deck. It lints the deck and does the judgment pass for rule fit and conflicts, and once the card passes, its approval record is rewritten with the new copy. Fixes to the copy still go back through `cards-draft`, because that is where the approval round happens.

## YAML and comments

Scripts read YAML with the safe loader and write it with ruamel.yaml in block style, so output is stable and readable. Generated files are written whole from their inputs, which is another reason not to keep anything in them you want to persist: a comment there is gone at the next run. Your own files are rewritten only by the skills or scripts that work on them, always with ruamel's round-trip writer, so comments and key order survive.

## If a check disagrees with your edit

A schema error names the file and the field, through a JSON pointer. Read that first: a typo in a key is more common than a wrong value. If the schema rejects something the spec says is allowed, that is a bug in the schema or the spec, so open an issue rather than widening the file.

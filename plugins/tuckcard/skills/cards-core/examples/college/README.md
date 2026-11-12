# College example

A fictional deck for a first-year college student, written in a parents' "we/us" voice. It is one of the shipped examples: `example: true` marks it as fictional copy, not a real deck.

## How it was de-specified

The copy is a de-specified derivative of an approved deck, following SPEC.md Section 9. Every personal item in the source was replaced with a fictional equivalent of the same kind: the major and its clubs and projects, the family roles and relatives a card names, the vehicle, the living situation, the sport and its shorthand, brand names, and the school calendar terms. The deck metadata, category labels and `personal_details` describe the fictional recipient only.

No mapping from the real details to the fictional ones is stored in the repository or in this file.

## Lint fixes applied

- Card 11 ended with a help-line number and card 49 ended with an emergency number. Help numbers and links must match a verified help-resource finding exactly, and none of the shipped findings prints those numbers, so the lines now say "call a crisis line" and "call an ambulance".
- A card title echoed a one-word title from the private reference list and was retitled "Fail, Then PIVOT".
- Remaining warning, accepted and documented: card 53 has text that is shrunk to fit the index layout.

Lint reports 0 errors and 1 warning against the rules compiled for this age band.

## Checking it

Compile the rules for this deck, then lint against them:

```
python ../../scripts/compile_rules.py deck.yaml --out /tmp/college-rules.yaml
python ../../scripts/lint.py deck.yaml --rules /tmp/college-rules.yaml
```

The compiled rules file is not shipped with the example, so `rules_snapshot.sha256` is all zeros as in `examples/parity-fixture`. Compiling and linting needs no network access. The fit check needs Pillow; without it, lint reports that layout fit was skipped.

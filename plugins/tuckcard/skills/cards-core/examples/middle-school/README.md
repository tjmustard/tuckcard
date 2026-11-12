# Middle school example

A fictional deck for an eighth grader, written in a parents' "we/us" voice. It is one of the shipped examples: `example: true` marks it as fictional copy, not a real deck.

## How it was de-specified

The copy is a de-specified derivative of an approved deck, following SPEC.md Section 9. Every personal item in the source was replaced with a fictional equivalent of the same kind: sports and team level, family roles, a place a family might talk, a sport and its shorthand, brand names, a family code word and exit phrase. The deck metadata, category labels and `personal_details` describe the fictional recipient only.

No mapping from the real details to the fictional ones is stored in the repository or in this file.

## Lint fixes applied

- Card 23 ended with a help-line number. Help numbers and links must match a verified help-resource finding exactly, and none of the shipped findings prints that number, so the line now says "call a crisis line".
- Card 47 had a marked word with no note. The card schema requires a note whenever a mark is set, so the mark was removed.
- Remaining warnings, accepted and documented:
  - card 44 reuses one line verbatim from `examples/grade-school`
  - cards 11, 28 and 49 have text that is shrunk to fit the notebook layout

## Checking it

Compile the rules for this deck, then lint against them:

```
python ../../scripts/compile_rules.py deck.yaml --out /tmp/middle-school-rules.yaml
python ../../scripts/lint.py deck.yaml --rules /tmp/middle-school-rules.yaml
```

The compiled rules file is not shipped with the example, so `rules_snapshot.sha256` is all zeros as in `examples/parity-fixture`. Compiling and linting needs no network access. The fit check needs Pillow; without it, lint reports that layout fit was skipped.

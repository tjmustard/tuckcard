# Grade school example

A fictional deck for a third grader, written in a parents' "we/us" voice. It is one of the shipped examples: `example: true` marks it as fictional copy, not a real deck.

## How it was de-specified

The copy is a de-specified derivative of an approved deck, following SPEC.md Section 9. Every personal item in the source was replaced with a fictional equivalent of the same kind: sports and team level, family roles, school details, possessions and brand names, a family signal, and a daily routine. The deck metadata, category labels and `personal_details` describe the fictional recipient only.

No mapping from the real details to the fictional ones is stored in the repository or in this file.

## Lint fixes applied

- No errors. The deck validates as a deck and lints with 0 errors against the rules compiled for its age band.
- Two card titles echoed titles from the private reference deck and were retitled: "Let It GO" and "Wrong Answers TEACH".
- Cards 15, 28, 33 and 46 cited a rule scoped to college readers. Card 15 now cites the grade-school rule on learning and practising how to handle a feeling, and its last note says the practice gets easier. The other three drop that rule and keep a basis that applies to this age band.
- Remaining warnings, accepted and documented:
  - card 42 reuses three lines verbatim from `examples/parity-fixture`
  - card 44 reuses one line verbatim from `examples/middle-school`

Lint reports 0 errors and 4 warnings against the rules compiled for this age band.

## Checking it

Compile the rules for this deck, then lint against them:

```
python ../../scripts/compile_rules.py deck.yaml --out /tmp/grade-school-rules.yaml
python ../../scripts/lint.py deck.yaml --rules /tmp/grade-school-rules.yaml
```

The compiled rules file is not shipped with the example, so `rules_snapshot.sha256` is all zeros as in `examples/parity-fixture`. Compiling and linting needs no network access. The fit check needs Pillow; without it, lint reports that layout fit was skipped.

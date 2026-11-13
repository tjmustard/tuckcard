# Adult example

A fictional deck for a 38-year-old project manager, written in a partner's "I/me" voice. It is one of the shipped examples: `example: true` marks it as fictional copy, not a real deck.

## How it was built

Unlike the other four examples, this one is not a de-specified derivative of an approved deck. It was written fresh on 2026-11-13 against the adult band rules seeded the same day from four findings:

- F-0090, leader autonomy support at work
- F-0091, social relationships and survival
- F-0092, the seven-hour sleep recommendation
- F-0093, what works in loneliness interventions

It also draws on the shipped core, safety, emotional-intelligence and personal-growth rules. Every card's `basis` names the rules it serves. Four cards carry `visibility: private` (17, 21, 25, 42), so lock screens and fridge-facing output leave them out by design.

The fictional recipient's details are in `personal_details`: a team of eight, a marriage, one child in primary school, a father who has started needing help, a train commute, two slow runs a week. Nothing outside that list is asserted as a fact about a person.

## Approval record

Each card's `approval` block records one drafting pass: `approved_by: round`, `approved_round: 1`, with `approved_hash` and `linted_hash` equal. That is the shape the schema requires. It does not mean a card owner read every card the way the rounds in `cards-draft` describe, because the recipient is fictional and there is no owner. The rule set behind the deck was reviewed and approved before drafting.

## Checking it

Compile the rules for this deck, then lint against them:

```
python ../../scripts/compile_rules.py deck.yaml --out /tmp/adult-rules.yaml
python ../../scripts/lint.py deck.yaml --rules /tmp/adult-rules.yaml
```

The compiled rules file is not shipped with the example, so `rules_snapshot.sha256` is all zeros as in `examples/parity-fixture`. Compiling and linting needs no network access. The fit check needs Pillow; without it, lint reports that layout fit was skipped.

Lint reports 0 errors and 0 warnings against the rules compiled for this age band.

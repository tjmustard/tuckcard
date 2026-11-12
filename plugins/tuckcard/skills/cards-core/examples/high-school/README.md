# High School example

A fictional deck for a sophomore in their parents' voice. It is one of the shipped examples: `example: true` marks it as fictional copy, not a real deck. The recipient, the team, the weekend job and the science class are invented; no real person or private source was used.

## How it was made

The deck was written end to end by running the plugin's own workflows for a fictional recipient: `cards-new` intake, the coverage check (no missing scope, so no research round), `cards-draft` in seven approval rounds, `cards-review`, then `cards-render`. Every card carries the round it was approved in and the matching approval and lint hashes. A final copy round (round 8) shortened marked phrases and rewrote four lines after the first render showed text running past the card edge; see "Render fit" below.

The deck uses the stacked layout, the casual preset and the color theme. Its categories are School, Game Day, Feelings, Friends, Growing Up and Home.

## Lint fixes applied

- No lint errors were raised at any point in the run, and none were silenced.
- The review pass changed nine cards for voice and clarity (cards 6, 23, 28, 31, 34, 37, 44, 48 and 50). Those changes were approved in round 7 and re-linted; none of them was a lint finding.
- Round 8 changed the marked phrase or wording on 23 cards so every text row stays inside the 420 px content width. The renderer keeps a marked phrase together, so a long mark could be pushed past the card edge even though the fit report reported no failure.

Remaining warning: none. Lint reports 0 errors and 0 warnings against the rules compiled for this age band.

## Checking it

Compile the rules for this deck, then lint against them:

```
python ../../scripts/compile_rules.py deck.yaml --out /tmp/high-school-rules.yaml
python ../../scripts/lint.py deck.yaml --rules /tmp/high-school-rules.yaml
```

The compiled rules file is not shipped with the example, so `rules_snapshot.sha256` is all zeros as in `examples/parity-fixture`. Compiling and linting needs no network access. The fit check needs Pillow; without it, lint reports that layout fit was skipped.

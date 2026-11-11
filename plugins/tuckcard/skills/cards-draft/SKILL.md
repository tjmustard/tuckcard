---
name: cards-draft
description: Write a Tuckcard deck's copy in approval rounds, one category at a time, linting each batch against the deck's rules. Use after intake and any research are done, or to add or rewrite cards.
---

# cards-draft

Prerequisite: deck `status` is `drafting` (or the user is adding or rewriting cards in a later-stage deck). Follow `../cards-core/ROUNDS.md` for every round, including the crisis stop.

## Before drafting

1. Run `python ../cards-core/scripts/env_probe.py`.
2. Compile the rules if the snapshot is missing or out of date: `python ../cards-core/scripts/compile_rules.py deck.yaml`. This writes `effective-rules.yaml`.
3. Read the deck: voice, policies, personal details, categories and their contexts, numbering, layout.
4. Read the matching age-band example in `../cards-core/examples/` for tone and length only. Never reuse an example line verbatim; lint checks.

## What a card is

- A short title.
- About four or five lines that read as one short passage.
- A few marked phrases, each with a short note that explains or extends it.
- `basis`: the rule IDs the card serves.

Write within the format rules for the deck's layout (`layout.json` capacity). The `notebook` layout holds the least text per line.

## Writing guidance

The compiled rules are the authority. In addition:
- Specific and believable over global and grand: name a real situation and a concrete action.
- Use only personal details the user confirmed. Leave out anything you'd be guessing.
- Match the voice and pronouns exactly.
- Sensitive topics only as the deck's policies allow. Safety rules point to people, not phone numbers, unless the user added verified help resources.
- Mark the private cards (`visibility: private`) when a card names a code word, a health detail or a private struggle.

## Rounds

1. Take the next category. Draft up to about 10 cards.
2. Lint the batch: `python ../cards-core/scripts/lint.py deck.yaml --cards <numbers>`. Fix every error before showing the batch.
3. Show the batch with remaining warnings and each rule's `why`, numbered questions and assumptions.
4. Apply answers, re-lint, show the revised batch, and ask again. Answers are not approval.
5. On approval, record each card's `approved_hash`, `linted_hash`, `approved_by: round` and `approved_round`.
6. Repeat for every category.

For fixes coming back from `cards-review`, redraft only the flagged cards and run them through the same round.

## Hand off

When every category is approved, set `status: drafted` and hand off to `cards-review`. On claude.ai, emit the bundle after each approved category so a dropped conversation loses at most one batch.

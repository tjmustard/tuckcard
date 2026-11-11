---
name: cards-review
description: "Check a Tuckcard deck against its rules: lint, then a judgment pass for rule fit and conflicts. Use before rendering, after hand-editing a deck file, or when asked to review cards."
---

# cards-review

Prerequisite: deck `status` is `drafted` or later, or the user hand-edited a deck and wants it checked. This skill never edits cards; fixes go back through `cards-draft`.

## 1. Lint (deterministic)

1. Run `python ../cards-core/scripts/env_probe.py`.
2. Recompile the rules if the snapshot is out of date.
3. Run `python ../cards-core/scripts/lint.py deck.yaml`. It checks:
   - format and fit for the deck's layout
   - reading level, word by word, plus a deck-level Flesch-Kincaid warning
   - help-resource matching: any number or URL must match a verified resource exactly
   - visibility: cards that look private but are marked public
   - repetition: duplicate titles and heavily overlapping lines; lines reused verbatim from the examples
   - schema validity, including marks without notes and targets missing from their lines
   - hand edits: cards whose content matches neither `approved_hash` nor `linted_hash`

## 2. Judgment pass

Read each card against the compiled rules with `check: judge` or `both`:
- Does the card follow each rule in its `basis`, and does that `basis` still hold after any edits?
- Do any two rules pull a card in opposite directions without a declared `overrides`? Name both rule IDs and suggest an `overrides` entry for the user to approve.
- Does a context rule read as age-specific without a `when: {age_band: ...}` gate?
- Is the voice consistent with the deck's sender and pronouns throughout?

**In Claude Code**, run this pass in a fresh sub-agent that hasn't seen the drafting, so the work isn't grading itself. Give it the deck, the compiled rules and this section. **On claude.ai**, run it in the same conversation.

## 3. Report

Write `deck/review.md`: each flag with card number, severity (error or warning), rule ID and the rule's `why`, then deck-level notes (category balance, reading level, anything repeated). Show the user a short summary and ask which fixes to make.

## 4. Hand off

- Fixes chosen: hand the card numbers and flags to `cards-draft`. Changed cards are re-approved there.
- Clean, or the user accepts the remaining warnings: set `status: reviewed`, record which warnings were accepted, and hand off to `cards-render`.
- On claude.ai, emit the bundle.

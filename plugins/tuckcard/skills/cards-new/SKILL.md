---
name: cards-new
license: MIT
description: "Start a motivational or encouragement card deck for a person or group: runs the intake interview and creates the deck file. Use when someone wants to make motivational, encouragement, habit or pep-talk cards, or attaches a Tuckcard bundle without naming a step."
---

# cards-new: intake

Creates one deck for one person, or for one group sharing the same cards. Follow `../cards-core/ROUNDS.md` for every round, including the crisis stop.

## 0. Before anything

1. Run `python ../cards-core/scripts/env_probe.py` and keep its report for this run.
2. **Bundle attached?** Unpack it to the working directory and read `deck/deck.yaml`. If the user named a step, hand off to that skill. If not, route by `status`:
   - `intake`: continue intake here
   - `researching`: `cards-research`
   - `drafting`: `cards-draft`
   - `drafted`: `cards-review`
   - `reviewed` or `rendered`: ask whether they want to render, restyle or add cards
3. **No bundle:** start a new deck. In Claude Code, decks live in `local/decks/<deck-id>/`.

## 1. Intake, in four rounds

Ask only for what the cards will use.

**Round 1: who it's for**
- Person or group? For a group, only group-level details (no details about individual members).
- Age band: `grade-school`, `middle-school`, `high-school`, `college`, `adult`. Ask the age or grade; don't guess.
- Relationship and voice: who's speaking (parents "we/us", one person "I/me", a coach, the recipient to themselves) and the age-label text for the card (for example "Kid", "High School", "U14").

**Round 2: what the deck covers**
- Purpose in a sentence.
- Categories (usually 4–6), each with a label, a color and the contexts it maps to (`athletics`, `academics`, `emotional-intelligence`, `personal-growth`, `managing-a-team`, `coaching-a-team`, or none). Context rules apply only to cards in mapped categories.
- Count and numbering: weekly (52 plus a bonus card 53, week 1 = the week containing Jan 1, weeks start Sunday) or sequential with a count.

**Round 3: policies and personal details**
- Sensitive topics, each defaulting to `omit`, offered only within the age band's ladder in `../cards-core/knowledge/rules/policies.yaml`: substances, sex and relationships. Explain the options plainly.
- Faith: `neutral`, or `include` with references the user supplies.
- Register: humor level, slang.
- Help resources: off by default. If the user wants help lines on cards, they supply them and `cards-research` verifies each.
- Personal details: only facts the user confirms (sports, activities, situations). Never infer. Culture, faith, family norms and language come only from what the user says.
- Warn, without blocking, if a combination of details would identify a child to strangers on a lock screen (full name plus school plus team, for example).

**Round 4: look and outputs**
- Layout: `stacked` (default), `notebook` or `index`. Show the one-line description of each from `SPEC.md` Section 7. The layout is chosen now so every card is fit-checked against it while drafting.
- Style preset: `casual` (default) or `professional`. Suggest `professional` only when the age band is `adult`.
- Outputs: print sheet, PDF, phone lock screens, tablet lock screens, single PNGs. Page size: Letter or A4.
- Cards that should stay off the fridge and lock screens (`visibility: private`).

## 2. Write the deck

1. Write `deck.yaml` per `SPEC.md` Section 6 with `status: intake`, `schema_version` and `plugin_version`.
2. Validate: `python ../cards-core/scripts/validate.py deck.yaml`. Fix and re-validate until clean.

## 3. Coverage check

For the age band and every mapped context, read the rule file's `status` and the findings index:
- **active** with rules citing active findings: covered.
- **stub**, or rules citing only provisional findings: not covered.

Tell the user which scopes are covered in one or two lines.

## 4. Hand off

- Any scope not covered: set `status: researching` and hand off to `cards-research` with the list of scopes.
- Everything covered: set `status: drafting` and hand off to `cards-draft`.
- On claude.ai, emit the bundle first (`python ../cards-core/scripts/bundle.py`) and remind the user to keep it private.

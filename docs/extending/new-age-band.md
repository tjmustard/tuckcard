# Add an age band

An age band is the file that says how a deck should read for its audience: how many words a title can hold, how many lines a card can take, how long a line can be, and what reading level to warn about. It also carries rules that only apply to that band.

The five shipped bands are `grade-school`, `middle-school`, `high-school`, `college` and `adult`. Several ship as stubs in this version, with their limits unset.

## Where the file goes

| Level | Path | Survives plugin updates |
| --- | --- | --- |
| Overlay, Claude Code | `local/knowledge/rules/age/<band>.yaml` | Yes |
| Overlay, claude.ai | `knowledge/rules/age/<band>.yaml` at the unpacked bundle root | Yes |
| Fork | `plugins/tuckcard/skills/cards-core/knowledge/rules/age/<band>.yaml` | No |

An overlay file of the same name wins over the shipped one, including for a band that already ships. That is how you set limits for `adult` in the overlay without editing the plugin.

## Start from the template

```sh
cp plugins/tuckcard/skills/cards-core/knowledge/rules/age/_TEMPLATE.yaml \
  local/knowledge/rules/age/early-career.yaml
```

Set `scope: age/early-career` to match the file name, and write a `description` that says who the band covers and what is developmentally distinct about them.

```yaml
scope: age/early-career
status: stub
description: People in their first years of work.
defaults:
  reading:
    max_avg_syllables_per_word: null
    familiarity_list: null
    deck_fk_grade_warning: null
  card:
    max_title_words: null
    max_lines: null
    max_words_per_line: null
rules: []
```

A `null` limit means that check does not run for the band. Setting `max_title_words: 6` makes lint fail a title longer than six words. Setting `familiarity_list: list.txt` points at a word list beside the band file, and the file must carry a permissive license.

There is no enum to extend: the deck's `recipient.age_band` is a free string, so a new band needs no schema change.

## The policy ladder, and the omit floor

The per-band policy ladder lives in `knowledge/rules/policies.yaml`, which is a shipped file. A band that is not in its `ladder` falls back to `unlisted_band_default`, which allows only `omit` for `substances` and `sex_relationships`.

So until the band has a ladder entry, a deck on that band can only omit those topics. That is the safe default and it is not a bug. Setting the ladder is a fork-level edit of `policies.yaml`: there is no overlay for it. If you need it in the overlay, say so in an issue rather than editing the shipped file in place.

## What is checked

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate.py local/decks/my-deck/deck.yaml
```

The deck's policy values are checked against the band's ladder. A value the band does not allow is an error naming the value and the allowed set.

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate_rules.py
```

This checks the rule file's schema, citations, evidence floor and overrides. It adds `local/knowledge/` by default when it exists.

## Use it in a deck

```yaml
recipient:
  kind: person
  pill: A first job
  age_band: early-career
  description: A fictional 23 year old starting their first full-time job.
  culture_notes: null
```

Then compile and lint:

```sh
python plugins/tuckcard/skills/cards-core/scripts/compile_rules.py local/decks/my-deck/deck.yaml
python plugins/tuckcard/skills/cards-core/scripts/lint.py local/decks/my-deck/deck.yaml \
  --rules local/decks/my-deck/effective-rules.yaml
```

The compile picks up `age/early-career.yaml` from the overlay, and lint applies its limits from then on.

## Fill it with research

Run `cards-research` on the band. It plans the questions, verifies sources, writes findings and proposes rules for approval. `knowledge/RESEARCH-GUIDE.md` describes that work and this page does not repeat it.

Age-band rules may be specific to the band. That is the difference from a context, whose rules must stay age-neutral and gate anything age-specific with `when: {age_band: [...]}`.

## Ask Claude to do it

`cards-research` does the research and rule writing. It proposes each rule for approval before the file changes.

# Add a context

A context is a domain a deck can be about: athletics, academics, managing a team. It carries rules that apply to the categories mapped to it. An age band carries rules for who the deck is for. A rule can be in both, and the age band wins where they disagree.

## Where the file goes

| Level | Path | Survives plugin updates |
| --- | --- | --- |
| Overlay, Claude Code | `local/knowledge/rules/context/<name>.yaml` | Yes |
| Overlay, claude.ai | `knowledge/rules/context/<name>.yaml` at the unpacked bundle root | Yes |
| Fork | `plugins/tuckcard/skills/cards-core/knowledge/rules/context/<name>.yaml` | No |

An overlay rule file adds to the shipped ones. Both are read when the deck's rules are compiled, and every rule records the file it came from. A rule id can only be declared once, so replacing a shipped rule means adding a rule with its own id and listing the shipped one in `overrides`.

## Start from the template

```sh
cp plugins/tuckcard/skills/cards-core/knowledge/rules/context/_TEMPLATE.yaml \
  local/knowledge/rules/context/my-domain.yaml
```

The template is four fields:

```yaml
scope: context/<name>
status: stub
description: The domain this context covers.
typical_relationship: null
rules: []
```

Set `scope` to `context/my-domain`, matching the file name. Leave `status: stub` until the file has rules: a stub is read as "this context exists and nothing is written for it yet", which is a truthful state and does not stop a deck from rendering.

## Fill it with research

Run `cards-research` on the context and point it at your file. It plans the questions, finds and verifies sources, writes findings under `knowledge/findings/`, and proposes rules for approval. `knowledge/RESEARCH-GUIDE.md` is the only description of how that work is done, so this page does not repeat it.

Each rule cites at least one finding and carries an evidence grade. A rule looks like this:

```yaml
  - id: R-my-domain-001
    type: do
    strength: should
    applies_to: [title, lines]
    when: null
    overrides: []
    text: The rule, as a direction to whoever writes the card.
    why: What the sources support, in one sentence.
    cites: [F-0100]
    check: judge
    lint: null
    examples:
      bad: "A card line that breaks the rule."
      good: "A card line that follows it."
```

Keep rules age-neutral and gate anything age-specific instead:

```yaml
    when: {age_band: [high-school, college]}
```

Age-specific guidance belongs in `rules/age/<band>.yaml`. A context that hard-codes one band's needs is the wrong shape for every other band that maps to it.

## Check the file

```sh
python plugins/tuckcard/skills/cards-core/scripts/validate_rules.py
```

It checks the rule schema, that every citation resolves, the evidence floor and that overrides are permitted. The overlay is added by default when `local/knowledge/` exists. Add `--overlay DIR` to name one explicitly, or `--no-default-overlay` to leave it out.

## Use it in a deck

A context only reaches a card through a category. In the deck's `categories`, list the context on the category it belongs to:

```yaml
categories:
  - key: practice
    label: Practice
    color: teal
    contexts:
      - my-domain
```

Then compile the deck's rules again and reread its `effective-rules.yaml`:

```sh
python plugins/tuckcard/skills/cards-core/scripts/compile_rules.py local/decks/my-deck/deck.yaml
```

The compiled file lists the rules the deck will be linted against, with the scope each came from. If your context's rules are absent, the category mapping is the first thing to check.

## In a fork

A context in `cards-core/knowledge/rules/context/` is a shipped default for everyone using your fork, and it must pass `validate_rules.py` in CI. If it adds a sensitive topic, that topic also needs a key and a ladder entry in `rules/policies.yaml`. The overlay avoids all of that.

## Ask Claude to do it

`cards-research` writes the findings and the rules, and it proposes each rule for approval before the file changes.

<div align="center">
    <img src="./media/icons/icon-1024.png" width="128" height="128" alt="Tuckcard icon" style="border-radius: 28px; box-shadow: 0 8px 24px rgba(0,0,0,0.25);" />
    <h1>Tuckcard</h1>
    <p><strong>Short, research-informed cards for someone you know.</strong></p>
    <p><em>A Claude plugin that interviews you, checks what the research says for that age and setting, drafts the copy with you a batch at a time, and renders a deck for the fridge or a lock screen.</em></p>
    <p>
        <a href="./LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"/></a>
        <img src="https://img.shields.io/badge/version-0.1.0-orange.svg" alt="Version"/>
        <img src="https://img.shields.io/badge/skills-7-informational.svg" alt="Skills"/>
        <img src="https://img.shields.io/badge/examples-3%20%C2%B7%20159%20cards-indigo.svg" alt="Examples"/>
        <img src="https://img.shields.io/badge/output-print%20%2B%20PDF%20%2B%20lock%20screen-amber.svg" alt="Output"/>
    </p>
</div>

---

## What this is

You tell Claude who the cards are for: a third grader on a town team, a high-school junior, a nephew starting college, a team you coach. Tuckcard runs an intake interview, researches the age band and the contexts that apply (school, athletics, feelings, friendships), drafts the cards with you one category at a time, checks every card against the rules it was written from, and renders the deck as a print sheet, a PDF, lock screens and single-card images.

Two things make it more than a text generator.

**The cards are written from rules, not vibes.** The knowledge tree holds findings with sources, verification and status, and rule files compiled from them. Every card cites the rules it was written from, and `lint.py` fails the deck if a card cites a rule that is not in its compiled rules, if a mark points at text that is not there, or if a help-line number does not match a verified resource. A deck stores its own compiled rules, so an old deck re-lints against the rules it was made with.

**The person is in the loop by construction.** Drafting happens in approval rounds, one category at a time, and the deck records which cards the person approved. A card edited by hand afterwards no longer matches its approval hash and is flagged rather than silently shipped.

## Status

Tuckcard is at version 0.1.0 and is **not yet tagged for release**. What is true today:

- The plugin installs from this repository's marketplace in Claude Code and lists seven skills. That path is tested.
- Three example decks ship and are lint-clean, with their remaining warnings documented in each example's README.
- The render path is covered by a parity check across 18 layout, preset and theme combinations.
- **The claude.ai half of the acceptance test has not been run.** It needs a paid account and a platform probe that has not happened. Treat claude.ai support as expected but unproven.
- The public README, extending docs, hand-edit guide and release tag land with milestone M8.

## Install

Requires Claude Code, and Python 3.9 or newer for the scripts the skills call.

```sh
claude plugin marketplace add tjmustard/tuckcard
claude plugin install tuckcard@tuckcard
```

Then check what arrived:

```sh
claude plugin details tuckcard      # lists the seven skills
```

Start with `cards-new` for a fresh deck, or open one of the examples to see what a finished deck looks like.

## Making a deck

The skills are a chain, each naming the next. There is no orchestrator.

| Skill | What it does |
|---|---|
| `cards-new` | Runs the intake interview and writes the deck file: recipient, age band, categories, policies, page size, numbering. |
| `cards-research` | For an age band or context that is thin: plans the questions, finds and verifies sources, records gaps, proposes findings. Only when a scope needs it. |
| `cards-draft` | Writes the copy in approval rounds, one category at a time, linting each batch against the deck's own rules. |
| `cards-review` | Lints, then does a judgment pass for rule fit and conflicts. Never edits cards. |
| `cards-render` | Renders the print sheet, PDF, lock screens and single-card PNGs, with a fit report for every card. |
| `cards-restyle` | Changes layout, preset, theme, colours, fonts or spacing, previewing one card before re-rendering everything. |
| `cards-core` | The shared engine the others call: schemas, knowledge, rules, renderers, examples. Not invoked directly. |

## What a card is

A card is a record, not a picture. It has a number, a category, a title and a handful of lines, each optionally carrying a mark (a word to highlight) and a note (the aside underneath). It also carries the rules it was written from and the approval hash the person's sign-off produced.

```yaml
- n: 1
  category: growth
  title: Try It AGAIN
  lines:
    - text: First tries are practice.
      mark: {target: First}
      note: Nobody nails it on try one.
    - text: Change one little thing
      mark: {target: Change}
      note: Slower? Softer? Other foot?
  visibility: public
```

Cards are `public` or `private`. Private cards never reach the fridge sheet or the lock screens, which is the difference between a card for the wall and a card for a phone only that person sees.

## The examples

Three fictional examples under `plugins/tuckcard/skills/cards-core/examples/`, 53 cards each, written in the parents' we/us voice. They exist so the repo has something real to lint, render and argue about, and they are de-specified derivatives rather than anybody's private deck.

| Example | Audience in the deck |
|---|---|
| `grade-school` | A fictional third grader on a town team, learning to name feelings and keep trying. |
| `middle-school` | The 13 to 14 band. |
| `college` | A student leaving home for the first time. |

Each has a `README.md` listing the fixes applied during review and the warnings that remain. There is also `parity-fixture`, a five-card deck that exists only so the renderers can be compared against each other.

The high-school example is deliberately absent. It is written at M7 by running the plugin end to end on a fictional recipient, so the example and the acceptance test are the same artefact.

## Looks

A deck picks one of each:

- **Layout:** `stacked` (title above body), `notebook` (ruled page, handwritten feel) or `index` (card-catalogue index card).
- **Preset:** `casual` or `professional`.
- **Theme:** `color`, `dark` or `mono`. `mono` is the black-and-white path, for printing without colour or for anyone who needs high contrast.

Outputs are a printable sheet, a PDF, lock screens sized for phone and tablet, and single-card PNGs. Every render writes a fit report saying whether the copy fits its card, and the renderers are checked against each other so the HTML reference design and the Playwright and Pillow renderings do not drift.

## The knowledge behind the cards

`knowledge/` holds the evidence side of the plugin:

- `findings/` records with sources, verification and a status: `active`, `contested`, `provisional` or `quarantined`. A retracted or corrected source quarantines its finding automatically.
- `rules/` rule files, compiled into the rules a deck is linted against. The rule files total 101 rules; a deck compiles only the ones its age band and contexts apply, which is 54 for the grade-school example and 62 for the college example.
- `gaps/` what the research does not answer. A gap is a written admission, not an empty folder.
- `RESEARCH-GUIDE.md` the single source for how research is done, and `sources-allowlist.yaml` the domains a source may come from.

Age bands and contexts carry their own policies: which sensitive topics are omitted, neutral or allowed, and the help-line rules. Help lines are off by default in a deck; when they are on, a number on a card must match a verified resource or lint fails.

## Repository layout

```
.claude-plugin/          marketplace manifest
plugins/tuckcard/
  .claude-plugin/        plugin manifest and icon
  skills/
    cards-core/          shared engine: schemas, knowledge, scripts, renderers,
                         examples, fonts, layouts, marks, presets, themes
    cards-new/           intake
    cards-research/      research a scope
    cards-draft/         write copy in approval rounds
    cards-review/        lint and judgment pass
    cards-render/        print, PDF, phone, PNG
    cards-restyle/       change the look
tests/                   schema fixtures, tool tests, example checks
tools/                   development-only helpers, never shipped
media/                   icons
SPEC.md                  the design
DECISIONS.md             every deviation from the spec, and why
CHANGELOG.md             what changed, with evidence
```

`tools/`, `tests/`, `reference/` and `docs/` never ship inside the plugin.

## Developer setup

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

`requirements.txt` pins the validation path (jsonschema, ruamel.yaml, pytest) and holds a Python 3.9 floor; `requirements-dev.txt` adds the rendering path (Pillow, Playwright). With the development set the suite is 243 tests; with `requirements.txt` alone it is 188 passing and 3 module skips, which are the render modules that need Pillow and Playwright.

CI runs on Ubuntu 24.04 with Python 3.9 and 3.12 and adds three checks of its own: both manifests parse, every font family ships a font file and its OFL license, and no `deck.yaml` outside `examples/`, no bundle and nothing under `renders/` is committed.

Useful single commands:

```sh
python plugins/tuckcard/skills/cards-core/scripts/compile_rules.py deck.yaml
python plugins/tuckcard/skills/cards-core/scripts/lint.py deck.yaml --rules effective-rules.yaml
python plugins/tuckcard/skills/cards-core/scripts/validate.py deck.yaml
```

## Disclaimers

1. These cards aren't therapy, counseling or medical advice. In a crisis, call or text 988 in the US, or your local emergency number.
2. The cards are research-informed; no deck is claimed to improve outcomes.
3. Deck bundles contain personal details, so keep them private. The example decks are fictional.
4. When writing for minors, the adult making the deck reviews every word.
5. This project isn't affiliated with or endorsed by Anthropic.

## License

MIT for code, skills, docs, findings, rules and examples. Bundled fonts are under the SIL Open Font License 1.1, each with its license file.

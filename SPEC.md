# Tuckcard specification

Version 0.1, approved 2026-11-10. This is the source of truth for building the repository. Where this document and a skill, a script or your own defaults disagree, this document wins. Where this document is silent or contradicts itself, stop and ask the maintainer rather than guessing (see `BOOTSTRAP.md`).

Sections 1–10 were approved one at a time. Later decisions that changed an approved section are merged into that section, and Appendix B records each one.

**Contents**
1. Purpose, scope, principles
2. Architecture
3. Research layer
4. Rules layer
5. Skills
6. Data model
7. Render pipeline
8. Customization and extension
9. Privacy, ethics, licensing
10. Seed kit and bootstrap
- Appendix A: Fast follows
- Appendix B: Decisions log
- Appendix C: Platform facts

---

## 1. Purpose, scope, principles

### Purpose

An MIT-licensed GitHub repository that is also a Claude plugin marketplace. It ships one plugin, `tuckcard`, made of several skills. Together they guide someone through creating one deck of short motivational cards for a specific person or group, using research and rules shipped in the plugin, and render the deck for print and screens. It runs in claude.ai chat, Claude Desktop, Cowork and Claude Code.

### Users

People on paid claude.ai plans (Pro, Max, Team, Enterprise) and Claude Code users. Free plans are not supported in v1 (see FF-2).

### Platform constraints

- **claude.ai chat**
  - Skills are read-only and each conversation's sandbox is temporary, so everything the plugin creates leaves as a download.
  - Network access from code depends on plan and admin settings. The core flow cannot depend on it.
  - Sub-agents and hooks are unavailable in chat.
- **Claude Code:** files are written in place, scripts get normal network access, and sub-agents are available as an enhancement (for example, an independent review pass).
- **Design rule:** every core workflow runs in claude.ai chat using skills alone.

### In scope (v1)

- One deck per run, for one person or one group sharing the same cards. Per-player decks mean one run per player.
- English only.
- Three card layouts, `stacked` (default), `notebook` and `index`, all reading one card data model.
- The guided flow: intake → research if the context isn't covered → rules → copy drafted and approved in rounds → lint → render.
- Rendering uses the best tool each platform has, from one HTML template per layout:
  - **Claude Code:** Playwright renders a vector print PDF with cut lines (color and B&W), phone and tablet lock screens, and single-card PNGs. It also writes the HTML print sheet.
  - **claude.ai:** a self-contained HTML print sheet the user prints from their own browser, plus Pillow-rendered lock screens, single-card PNGs and a raster PDF.
- A deck bundle: the deck file plus any new research, rules, themes and presets. Later runs start from the bundle to restyle, re-render or add cards.
- Research verification tagged by method. A finding verified only by fetch stays provisional, and no rule can cite it until a script check upgrades it.
- Four example decks (grade school, middle school, high school, college), fully de-specified.
- Research suggestions through a GitHub issue template.

### Out of scope (v1)

A web UI or hosted service; AI image generation; non-English decks; several decks in one run; pull requests that add research; Free-plan support; clinical or crisis content beyond pointing to people and, when the user adds them, verified resources; claims that a deck improves outcomes.

### Principles

1. **Research-informed and graded.** Every rule cites verified findings with an evidence grade.
2. **Tailored to the person.** Age band and context set the defaults. Culture, faith, family norms and language come only from the user's description of the recipient. Nothing is inferred from sex, ethnicity or any other category the user didn't supply.
3. **Specific and believable over global and grand.** Cards name real situations and concrete actions.
4. **A human approves every word.** Nothing unapproved is rendered without a visible flag (Section 2, approval enforcement).
5. **Content is data.** Copy, rules and styling live in plain files, and rendering is deterministic per platform.
6. **Private by default.**
7. **Fixed safety lines, flexible tone.** The user picks policies at intake, within what the age band allows, and no deck can override `rules/safety/`.
8. **claude.ai chat is the baseline.** Anything that needs Claude Code, sub-agents or hooks is an enhancement.

---

## 2. Architecture

### Names

| Thing | Name |
|---|---|
| Repository | `tuckcard` (github.com/tjmustard/tuckcard) |
| Marketplace | `tuckcard` |
| Plugin | `tuckcard` |
| Skills | `cards-core`, `cards-new`, `cards-research`, `cards-draft`, `cards-review`, `cards-render`, `cards-restyle` |

Skills carry the `cards-` prefix so generic names like `render` don't collide with other plugins or trigger on unrelated requests. Invoked by name they read as `/tuckcard:cards-new`.

### Layers

1. **Research.** Findings, one claim per file, each with a citation, evidence grade, verification record and scope tags. Findings describe the world and never give instructions.
2. **Rules.** Decisions that cite findings, organized by scope: `core`, `safety`, `age/<band>`, `context/<name>`. Context files can start as stubs.
3. **Deck.** One per run: the recipient profile, intake choices (voice, policies, layout, count, numbering, formats), a snapshot of the compiled rules, the cards and their approval records.
4. **Render.** One HTML/CSS template per layout, layout files, theme and preset token files, bundled fonts, and three output paths: Playwright, the HTML print sheet and Pillow.
5. **Workflow.** The skills. They read layers 1–4 and write only to the deck or to the overlay.

### Data flow

Intake → resolve scopes (age band + contexts mapped from categories) → coverage check → research, if a scope is missing or its rules cite only provisional findings → user approves proposed rules → compile the effective rules → draft cards in rounds, linting each batch → approve → review → render → bundle.

### Rule precedence

Applied when rules are compiled: **safety > deck policy > age band > context > core**. Nothing overrides safety. Below that, the more specific scope wins, and developmental fit (age band) outranks the conventions of a domain (context).

### Persistence: the overlay model

Shipped knowledge is read-only on every platform. New findings, rules, themes and presets go into an overlay that is merged on top at compile and render time.
- On claude.ai the overlay travels inside the deck bundle.
- In Claude Code it lives in `local/`.

Both platforms share one merge path, and pulling plugin updates never conflicts with a user's own research. The only route from overlay to shipped knowledge is `promote.py`, run by the maintainer (Section 3).

### Approval enforcement

Each card keeps two hashes:
- `approved_hash`: the card's approvable content as it was approved.
- `linted_hash`: the same content as it last passed lint.

Hand edits are allowed. When the renderer finds a card whose content matches neither hash, it treats the change as the user's own edit: it records `approved_by: hand-edit`, renders the card, and lists it in the fit report as "edited by hand, not linted since," with a pointer to `cards-review`. The renderer never blocks.

### Skills

| Skill | What it does | Hands off to |
|---|---|---|
| `cards-core` | Library: knowledge, schemas, templates, layouts, themes, presets, fonts, scripts, examples. Never invoked directly. | none |
| `cards-new` | Intake interview, creates the deck, runs the coverage check | `cards-research` or `cards-draft` |
| `cards-research` | Plans questions, searches, writes and verifies findings, records gaps, proposes rules for approval | back to its caller, usually `cards-draft` |
| `cards-draft` | Writes copy in category batches with approval rounds, linting each batch | `cards-review` |
| `cards-review` | Lints the full deck, then a judgment pass for rule fit and conflicts. Works on hand-edited decks too. | `cards-draft` for fixes, or `cards-render` |
| `cards-render` | Picks the platform's output path, renders, runs the fit report | none |
| `cards-restyle` | Changes layout, preset, theme, colors, fonts or layout tokens, previewing one card first | `cards-render` |

### Directory tree

```
tuckcard/                                  # the repo is also the marketplace
├── .claude-plugin/marketplace.json
├── plugins/tuckcard/
│   ├── .claude-plugin/plugin.json
│   └── skills/
│       ├── cards-core/
│       │   ├── SKILL.md                   # library; not invoked directly
│       │   ├── ROUNDS.md                  # approval protocol and crisis stop
│       │   ├── knowledge/
│       │   │   ├── RESEARCH-GUIDE.md
│       │   │   ├── sources-allowlist.yaml
│       │   │   ├── findings/              # F-0001.md ..., flat pool; index.yaml generated
│       │   │   ├── quarantine/
│       │   │   ├── gaps/
│       │   │   └── rules/
│       │   │       ├── core.yaml
│       │   │       ├── policies.yaml
│       │   │       ├── safety/
│       │   │       ├── age/               # grade-school, middle-school, high-school, college, adult
│       │   │       └── context/           # athletics, academics, personal-growth, emotional-intelligence,
│       │   │                              # managing-a-team, coaching-a-team
│       │   ├── schemas/                   # JSON Schemas (Section 6)
│       │   ├── templates/                 # stacked/, notebook/, index/: card.html, card.css, layout.json
│       │   ├── marks.json
│       │   ├── themes/                    # color, mono, dark
│       │   ├── presets/                   # casual, professional
│       │   ├── fonts/                     # OFL fonts + license files
│       │   ├── scripts/                   # validate, verify_citations, index, validate_rules, compile_rules,
│       │   │                              # lint, bundle, promote, migrate, env_probe,
│       │   │                              # render_playwright, render_pillow, build_print_sheet
│       │   └── examples/                  # grade-school, middle-school, high-school, college
│       ├── cards-new/SKILL.md
│       ├── cards-research/SKILL.md
│       ├── cards-draft/SKILL.md
│       ├── cards-review/SKILL.md
│       ├── cards-render/SKILL.md
│       └── cards-restyle/SKILL.md
├── local/                                 # Claude Code overlay
│   ├── knowledge/                         # the user's own findings and rules (tracked)
│   ├── themes/  presets/                  # the user's own styles (tracked)
│   └── decks/                             # private decks (gitignored)
├── reference/layouts/                     # original design prototypes, the visual source for M3
├── tools/                                 # probe-plugin, build/zip, parity check, PII scan (repo only)
├── tests/                                 # repo only
├── docs/                                  # extending/, editing-by-hand.md
├── .github/ISSUE_TEMPLATE/suggest-research.yml
├── .github/workflows/                     # ci.yml, weekly-recheck.yml
└── CLAUDE.md, SPEC.md, BOOTSTRAP.md, README.md, LICENSE, THIRD_PARTY.md, .gitignore
```

`tools/`, `tests/`, `reference/` and `docs/` live only in the repo and never ship inside the plugin.

---

## 3. Research layer

### The two questions verification answers

1. **Does the source exist and match its metadata?** A script can settle this.
2. **Does the source support the claim?** Only reading the source can settle this. A hallucinated finding with a real DOI attached passes the first check and fails the second.

Each finding records both checks separately.

### Finding file

One markdown file per finding in `knowledge/findings/`, with YAML frontmatter and a short body written in the repo's own words. Template: `knowledge/findings/_TEMPLATE.md`.

```yaml
---
id: F-0007
claim: >
  Among undergraduates low in self-esteem, repeating a global positive
  self-statement left mood and self-regard worse than not repeating it.
direction: caution          # supports | caution | null | mixed
scopes: [core]
grade: B
design: experiment
population: undergraduates
effect: not extracted       # metric and size when reported; never estimated
distance: adjacent          # direct | adjacent | distal: how close the setting is to reading a card
replication: unknown        # replicated | mixed | failed | unknown
source:
  citation: "Wood, Perunovic & Lee (2009). Psychological Science 20(7):860–866."
  doi: 10.1111/j.1467-9280.2009.02370.x
  pmid: 19493324
verification:
  exists: script            # none | fetch | script
  metadata_match: [title, year, first_author]
  retraction: none          # none | correction | concern | retracted
  support: abstract         # unchecked | abstract | full_text
  anchor: "<one excerpt of 15 words or fewer from the checked text>"
  checked_on: 2026-11-03
status: active              # provisional | active | contested | quarantined
related: []                 # IDs of supporting or contradicting findings
---
**Implication for cards.** Avoid global, unconditional self-praise. Prefer
statements the reader can check against their own experience.

**Limits.** Undergraduate sample, short-term mood measures, lab setting.
```

### Evidence grades

| Grade | Design |
|---|---|
| A | Systematic review or meta-analysis |
| B | Randomized or preregistered experiment |
| C | Observational, correlational or quasi-experimental study |
| D | Guidance from public-health or professional bodies |
| E | Theory, expert opinion, practitioner literature |

Three fields qualify every grade:
- `distance`: no study tests a fridge card, so every finding states how far its setting is from reading one.
- `replication`: replicated, mixed, failed or unknown.
- `direction`: whether the finding supports a practice, warns against it, found nothing, or is mixed.

### Verification

- **Existence by script.** `verify_citations.py` resolves DOIs through the Crossref REST API and PMIDs through PubMed, then compares title, year and first author against the finding. It also checks retractions and corrections through Crossref's `update-to` field, which carries both publisher and Retraction Watch records. For guidance documents without a DOI it checks that the URL resolves, that its domain is on `knowledge/sources-allowlist.yaml`, and that the page title matches. The script runs on any platform whose network allows it.
- **Existence by fetch.** The fallback when the script can't reach the network. Claude opens the DOI or PubMed page with its web tools and records the same fields, with `exists: fetch`.
- **Support check** (both platforms). Claude reads the abstract, or the full text when it's open access, and confirms the claim. It records the depth of reading and one anchor excerpt of 15 words or fewer, so a human can audit the judgment quickly.

### Status rules

| Status | Condition | What it can back |
|---|---|---|
| `provisional` | `exists: fetch`, or `support: unchecked` | Nothing |
| `active` | `exists: script`, support at `abstract` or deeper, retraction `none` or `correction` | Any rule, subject to the evidence floor |
| `contested` | Active, but replication is mixed or failed, or a related active finding points the opposite way | Only `avoid` and `must_not` rules |
| `quarantined` | Source didn't resolve, metadata didn't match, claim unsupported, expression of concern, or retraction | Nothing. The file moves to `quarantine/` with `quarantine_reason`. |

### Invariants

1. Every shipped finding is `active` or `contested`. CI runs the script check on every push and weekly. A new retraction fails the build and flags every rule that cites the paper.
2. Before adding a finding, the research skill checks the pool and the quarantine by DOI. A quarantined citation can't re-enter under a new ID.
3. Nothing is deleted automatically.
4. Findings are paraphrased. The repo stores no abstracts or full text, only the single anchor excerpt per finding.

### Research procedure

`knowledge/RESEARCH-GUIDE.md` is the single source for how agents research a scope: the question plan, search order, writing findings, where to save them, verification, gap entries, referencing and handoff. Skills and `CLAUDE.md` point to it and do not restate it. The question plan is shown to the user and approved before any searching, on both platforms.

### Gap entries

When a planned question turns up nothing usable, the research skill writes a gap entry to `knowledge/gaps/<scope>.md`: the question, the searches tried and the date. Later runs read gap entries first and don't repeat dead searches. Gap entries ship with the seed, so users and contributors can see which questions have no evidence behind them.

### Findings index

`knowledge/findings/index.yaml` is generated by `scripts/index.py`: one entry per finding with ID, one-line claim, scopes, grade, direction and status. Skills read the index first and open individual findings only when needed, which keeps context small on claude.ai.

### Seeding the research

v1 ships pre-researched for `core`, `safety`, all four example age bands (`grade-school`, `middle-school`, `high-school`, `college`) and the `athletics`, `academics`, `emotional-intelligence` and `personal-growth` contexts. `adult`, `managing-a-team` and `coaching-a-team` ship as stubs. Target: 10–20 active findings per seeded scope.

Two paths can produce the seed:
- **Path A, Claude Code:** run `cards-research` directly, following `RESEARCH-GUIDE.md`.
- **Path B, paid claude.ai with Research:**
  1. `cards-research` writes the approved question plan as a ready-to-paste Research prompt.
  2. The maintainer runs Research with that prompt.
  3. In the same chat, `cards-research` turns the report into finding files. It follows each report citation back to the primary source, since the report itself is a secondary source. It verifies by script if the network allows, otherwise by fetch.
  4. The run ends with a bundle.

  Path B never depends on a skill starting Research by itself.

### Promotion

`scripts/promote.py` is the only way findings and rules move from an overlay into the shipped files, whatever produced them. It:
1. takes findings and rules from a bundle or from `local/`
2. renumbers `L-` IDs to the next `F-` IDs and overlay rule IDs to shipped rule IDs, rewriting every reference in rules and gap entries
3. runs the script check
4. moves findings that pass into `cards-core/knowledge/findings/` and findings that fail into `quarantine/`
5. regenerates `index.yaml`

Promotion is a maintainer step, run wherever the script can reach Crossref and PubMed. CI then enforces invariant 1. A GitHub Action version is FF-1.

---

## 4. Rules layer

### Rule file

One YAML file per scope, `knowledge/rules/<scope>.yaml`. Template: `knowledge/rules/_TEMPLATE.yaml`.

```yaml
scope: core
status: active                 # active | stub
description: Applies to every deck.
rules:
  - id: R-core-003
    type: avoid                # do | avoid | must | must_not | format
    strength: should           # must = lint error, should = warning
    applies_to: [title, lines, notes]
    when: null                 # gate on deck policy and/or age band, e.g. {substances: harm_reduction}
    overrides: []              # lower-precedence rule IDs this replaces
    text: Avoid global, unconditional self-praise.
    why: Sweeping self-praise can leave readers low in self-esteem feeling worse.
    cites: [F-0007]
    check: judge               # lint | judge | both
    lint: null                 # pattern spec when check includes lint
    examples:
      bad: "I am unstoppable."
      good: "I've come back from a bad first half before."
```

### Rule types and evidence floor

| Type | Meaning | Evidence floor | Severity |
|---|---|---|---|
| `do` | Prefer this pattern | At least one active finding graded A or B, or D for practical safety guidance | Judged at deck level for coverage |
| `avoid` | Steer away from this | Any active or contested finding | Warning |
| `must` / `must_not` | Hard line | Active finding graded A, B or D | Error |
| `format` | Length, structure, reading level | None; records `basis: template` instead, since these come from layout fit | Error or warning |

The asymmetry is deliberate: weak evidence that a phrasing backfires is enough to avoid it; weak evidence that it helps is not enough to require it.

### Scopes

- **core:** applies to every deck, including principle-level rules such as never inferring anything about the recipient from categories the user didn't supply.
- **safety:** the fixed lines. No deck policy or other scope can override them.
- **age/\<band\>:** developmental fit, reading targets, and which policy values the band allows.
- **context/\<name\>:** domain conventions. Context rules apply only to cards in categories mapped to that context: athletics rules govern "Game Day" cards, not "Feelings" cards. Core, age-band and safety rules apply to every card.

**Context rules must be age-neutral.** Anything age-specific goes in the age-band file, or the context rule is gated with `when: {age_band: [...]}`. Example: "point the player to a parent or coach" is age-specific. This keeps an adult sports deck (`adult` band + `athletics` context) from inheriting kids' rules. `RESEARCH-GUIDE.md` step 8 and the `cards-review` judge pass both enforce it.

### Precedence mechanics

Conflicts are declared, not inferred. A rule names the lower-precedence rules it replaces in `overrides`, and gates itself on deck policy or age band with `when`. `validate_rules.py` rejects any override of a safety rule or of a higher-precedence scope. Compiling is deterministic. Conflicts nobody declared are caught by the judge pass in `cards-review`, which names both rule IDs and suggests an `overrides` entry for the user to approve. A dedicated conflict scan is FF-3.

### Safety topics

This list is fixed. Seed research writes the rule text for each, at grade D or better.
1. Self-harm and suicide
2. Eating, weight and body image
3. Alcohol and other drugs
4. Sex, consent and online sexual exploitation
5. Abuse, bullying and unsafe adults
6. Medical and mental-health claims: no diagnosing, and no claims that a card treats anything
7. Shame, threats and conditional worth (for example, "we're proud of you when you win"), including job-security pressure in manager decks
8. Visibility: fridge cards and lock screens can be seen by anyone nearby. A card naming a family code word, a medical detail or a private struggle is marked `visibility: private` and left out of fridge and lock-screen outputs.

No safety rule may require a phone number. Where a card touches a hard topic, safety rules point to people: a parent, a coach, someone the recipient trusts. Help lines appear only when the user adds them (`help_resources: custom`).

### Intake policies

`knowledge/rules/policies.yaml` defines each policy key, its allowed values, its default, and which age bands may use each value. The deck stores the user's choices; rules switch on or off with `when`.

| Key | Values | Default |
|---|---|---|
| `voice` | sender relationship and pronouns (parents "we/us", one person "I/me", coach, self-talk) | asked at intake |
| `substances` | `omit` \| `safety_only` \| `abstain` \| `harm_reduction` | `omit` |
| `sex_relationships` | `omit` \| `safety_only` \| `harm_reduction` | `omit` |
| `faith` | `neutral` \| `include` (references the user supplies) | `neutral` |
| `personal_details` | confirmed by the user only, never inferred | none |
| `register` | humor level, slang tolerance | asked at intake |
| `help_resources` | `none` \| `custom` | `none` |

**Policy ladder by age band**

| Band | substances | sex_relationships |
|---|---|---|
| grade-school | `omit`, `safety_only` | `omit` (body safety and boundaries are covered by the safety topics) |
| middle-school | `omit`, `safety_only` | `omit`, `safety_only` (consent, online safety) |
| high-school | `omit`, `safety_only`, `abstain` ("call me, no questions asked" counts as `safety_only`) | `omit`, `safety_only` |
| college | all four | all three |
| adult | all four | all three |
| a user-added band | `omit` only, until the user sets its ladder | `omit` only |

Every sensitive-topic policy defaults to `omit`. The user opts in topic by topic.

### Help resources

Help resources the user adds are stored as grade-D findings with URL checks. Any phone number or URL on a card must exactly match a verified resource, and lint enforces it. v1 ships US resource checks only; for other countries the user supplies local resources and they go through the same verification. The weekly CI re-check matters here, because help lines do change.

### Reading level

Readability formulas are built for passages much longer than a card, so on a 10-word line they're noisy. Lint checks each card word by word (syllables per word, words outside the band's familiarity list) and runs Flesch-Kincaid only as a deck-level warning. The familiarity list comes from a permissively licensed source chosen at build time, with its license file shipped alongside.

### Proposal and approval

1. After research, `cards-research` proposes rules.
2. `validate_rules.py` checks schema, citation status, the evidence floor and override legality.
3. The user reviews proposals in rounds. Each shows the rule text, the `why`, citations as author-year with a link, and the bad and good examples. The user approves, edits or rejects each.
4. Approved rules go to the overlay. `promote.py` moves them into the shipped files and renumbers their IDs.

### Compile

`compile_rules.py` runs once per deck (and again whenever its inputs change) and writes `effective-rules.yaml` into the deck. It:
1. merges the applicable scopes, shipped plus overlay
2. applies the deck's policies and age band through `when`, then `overrides`
3. maps context rules to their categories
4. records each rule's provenance: scope, file and plugin version

Same deck plus same plugin version produces byte-identical output.

### IDs and rule text

- Shipped rule IDs are `R-<scope>-NNN`; overlay rules are `R-<scope>-LNNN`. `<scope>` is the scope's last path segment (`R-athletics-002`).
- Every rule carries a `why` sentence written for the user, shown whenever review flags a card.
- `validate_rules.py` runs in CI and before every compile.

---

## 5. Skills

### Shared by every skill

- **Environment check first.** Every skill starts by running `scripts/env_probe.py`, which reports whether files can be written in place, whether Crossref and PubMed are reachable, and whether Chromium can launch. Skills act on that report, never on a guess about which platform they're on.
- **Bundle first, bundle last on claude.ai.** Each run checks for an attached bundle first and emits an updated bundle last, so a conversation that dies mid-flow loses at most one stage.
- **One approval protocol.** `cards-core/ROUNDS.md` defines it once, including the crisis stop. Each round shows a batch, numbered questions and stated assumptions. Only "approved" or an explicit equivalent counts as approval; when unsure, ask. v1 is strict only (relaxed approval is FF-4).
- **Short skill files.** Each `SKILL.md` points to `ROUNDS.md`, `RESEARCH-GUIDE.md` and the scripts rather than restating them.
- **Prerequisites.** Any skill can be called directly with a bundle attached. It checks that the deck's status satisfies its prerequisites and, if not, says which skill to run first.
- **Frontmatter.** `SKILL.md` files use only standard frontmatter fields (`name`, `description`, and where needed `license`), so one file works in claude.ai and Claude Code. The probe (P2) confirms the upload accepts them.

### Trigger descriptions

| Skill | Description |
|---|---|
| `cards-core` | Shared knowledge, schemas, templates and scripts for the Tuckcard skills. Not for direct use; other Tuckcard skills load files from it. |
| `cards-new` | Start a motivational or encouragement card deck for a person or group: runs the intake interview and creates the deck file. Use when someone wants to make motivational, encouragement, habit or pep-talk cards, or attaches a Tuckcard bundle without naming a step. |
| `cards-research` | Research a Tuckcard age band or context (for example high school, athletics, managing a team): plans questions, finds and verifies sources, records gaps, and proposes card-writing rules. Use when a deck's coverage check reports a missing scope, or the user asks to research a new audience or topic. |
| `cards-draft` | Write a Tuckcard deck's copy in approval rounds, one category at a time, linting each batch against the deck's rules. Use after intake and any research are done, or to add or rewrite cards. |
| `cards-review` | Check a Tuckcard deck against its rules: lint, then a judgment pass for rule fit and conflicts. Use before rendering, after hand-editing a deck file, or when asked to review cards. |
| `cards-render` | Render an approved Tuckcard deck to a print sheet, PDF, lock screens and single-card PNGs, with a fit report. Use when the user wants files to print or use as wallpapers. |
| `cards-restyle` | Change a Tuckcard deck's layout, style preset, theme, colors, fonts or spacing, previewing one card before re-rendering. Use for a different look, a black-and-white or dark version, or a more professional style. |

### Steps

**`cards-new`**
1. Run the environment check. If a bundle is attached and the user didn't name a step, read the deck's status and hand off to the right skill.
2. Run intake in four rounds (`ROUNDS.md`):
   - recipient, age band, relationship and voice
   - purpose, categories and their context mapping, count and numbering
   - policies; personal details the user confirms; culture, faith and language notes the user supplies
   - layout (default `stacked`), style preset, outputs, page size, visibility concerns and theme. Suggest `professional` only when the age band is `adult`.
3. Ask only for details the cards will use. Warn, without blocking, when a combination would identify a child to strangers on a lock screen.
4. Write `deck.yaml` and validate it against the schema.
5. Check coverage: is each scope the deck uses `active`, a `stub`, or backed only by provisional findings?
6. Hand off to `cards-research` if any scope isn't active; otherwise to `cards-draft`.

**`cards-research`** (follows `RESEARCH-GUIDE.md`)
1. Show the question plan and get it approved.
2. Search, or on paid claude.ai offer the Path B Research prompt.
3. Write and verify findings; record gaps.
4. Show the summary table.
5. Propose rules, validate them, and run approval rounds.
6. Hand back to the calling skill.

**`cards-draft`**
1. Compile the rules if the snapshot is out of date.
2. Take the next category. Read the matching age-band example for style only; never reuse an example line verbatim (lint checks).
3. Draft the batch, one category per round, about 10 cards at most: title, lines with marks and notes, and `basis` for each card, within the format rules for the deck's layout.
4. Lint the batch. Fix errors before showing it, then show it with remaining warnings and each rule's `why`.
5. Run the round. On approval, record `approved_hash` and `linted_hash`; continue with the next category.
6. When every category is approved, set status `drafted` and hand off to `cards-review`.

**`cards-review`**
1. Lint the whole deck: format and fit for the layout, reading level, help-resource matching, visibility, repetition.
2. Judgment pass: judge-type rules, whether each card's `basis` still holds, undeclared conflicts, context rules that read as age-specific without a gate, consistency with the voice.
3. Write `deck/review.md`, listing each flag with severity, rule ID and `why`, plus deck-level notes such as category balance.
4. The user picks which fixes to make. Fixes go back through `cards-draft` and get re-approved; review never edits cards.
5. When the deck comes back clean, set status `reviewed` and hand off to `cards-render`.

**`cards-render`**
1. Pick the rendering path from the environment check.
2. Check approval hashes and warn about cards edited by hand since approval.
3. Leave `visibility: private` cards out of fridge and lock-screen outputs.
4. Render. Write the fit report. Build a contact sheet of every page and look at it before delivering.
5. Deliver the files, and on claude.ai the bundle too. Remind the user to keep the bundle private.

**`cards-restyle`**
1. Ask what to change: layout, style preset, theme tokens, category colors, fonts, or layout tokens (corner radius, spacing, mark stroke weight, mark wobble).
2. Check text-to-background contrast against WCAG ratios, and check that category colors stay distinguishable in grayscale, so a B&W print doesn't turn every accent into the same mid-gray.
3. Preview one card in each affected combination and get it approved. A layout switch reruns the fit check for the whole deck; cards that no longer fit go back to `cards-draft`.
4. Save the style into the deck and hand off to `cards-render`.

### What changes by platform

| | claude.ai chat | Claude Code |
|---|---|---|
| Start | Look for an attached bundle | Find the deck in `local/decks/` |
| Writes | Working directory, packaged into the bundle | In place, in `local/` |
| Citation checks | Script if the network allows, otherwise fetch | Script |
| Rendering | HTML print sheet + Pillow | Playwright + HTML print sheet |
| Review's judgment pass | Same conversation context | A fresh sub-agent that hasn't seen the drafting |
| End | Files plus an updated bundle | Files written in place |

---

## 6. Data model

### Schema inventory

JSON Schema 2020-12 files in `cards-core/schemas/`. YAML files are converted to JSON for validation. Scripts write YAML with ruamel.yaml so comments, key order and formatting in hand-edited files survive.

| Schema | Validates | Defined in |
|---|---|---|
| `deck` | `deck.yaml`, including its cards | this section |
| `card` | each entry in the deck's `cards` list | this section |
| `finding` | finding frontmatter | Section 3 |
| `rule_file` | `knowledge/rules/<scope>.yaml` | Section 4 |
| `policies` | `knowledge/rules/policies.yaml` | Section 4 |
| `gap` | gap entries | Section 3 |
| `index` | `knowledge/findings/index.yaml` | Section 3 |
| `bundle_manifest` | `manifest.json` in a bundle | this section |
| `layout` | `templates/<layout>/layout.json` | Section 7 |
| `marks` | `marks.json` | Section 7 |
| `theme`, `preset` | theme and preset token files | Sections 7–8 |
| `fit_report` | render reports | Section 7 |

### Deck file

Fictional example:

```yaml
schema_version: 1
plugin_version: 0.1.0
id: sam-hs-2027
title: Sam's Week-by-Week Deck
status: drafting        # intake | researching | drafting | drafted | reviewed | rendered
created: 2026-11-10
recipient:
  kind: person          # person | group
  pill: High School     # text on the card's age label
  age_band: high-school
  description: >        # user-supplied, private
    Junior, plays soccer, nervous about junior-year course load.
  culture_notes: null   # faith, traditions, language; user-supplied only
sender:
  voice: parents
  pronouns: we/us
  signoff: Love, Mom & Dad
policies:
  substances: safety_only
  sex_relationships: safety_only
  faith: neutral
  register: {humor: light, slang: some}
  help_resources: none
personal_details:       # confirmed facts only
  - {id: P-01, text: "plays soccer, midfield", confirmed: true}
categories:
  - {key: growth, label: Growth, color: orange, contexts: [personal-growth]}
  - {key: game-day, label: Game Day, color: teal, contexts: [athletics]}
numbering:
  mode: weekly          # weekly (weeks 1-52 plus bonus 53) | sequential
  count: 53
  week_rule: contains_jan_1   # contains_jan_1 | iso8601
  week_start: sunday          # sunday | monday
outputs: [print_sheet, pdf, phone, tablet, png]
page_size: letter       # letter | a4
style:
  layout: stacked       # stacked | notebook | index
  preset: casual        # casual | professional
  theme: color          # per-output defaults apply when unset (Section 7)
  tokens: {}            # overrides from cards-restyle
rules_snapshot:
  file: effective-rules.yaml
  compiled_at: 2026-11-10T15:50:00Z
  plugin_version: 0.1.0
  sha256: "..."
cards: [ ... ]
```

Weekly decks store no year. The render step takes a year (default: the upcoming one) and uses it only for the week-of dates on the index pages, so a weekly deck works every year.

### Card

```yaml
- n: 42
  category: game-day
  title: Reset
  lines:
    - text: "Missed shot? Breathe, then get back on defense."
      mark: {target: "Breathe", occurrence: 1}   # style optional; the layout decides how it's drawn
      note: "your reset"
    - text: "Next play is the only play."
      mark: null
      note: null
  basis: [R-athletics-002, R-core-003]
  visibility: public      # public | private
  approval:
    approved_hash: "sha256:..."
    approved_by: round    # round | hand-edit
    approved_round: 7
    linted_hash: "sha256:..."
```

**Marks.** A mark stores the phrase it emphasizes (`target`, a substring of its line) and which occurrence (`occurrence`, default 1). The layout decides how marks are drawn: a hand-drawn swash in `stacked`, a highlighter in `notebook`, an underline in `index`. An optional `style` field lets a power user override the drawing for one mark with any style defined in `marks.json`. There is no per-card mark vocabulary and no mark-rotation lint.

**Notes.** A note belongs to its line. `notebook` and `index` number notes in line order; `stacked` places each note under its line. The card data doesn't change between layouts.

**Validation**
- A mark must have a note.
- A mark's `target` must occur in its line at least `occurrence` times.
- `basis` must name rules present in the deck's compiled rules snapshot.

**Approval hash** covers the title, the lines (text, mark target, occurrence and style, note), the category and the visibility. Number and `basis` stay out, so reordering weeks or recomputing `basis` doesn't trigger re-approval. Category is in because moving a card changes which rules apply. Visibility is in because making a private card public is a safety decision.

**Group decks.** For `recipient.kind: group`, `personal_details` accepts only group-level details ("U14 team, first season together"). The schema rejects entries about an individual member.

### Bundle

```
sam-hs-2027.tuckcard.zip
├── manifest.json
├── deck/deck.yaml
├── deck/effective-rules.yaml
├── deck/review.md
├── knowledge/findings/L-*.md
├── knowledge/rules/<scope>.yaml      # overlay rules only
├── knowledge/gaps/*.md
├── themes/  presets/                 # overlay styles, if any
└── renders/                          # optional
```

```json
{
  "schema_version": 1,
  "plugin_version": "0.1.0",
  "created": "2026-11-10T16:05:00Z",
  "platform": "claude.ai",
  "deck_id": "sam-hs-2027",
  "deck_status": "drafting",
  "contains_personal_details": true,
  "overlay": {"findings": 3, "rules": 2, "gaps": 1, "themes": 0, "presets": 0},
  "files": [{"path": "deck/deck.yaml", "sha256": "..."}]
}
```

If a file doesn't match its manifest hash, it's reported as a hand edit and never blocks. Example decks ship as plain folders inside `cards-core/examples/`, not as bundles.

### IDs

| Object | Format |
|---|---|
| Finding | `F-0001` shipped, `L-0001` overlay |
| Rule | `R-<scope>-001` shipped, `R-<scope>-L001` overlay |
| Gap | `G-<scope>-01` |
| Personal detail | `P-01` |
| Card | `n` (week number or sequence number) |

### Versioning

`schema_version` is an integer. `migrate.py` upgrades decks forward only. A deck with a newer schema than the installed plugin is refused with a message to update the plugin. Each deck stores its compiled rules and the plugin and schema versions, so an old deck re-lints against the rules it was written under unless the user chooses to upgrade.

---

## 7. Render pipeline

### Layouts

Three layouts ship. All are original designs; the prototypes in `reference/layouts/` are the visual source.

| Layout | Anatomy | Marks | Notes |
|---|---|---|---|
| `stacked` (default) | Category and age label top left; large watermark number top right; heavy sans title; left-aligned serif lines | Hand-drawn swash under the target | Under its line, indented, introduced by ↳, in an informal hand |
| `notebook` | Thin margin rule down the left; category and age label, number top right; serif title with the key word highlighted; left-aligned serif lines | Highlighter behind the target, with a numbered badge | Numbered, in one right-hand margin column, in a handwriting face |
| `index` | Colored header band holding category, age label, number and title; plain statement below | Bold target with an underline and a numbered badge | Numbered "Try this" list at the bottom |

Each layout lives in `templates/<layout>/` as `card.html`, `card.css` and `layout.json`.

### Template contract

- The HTML template is the reference design. Every visual value comes from CSS variables fed by the theme and preset: colors, fonts, corner radius, spacing, mark stroke weight, mark wobble.
- Each template exposes `render(card, deckStyle, format)` and writes its fit data to `window.__report` for Playwright.
- `layout.json` defines the card's regions in inches, the default font sizes, the shrink step sizes and the font floors, so both renderers share geometry. A power user can change them and the parity check picks up the change.
- The card is 5 × 5 in (480 × 480 CSS px at 96 px/in).

### Marks

`marks.json` defines each mark style (swash, highlight, underline, plus any added later) and the numbered badge as small parametric shapes sized to the target phrase's bounding box. Hand-drawn styles get a slight wobble from a small seeded random-number generator keyed to the card number and line index, implemented identically in JavaScript and Python, so a card renders the same every time in both renderers. `mark.wobble` is a token; `0` gives clean geometric marks.

### Auto-fit

One algorithm, implemented in both renderers, per layout:
1. Wrap words greedily with no hyphenation, at the layout's fixed widths.
2. Shrink the title, then the lines, then the notes, in the layout's fixed steps down to its floors.
3. If a card still overflows at the floors, it fails and goes back to `cards-draft`.

Layouts hold different amounts of text: `notebook` is the tightest because of its notes column; `stacked` holds the most. The deck's layout is chosen at intake, before drafting, so every card is fit-checked against it from the start. Switching layouts later reruns the fit check for the whole deck.

### Output paths

| Output | Claude Code (Playwright) | claude.ai (no Chromium) |
|---|---|---|
| HTML print sheet | Yes | Yes; the vector print path |
| Print PDF | Vector, fonts embedded | Pillow, raster at 300 dpi |
| Phone and tablet lock screens | Screenshot | Pillow |
| Single-card PNG (1500 × 1500) | Screenshot | Pillow |

On claude.ai the end-of-run message explains in one line that the PDF is a raster and that printing the HTML sheet from a browser gives vector output.

### HTML print sheet

One self-contained file: cards embedded as JSON, fonts embedded as base64, no network calls, so it works offline. Its `@page` CSS sets the page size and draws the cut lines. The sheet tells the user to print at 100% / Actual size so cards come out exactly 5 inches.

### Formats

- **Print:** 5 × 5 in cards, two per page in sequence (cards 1–2 on page 1, 3–4 on page 2; about 27 pages for 53 cards), on Letter or A4, each card with a thin cut line. Index pages follow, listing number, week-of date (weekly decks only), category and title.
- **Phone:** 1440 × 3200, the card in a centered band clear of the clock at the top and the shortcuts at the bottom, so it survives the crop on current Galaxy, Pixel and iPhone screens.
- **Tablet:** 2360 × 2360.
- **Single card:** 1500 × 1500 PNG.
- **Visibility:** `visibility: private` cards are left out of fridge and lock-screen outputs; the fit report lists them.
- **File names:** `<deck-id>-<format>-<n>.png`, zipped per format.

### Week numbering

`numbering.week_rule: contains_jan_1` (default) makes week 1 the week containing January 1; `iso8601` uses ISO weeks. `numbering.week_start` defaults to `sunday`.

### Themes

`themes/<name>.json` holds background, ink, muted color, category palette and mark color rules. Themes are independent of layout and preset.

| Theme | Use | Notes |
|---|---|---|
| `color` | Print and single PNGs (default) | White background, so trims leave no sliver and no background ink is used |
| `mono` | Print (default alongside `color`) | Everything in solid black, so laser printers don't dither accents into gray dots |
| `dark` | Lock screens (default) | Warm charcoal background with brightened accents |

### Fit report

`fit-report.json` plus a short summary for the user, listing each card's final font sizes, whether it was shrunk or failed, cards edited by hand since approval, and cards left out for visibility. Before delivering, `cards-render` builds a contact sheet of every page and looks at it, on both platforms.

### Parity check

`tools/parity/` (repo only) renders a reference set through Playwright and Pillow for every combination of layout (3), style preset (2) and theme (3), 18 combinations, plus each layout token at its default and extreme values (including `mark.wobble: 0`).
- Line breaks and final font sizes must match exactly.
- Pixels may differ within a threshold, the "close but not pixel for pixel" margin.

---

## 8. Customization and extension

### Principle

Everything is customizable by editing files. The skills help, but no customization requires changing a skill.

### Three levels

| Level | Where | Survives plugin updates | Typical use |
|---|---|---|---|
| Deck | `deck.yaml` `style` block, via `cards-restyle` or a hand edit | Yes | One deck's layout, preset, colors, fonts |
| Overlay | `local/` in Claude Code; the bundle on claude.ai | Yes | Your own themes, presets, findings, rules |
| Fork | The shipped files in `cards-core/` | No; you merge updates yourself | Changing defaults for everyone using your fork |

### Style presets

A preset sets typography and shape; a theme sets color; a layout sets structure. All three are independent.

| | `casual` (default) | `professional` |
|---|---|---|
| `stacked` fonts | Archivo Black titles, Source Serif 4 lines, Shantell Sans notes | Liberation Sans titles, Liberation Serif lines, Liberation Sans notes |
| `notebook` fonts | Fraunces titles, Literata lines, Caveat notes | Liberation Serif titles and lines, Liberation Sans notes |
| `index` fonts | Atkinson Hyperlegible throughout | Liberation Sans titles, Liberation Serif body |
| Mark wobble | On | `0` |
| Corners | Rounded | Square or minimal radius |
| Arrows and swashes | Hand-drawn | Straight |

A preset can remap mark styles at render time (for example, a swash drawn as a straight underline in `professional`). The deck's data doesn't change, so approval hashes stay valid when the user switches presets. `cards-new` suggests `professional` only when the age band is `adult`.

### Fonts

- **Shipped:** Archivo Black, Source Serif 4, Shantell Sans, Fraunces, Literata, Caveat, Atkinson Hyperlegible, Liberation Serif and Liberation Sans. All are SIL OFL 1.1, each with its license file. Liberation Serif is metric-compatible with Times New Roman, which can't be redistributed.
- **User-supplied:** must carry a license that allows embedding. `cards-restyle` asks about the license before using one.
- **Fonts a user owns:** in Claude Code, a theme can point to a local font file. On claude.ai the file must be attached to the conversation, because Pillow can't see system fonts. Embedding rights are the user's responsibility.

### Extension recipes

One page each in `docs/extending/`:
1. **New theme:** copy a theme file, edit tokens, preview with `cards-restyle`, run the parity check in Claude Code.
2. **New preset:** same steps with a preset file.
3. **New context:** copy `rules/context/_TEMPLATE.yaml` and run `cards-research` on it. Keep its rules age-neutral.
4. **New age band:** copy the band template, add the band to `policies.yaml`, run `cards-research`. Until its policy ladder is set, a new band allows only `omit` for every sensitive topic.
5. **New category:** add it to the deck's `categories` list with a context mapping and a color.
6. **New mark style:** add a shape definition to `marks.json`. Both renderers interpret it; no code changes.
7. **New layout:** fork-level. Add `templates/<name>/` and implement it in the Pillow renderer too; it isn't supported until the parity check passes for it.

### Hand-edit guide

`docs/editing-by-hand.md`:
- **Safe to edit:** decks, themes, presets, layout files, overlay findings, overlay rules.
- **Generated, don't edit:** `index.yaml`, `effective-rules.yaml`, fit reports, bundle manifests, `THIRD_PARTY.md`. Each carries a header saying so.
- **After any edit:** `python scripts/validate.py <path>` checks the file against its schema.

---

## 9. Privacy, ethics, licensing

### Personal data

- **Personal:** everything under `recipient`, `personal_details` and `culture_notes`; all card text; every bundle.
- **Not personal:** findings and rules describe populations and never contain deck details.

### Privacy defaults

- `.gitignore` ignores `local/decks/`, `*.tuckcard.zip`, `renders/` and `out/`.
- CI fails if a `deck.yaml` outside `examples/`, or any bundle, is committed. Forks inherit the check; a fork owner can turn it off only by editing the workflow.
- Scripts send only identifiers (DOIs, PMIDs, URLs) to Crossref, PubMed and allowlisted sites. Deck content never leaves the machine or the sandbox through a script.
- The README says plainly that whatever a user enters on claude.ai is part of their Claude conversation and governed by their account's settings.
- Cards marked `visibility: private` stay off fridge and lock-screen outputs.

### Data minimization

`cards-new` asks only for details the cards will use, and warns without blocking when a combination would identify a child to strangers on a lock screen (for example full name plus school plus team).

### Example decks

Four examples ship: grade school (from the maintainer's age-8 deck), middle school (from the 13–14 deck), high school (new, written by running the finished plugin on a fictional recipient) and college (parents' "we/us" voice). Each is fully de-specified: every item below is replaced with a fictional equivalent of the same kind.
1. Names of people and pets, plus nicknames
2. Schools, teams, leagues and clubs
3. Places: cities, venues, landmarks
4. Dates tied to real events
5. Family structure details
6. Sport, position and level combinations
7. College majors and programs, vehicles, living situations
8. Distinctive hobbies, achievements and inside jokes
9. Code words and exit phrases
10. Faith and cultural specifics
11. Health details

Checking: a script scans the examples against a private terms list kept outside the repo, and the maintainer reads every example. No mapping from real to fictional details is stored anywhere. Each example carries `example: true` and a README listing the lint fixes applied. Example copy is also checked against the visible titles of the commercial deck that inspired the original personal decks, from a private list, and any echo is retitled.

### Sensitive topics and safety

- Every sensitive-topic policy defaults to `omit`; the user opts in within the age band's ladder.
- Help lines are off by default for every age band: none on cards and none in an index footer, unless the user adds them (`help_resources: custom`).
- **Crisis stop:** if the user describes someone at immediate risk during intake or drafting, the skill pauses card-making, gives crisis resources in the conversation, and says plainly that cards are no substitute for that help. This is Claude speaking to the adult making the deck, not deck content. It lives in `ROUNDS.md`, so every skill that runs rounds inherits it.
- Cards can't be used to guilt, threaten or control the recipient (safety topic 7).
- No efficacy claims: nothing in the README, index pages or skill output says a deck is proven to work.

### Intellectual property

- The card designs are original. The maintainer's personal decks were modeled on a commercial deck's look; a side-by-side comparison found six of seven visual signatures matching, so that look is retired entirely. The renderer is rebuilt from this spec and the original prototypes in `reference/layouts/`, not ported from the earlier code.
- The repo contains no third-party card images, screenshots, copy or code, and the README and docs don't mention the commercial product.
- Findings are paraphrased, with at most one short anchor excerpt per finding, and the README notes that cited works belong to their authors.
- Crossref metadata is free to reuse; Crossref asks for a citation when Retraction Watch data is used in published work. The README credits both.

### License inventory

| Item | License | File |
|---|---|---|
| Code, skills, docs, findings, rules, examples, layout prototypes | MIT | `LICENSE` |
| Archivo Black, Source Serif 4, Shantell Sans, Fraunces, Literata, Caveat, Atkinson Hyperlegible, Liberation Serif, Liberation Sans | SIL OFL 1.1 | `fonts/<family>/OFL.txt` |
| Word-familiarity list | Chosen at build time; must be permissive | its own license file |
| Python and Node dependencies | Checked at build time; must be permissive | `THIRD_PARTY.md` (generated; the build fails on copyleft or unknown licenses) |

### README disclaimers

1. These cards aren't therapy, counseling or medical advice. In a crisis, call or text 988 in the US, or your local emergency number.
2. The cards are research-informed; no deck is claimed to improve outcomes.
3. Bundles contain personal details, so keep them private. The example decks are fictional.
4. When writing for minors, the adult making the deck reviews every word.
5. This project isn't affiliated with or endorsed by Anthropic.

---

## 10. Seed kit and bootstrap

### What was written by hand vs. what Claude Code generates

Rule of thumb: hand-write what encodes judgment; generate what's mechanical.

| Hand-written (in the seed kit) | Generated by Claude Code from this spec |
|---|---|
| `SPEC.md` (this file) | JSON Schemas |
| `CLAUDE.md`, `BOOTSTRAP.md` | All scripts |
| `ROUNDS.md`, `RESEARCH-GUIDE.md` | Playwright, print-sheet and Pillow renderers |
| Seven `SKILL.md` drafts | `templates/*/` from the prototypes, `layout.json`, `marks.json`, themes, presets |
| `policies.yaml`, `sources-allowlist.yaml` (starter) | Tests, fixtures, CI workflows |
| Templates: finding, rule file, context, age band, gap entry; rule-file stubs for every scope | Marketplace and plugin manifests |
| `reference/layouts/` prototypes | `THIRD_PARTY.md`, findings index |
| `tools/probe-plugin/` | README (M8) |

### Pre-bootstrap tasks

1. **P1: name checks.** The name is Tuckcard. Before publishing, finish what couldn't be checked during naming: USPTO trademark search, `.com` and `.dev` domains, GitHub handle, social handles. If anything blocks the name, rename before M0.
2. **P2: platform probe.** Upload `tools/probe-plugin/` to a paid claude.ai account and run it. It has two skills so it can test whether one skill can read its sibling's files. It reports the Python version; whether Pillow, ruamel.yaml and jsonschema are installed; whether `pip install` works; whether Chromium launches; whether Crossref and PubMed are reachable; whether a skill can read its sibling's files; whether the frontmatter was accepted; and where skills are mounted. Record the results, with the date, in Appendix C. They settle assumption H (shared `cards-core` vs. copying it into each skill), F (frontmatter) and the claude.ai verification path. Any decision the probe overturns gets a decisions-log entry before bootstrap.
3. **P3: template comparison.** Done (2026-11-10). Result in Section 9 and Appendix B.
4. **P4: gather private assets.** Keep `private-legacy.zip` (approved copy of three decks, the PII terms list, the other deck's visible titles) outside the repo. M6 asks for its path.

### Build order

Milestones, with maintainer review gates marked ◆. Claude Code stops at each gate and waits for approval.

| # | Milestone | Done when |
|---|---|---|
| M0 | Skeleton: marketplace and plugin manifests, license files, `.gitignore`, CI skeleton, fonts downloaded from their sources with license files | `claude plugin validate` passes; installs from the repo in Claude Code |
| M1 ◆ | Schemas plus `validate.py` | Every schema validates its example and fixture files |
| M2 | Knowledge tooling: verify, index, validate rules, compile, promote | Fixtures behave: a fake DOI, a retracted DOI and a metadata mismatch land in quarantine; an evidence-floor violation and a safety override are rejected; compile is byte-identical on repeat runs |
| M3 ◆ | Render: three layouts from the prototypes, `layout.json`, `marks.json`, themes, presets, all three renderers, fit report, parity check | Parity passes for all 18 combinations; grayscale check passes; lock-screen safe band verified; no code or assets from the earlier personal renderer |
| M4 | Skills: the seven `SKILL.md` files finalized, plus `env_probe` and the bundle script | Each skill runs its steps on a fixture deck in Claude Code |
| M5 ◆ | Seed research: core, safety, four age bands, four contexts, by Path A or B, then promotion | CI green; every shipped finding active or contested; gap entries written |
| M6 ◆ | Examples: de-specify three decks from the private assets, lint, fix and document; retitle any echo of the other deck | Lint clean with remaining warnings documented; PII scan clean; maintainer has read every example |
| M7 ◆ | Acceptance: the high-school deck end to end | Passes on claude.ai and in Claude Code (tests below) |
| M8 | Docs and release: README, extending docs, hand-edit guide, issue template | v0.1.0 tagged |

### Acceptance tests

1. **Install:** the plugin installs from the repo marketplace in Claude Code and in claude.ai.
2. **Knowledge:** CI is green on all shipped findings and rules, and the weekly re-check is scheduled.
3. **Determinism:** the same deck and plugin version produce byte-identical compiled rules, and identical fit reports within each renderer.
4. **Enforcement:**
   - a card edited by hand gets flagged and still renders
   - private cards are left out of fridge and lock-screen outputs
   - a help-line number that doesn't match a verified resource fails lint
   - committing a dummy deck or bundle fails CI
5. **End to end on claude.ai:** in one conversation, the high-school deck goes through intake → research if needed → draft → review → render → bundle. In a new conversation, the bundle is attached, restyled to `notebook` + `professional` + `mono`, fit-checked and re-rendered.
6. **End to end in Claude Code:** the same flow, with output written to `local/decks/`.
7. **Render quality:** zero fit failures across all four examples in their own layouts, and parity passes.

---

## Appendix A: Fast follows

Deferred features, each with enough detail to build later without re-planning.

**FF-1: promotion as a GitHub Action.** A manually triggered workflow that takes an uploaded bundle as input and runs `promote.py`. It commits the promoted findings and rules to a `promote/<date>` branch for maintainer review; CI's invariant check runs on that branch before merge. No secrets beyond the default `GITHUB_TOKEN`.

**FF-2: Free-plan build target.** The build script also emits one standalone ZIP per skill, with `cards-core` copied into each, for upload under Customize > Skills. It reuses the copying fallback from assumption H. Extra work: the build step and a README section for Free-plan users.

**FF-3: dedicated conflict scan.** An explicit step (its own skill or a `cards-review` mode) at a fixed point: after compile, before drafting. Claude compares the compiled rules pairwise and writes results to `deck/conflicts.yaml`. It never edits the compiled rules. The user resolves each flagged conflict by approving an `overrides` entry, which goes into the overlay and takes effect on the next compile.

**FF-4 (possible): relaxed approval.** An intake setting allowing a whole drafting batch to be approved in one reply, with `strict` as the default. Reconsider after v1 feedback.

**FF-5: print together.** Takes two bundles and prints them interleaved, one card from each per page, restoring "page N = week N" for siblings. Both decks must use the same numbering mode, count and page size.

---

## Appendix B: Decisions log

Every assumption raised during planning, with its outcome. "Revised" means a later decision changed it; the section text above reflects the final state.

| ID | Decision | Outcome |
|---|---|---|
| A | The planning rounds produce this seed kit | Confirmed |
| B | Refactor the earlier personal renderer | Replaced: clean-room rebuild from this spec and the original prototypes (IP decision, 2026-11-10) |
| C | The original decks stay private | Revised: they stay private; de-specified derivatives ship as examples |
| D | Research uses web search plus verification, no paid databases; on claude.ai it needs web search on | Confirmed |
| E | Weekly numbering is optional; non-weekly decks are sequential | Confirmed |
| F | `SKILL.md` uses standard frontmatter only; test an upload | Confirmed; P2 verifies |
| G | Name is a placeholder | Resolved: Tuckcard |
| H | Shared knowledge lives in `cards-core`; if sibling skills can't read it on claude.ai, the build copies it into each skill | Open until P2 |
| I | Examples are linted against v1 rules; fixes listed in each example's README | Confirmed |
| J | HTML is the reference design; Playwright matches exactly; Pillow closely; a parity check keeps drift visible | Confirmed; parity now covers 18 combinations |
| K | The high-school example is written by running the plugin end to end, doubling as the acceptance test | Confirmed |
| L | The 13–14 deck becomes the middle-school example | Confirmed |
| M | Standard plugin layout | Confirmed |
| N | Deck files are YAML validated against JSON Schema | Confirmed |
| O | No orchestrator skill; each skill names the next | Confirmed |
| P | On claude.ai every skill ends its stage with an updated bundle | Confirmed |
| Q | Decks store compiled rules and versions; old decks re-lint against their own rules unless upgraded | Confirmed |
| R | `tools/` and `tests/` never ship in the plugin | Confirmed (also `reference/`, `docs/`) |
| S | `adult` band exists as a stub | Confirmed |
| T | Branding check before bootstrap | Revised: name chosen in a separate naming session; remaining checks in P1 |
| U | Findings paraphrased; one anchor excerpt each | Confirmed |
| V | Shipped `F-` vs. overlay `L-` IDs | Confirmed |
| W | Domain allowlist changes are a maintainer decision | Confirmed |
| X | 10–20 findings per seeded scope; claude.ai research runs cap at about 15 new findings | Confirmed |
| Y | `RESEARCH-GUIDE.md` is the single source for research procedure | Confirmed |
| Z | The question plan is approved before searching | Confirmed |
| AA | Rule ID formats | Confirmed |
| AB | Every rule has a user-facing `why` | Confirmed |
| AC | Help resources are grade-D findings with URL checks; on-card numbers must match; US-only in v1 | Confirmed; help lines off by default |
| AD | `validate_rules.py` in CI and before every compile | Confirmed |
| AE | Word-familiarity list from a permissive source | Confirmed |
| AF | Skills act on `env_probe.py`, never on a platform guess | Confirmed |
| AG | Bundle first and last on claude.ai | Confirmed |
| AH | `cards-review` never edits cards | Confirmed |
| AI | User fonts need an embedding license | Confirmed |
| AJ | Any skill can start from a bundle and checks prerequisites | Confirmed |
| AK | JSON Schema 2020-12 | Confirmed |
| AL | ruamel.yaml for all YAML writes | Confirmed |
| AM | Forward-only migrations; newer decks refused | Confirmed |
| AN | Bundle hash mismatch is reported as a hand edit, never blocks | Confirmed |
| AO | Bundle naming and the personal-details flag; examples ship as folders | Confirmed; extension is `.tuckcard.zip` |
| AP | Fonts | Revised: per-layout OFL set (Section 8); Libre Baskerville and Kalam dropped with the retired look |
| AQ | claude.ai PDF is a 300 dpi raster; vector comes from printing the HTML sheet | Confirmed |
| AR | Shrink steps and floors live in layout files | Confirmed; per layout |
| AS | Output file naming | Confirmed |
| AT | `cards-restyle` gains wobble as a layout token and switches presets | Confirmed; also switches layouts |
| AU | Custom themes and presets live in `local/` or travel in the bundle | Confirmed |
| AV | Parity covers every preset × theme | Revised: × layout too, 18 combinations |
| AW | The committed-deck CI check runs in forks | Confirmed |
| AX | Crisis stop lives in `ROUNDS.md` | Confirmed |
| AY | `THIRD_PARTY.md` generated; build fails on copyleft or unknown licenses | Confirmed |
| AZ | P2 runs on a paid account; overturned decisions get log entries before bootstrap | Confirmed |
| BA | `BOOTSTRAP.md` makes Claude Code follow this spec, stop at gates and raise conflicts as questions | Confirmed |
| BB | Either research path completes M5 once CI is green | Confirmed |
| BC | The seed kit is written in one pass after approval | Done |
| BD | Intake chooses the layout before drafting; switching later reruns fit | Confirmed |
| BE | Per-card mark types dropped; the layout draws marks; optional per-mark `style` | Confirmed |
| BF | Three layouts ship: `stacked` (default), `notebook`, `index` | Confirmed |
| BG | README keeps the 988 line in its disclaimer, since it addresses the adult installing the plugin | Default taken; maintainer can drop it |
| BH | The earlier look is retired after the P3 comparison (six of seven signatures matched a commercial deck) | Confirmed |

---

## Appendix C: Platform facts

Filled in after P2. Until then, every row is unknown and the design must not depend on any of them.

| Question | Result | Date | Settles |
|---|---|---|---|
| Python version in the claude.ai skill sandbox | unknown | | |
| Pillow, ruamel.yaml, jsonschema preinstalled? | unknown | | Script dependencies |
| `pip install` works? | unknown | | Script dependencies |
| Chromium launches? | unknown | | Rendering path on claude.ai |
| Crossref and PubMed reachable from code? | unknown | | Verification path (Section 3) |
| A skill can read a sibling skill's files? | unknown | | Assumption H |
| Standard frontmatter accepted on upload? | unknown | | Assumption F |
| Where skills are mounted | unknown | | Path resolution in scripts |
| Plugin install from "Add from a repository" works for this repo | unknown | | Acceptance test 1 |

### Claude Code / this Mac, 2026-11-11

These facts come from the person's operator on this machine, not from a claude.ai skill sandbox. Every claude.ai row above stays unknown.

- Python 3.9.6 on Darwin arm64.
- A skill can read its sibling skill's files: yes. This is a filesystem read, not a sandbox, so it says nothing about the claude.ai row.
- The skill folder and the current working directory are writable.
- Pillow, ruamel.yaml, PyYAML, jsonschema and Playwright are not importable.
- `pip install` into a temporary folder works.
- No Chromium is on PATH; launching it was not attempted.
- Crossref, PubMed, PyPI and Google Fonts are reachable.

The standard frontmatter row is self-referential on this machine: the harness reads the frontmatter it is given, so a local success settles nothing about what claude.ai accepts.

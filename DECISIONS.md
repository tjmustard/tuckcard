# Decisions

A numbered, append-only register of conscious deviations from `SPEC.md` or from the seed kit, with the reason for each. Entries are never renumbered, rewritten or removed. A later entry can supersede an earlier one, and the later entry says so. If a milestone makes no deviation, its section says so. No entry is invented.

## M0: skeleton

### D-001: Add `CHANGELOG.md` and `DECISIONS.md` to the repo root

**Deviation.** The directory tree in SPEC.md section 2 names neither file.

**Decision.** Both files start at M0, on the person's instruction of 2026-11-11 02:57Z (operator row `qitem-20261111025652-10637eacb5991aa7`).

**Why.** The person asked for a changelog that records what changed with evidence, and for a register that records conscious deviations and why. Keeping both at the repo root makes them visible to contributors.

### D-002: Keep the committed LICENSE copyright name over the seed kit's copy

**Deviation.** The committed `LICENSE` says "Thomas Mustard". The seed kit's copy says "TJ Mustard".

**Decision.** The committed file stays unchanged. The manifests use Thomas Mustard as author and marketplace owner, and the brief's "author per the repo" is read as that same name.

**Why.** The committed file is the repository's existing legal record, and the M0 brief directs keeping it. Deciding which name is canonical belongs to the person, not to this milestone. The question is reported to the lead.

### D-003: Font sources and versions

**Deviation.** None from the source list in SPEC.md sections 8 and 10 and the BOOTSTRAP M0 note, which name Google Fonts and liberationfonts/liberation-fonts. Two choices within that list are recorded here because they affect reproducibility.

**Decision.** The seven Google Fonts families are pinned to Google Fonts commit `5bb28733cec313b63fbd415b574b5ae35c8aa8b8`, downloaded from `https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/<family>/`. Liberation Serif and Liberation Sans come from liberation-fonts 2.1.5, from the binary tarball linked in that release's notes: `https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz`. Variable font files ship where the family publishes one: Source Serif 4, Shantell Sans, Fraunces, Literata and Caveat. Static files ship for Archivo Black, Atkinson Hyperlegible (Regular, Bold, Italic, BoldItalic) and Liberation (Regular, Bold, Italic, BoldItalic).

**Why.** A pinned commit makes the downloaded bytes reproducible and auditable. The liberation-fonts repository tree holds only `.sfd` sources, and the 2.1.5 release page carries no Assets entries; its binaries are attached as file links in the release notes. The ttf tarball linked there is the original project's own build. Shipping the files each family actually publishes avoids generating missing styles ourselves.

### D-004: `weekly-recheck.yml` reports that it has nothing to check until M5

**Deviation.** SPEC.md section 3, invariant 1 says CI runs the citation existence and retraction check on every push and weekly. That check script (`verify_citations.py`) starts at M2, and shipped findings start at M5, so the weekly check cannot run at M0.

**Decision.** The scheduled workflow is created now. While no `F-*.md` files exist, it prints that there is nothing to re-check and that no check ran, then exits 0. If findings exist before the script does, it exits 1 rather than report a pass.

**Why.** The schedule should exist before findings arrive, and a placeholder that claims a pass would be a false signal. Exiting 1 on unexpected findings keeps the gap visible.

### D-005: Restore the seed kit's LICENSE copyright line

**Supersedes.** D-002.

**Deviation.** D-002 kept the committed "Thomas Mustard" copyright line. The lead, from the operator, directs restoring the seed kit's line instead.

**Decision.** `LICENSE` now reads "Copyright (c) 2026 TJ Mustard", the seed kit's line. The marketplace owner and the plugin author use the same name. The canonical name stays open for the person to set.

**Why.** The seed kit's line is the project's own record of authorship. The earlier committed line was not this milestone's to harmonize, and an agent should not settle a name the person has not. The line is restored pending the person's word.

## M1: schemas and validation

### D-006: Record the in-place rewrite of the DECISIONS preamble

**What changed.** On the M0 branch the preamble was edited in place to state that entries are append-only, never renumbered or rewritten, and that a later entry can supersede an earlier one and says so. No past entry was rewritten.

**Decision.** The preamble stands as written, and this entry records the edit so the register's history is explicit. QA observed the rewrite during M0 sign-off, and the lead directed this entry on the M1 branch.

**Why.** A register that records conscious changes should record a change to itself, even when the change only clarifies its own rules. Recording it here keeps both the fact and its reason auditable.

### D-007: The validation runtime floor is Python 3.10, not 3.9

**Deviation.** The M1 brief asks for Python 3.9 compatibility unless a pinned dependency needs newer, and for the higher floor to be recorded here.

**Decision.** `requirements.txt` pins `jsonschema==4.26.0`, `ruamel.yaml==0.19.1` and `pytest==9.2.0`. jsonschema 4.26.0 and pytest 9.2.0 both declare `Requires-Python >=3.10`; ruamel.yaml accepts 3.9. The floor for the test and validation path is therefore Python 3.10. The suite runs on Python 3.12.14 from `/opt/homebrew/bin/python3.12`, and CI uses `actions/setup-python` with 3.12. `validate.py` avoids syntax newer than 3.9, so only the pinned dependencies set the floor.

**Why.** Pinning the versions the suite was actually run with makes the result reproducible. Downgrading jsonschema or pytest to keep a 3.9 floor would trade a tested pin for an untested one, and the runtime that matters on claude.ai is a separate platform question (Appendix C).

### D-008: Provisional field names for the five token and report files

**Deviation.** SPEC.md names what `layout.json`, themes, presets, `marks.json` and fit reports carry, but not their field names. The schemas have to choose names now.

**Decision.** The first encoding is:

- `layout.json`: `regions` (each with `x_in`, `y_in`, `width_in`, `height_in`), `font_sizes`, `shrink_steps` and `font_floors`, each keyed by `title`, `lines` and `notes`. Extra top-level keys are allowed for template geometry not yet named.
- Themes: `name`, `background`, `ink`, `muted`, `category_palette` (category key to color) and `mark_colors` (style to color). Extra keys are allowed.
- Presets: `name`, `fonts` (layout to title/lines/notes family), `mark_wobble`, `corner_radius`, and optional `mark_styles` and `tokens`. Extra keys are allowed.
- `marks.json`: `styles` (name to `shape` plus free-form `params`) and `badge` (`shape: badge` plus `params`).
- Fit report: `deck_id`, `renderer`, `generated_at`, optional `layout`, `preset` and `theme`, a `cards` list (`n`, `font_sizes`, `shrunk`, `failed`, optional `hand_edited`), `hand_edits` and `private_omitted`.

**Why.** The milestone needs schemas a renderer can be held to. M3 builds the templates and both renderers, and is the first place these names meet real geometry and tokens. The schemas allow extra keys where user styles and future layout tokens are expected, so extending one does not need a schema change. M3 should confirm or amend the names, and any change gets its own entry here.

### D-009: Gap files are validated one parsed entry at a time

**Deviation.** SPEC.md stores gaps as Markdown headings and bullets, while the M1 inventory names a `gap` JSON Schema. There is no single JSON document in a gap file.

**Decision.** `validate.py` parses each `## G-<scope>-NN` section's five bullets into an object and validates that object against `gap.schema.json`, reporting a synthetic pointer such as `/entries/0/date`. The file's `# Gaps: <scope>` heading is not validated. The template's `G-<scope>-01` and `YYYY-MM-DD` placeholders pass, so the shipped template validates before it is filled in.

**Why.** A schema that never checks a real gap file is not worth having. Validating entries keeps the errors locatable and keeps the hand-written Markdown format the spec uses.

### D-010: Group decks mark each personal detail with `group_level: true`

**Deviation.** SPEC.md says a group deck's `personal_details` accepts only group-level details and the schema rejects entries about an individual member. JSON Schema cannot tell whether a sentence describes a person or a group, and the deck example shows no marker field.

**Decision.** Each personal detail item may carry `group_level: true`. When `recipient.kind` is `group`, the `allOf` in `deck.schema.json` rejects an item without the marker; `validate.py` only runs the schema. Person decks may omit the field.

**Why.** The rule is a safety rule and needs a signal the validator can enforce. The marker makes the author assert that the detail is group-level, and review still reads the text. The field is an addition to the deck shape and is reported to the lead as a question for the person.

### D-011: Keep the Python 3.9 floor by pinning older test dependencies

**Supersedes.** D-007.

**Deviation.** D-007 accepted a Python 3.10 floor because jsonschema 4.26.0 and pytest 9.2.0 require it. SPEC.md Appendix C leaves the claude.ai sandbox Python unknown, so the baseline must not depend on a 3.10 floor.

**Decision.** `requirements.txt` pins `jsonschema==4.25.1`, `ruamel.yaml==0.19.1` and `pytest==8.4.2`, all of which declare `Requires-Python >=3.9`. Under those pins the suite still passes on Python 3.12.14 (35 passed in 7.25s), all 26 kit rule, policy and template files still validate at exit 0, and `validate.py` plus every test file parses with `ast.parse(feature_version=(3, 9))`.

**Why.** The 3.9 floor removes an avoidable dependency on a runtime the target platform has not been measured to have. The two older pins keep the same APIs and the same tests; the cost is being two versions behind current, which a later milestone can revisit if a needed feature appears.

### D-012: Record the in-place correction to D-003's release description

**What changed.** In the M0 review fix at 0031e73, D-003's Why paragraph was edited in place. The second sentence changed from "its GitHub releases carry no uploaded assets, so the project's published binary tarball is the original project's own build" to "the 2.1.5 release page carries no Assets entries; its binaries are attached as file links in the release notes. The ttf tarball linked there is the original project's own build." The rest of D-003 is unchanged.

**Decision.** The corrected paragraph stands. This entry records the edit so the register's history stays explicit, following D-006. The M0 review checked the release API and page, found the original sentence inaccurate, and the lead directed the correction.

**Why.** The API's assets array is empty, but the release notes link two uploaded binaries. A register that is append-only should record a change to one of its own entries, as D-006 does for the preamble, even when the change only corrects a description.

### D-013: `approval` is required on every card written to `deck.yaml`

**Deviation.** SPEC.md section 6 shows an approval block on its card example but does not say whether a deck may hold a card that is not yet approved, and a deck can be in status `drafting`.

**Decision.** `deck.schema.json` and `card.schema.json` require `approval` on every card. A drafting round's proposed cards live in the conversation until the user approves the batch; only approved cards are written to `deck.yaml`. The approval hash is what the render step compares, so a card without one has nothing to compare.

**Why.** One card shape for both the standalone card and the deck avoids a second set of rules for unapproved cards, and the schema is then itself the check that no unapproved card reaches a render. `cards-draft` is where this is carried out next: it returns the batch in chat and writes only after approval.

### D-014: The manifest sample's `...` hashes are illustrative

**Deviation.** SPEC.md section 6 shows `"sha256": "..."` in the bundle manifest sample.

**Decision.** `bundle_manifest.schema.json` requires a real SHA-256 digest, with or without the `sha256:` prefix, and rejects a literal `...`. The sample's fields are all required: `schema_version`, `plugin_version`, `created`, `platform`, `deck_id`, `deck_status`, `contains_personal_details`, `overlay` and `files`.

**Why.** A manifest exists so a bundle's files can be compared with their recorded digests; a placeholder would defeat the comparison. The test fixture carries the sample's field set with a real digest, and another test proves a literal ellipsis fails.

### D-015: Finding status is enforced by the schema, not deferred to M2

**Deviation.** SPEC.md section 3 states status as a function of the verification block but does not say which check enforces it. The M1 review offered the schema now or `validate_rules.py` at M2.

**Decision.** `finding.schema.json` ties status to the verification block with `allOf`: `provisional` requires `exists: fetch` or `support: unchecked`; `active` and `contested` require `exists: script`, support at `abstract` or `full_text`, and retraction `none` or `correction`; a retraction of `concern` or `retracted` requires `quarantined`, which already requires `quarantine_reason`. M2's `validate_rules.py` still checks which statuses may back which rule strengths.

**Why.** The finding file is what a rule cites, and a hand edit gets no other check. Enforcing the record's own status in its schema closes the gap at the file rather than a milestone later, and leaves rule-level consequences where they belong. Whether replication is mixed or failed, or a related finding points the opposite way, stays a research judgment: the schema enforces the active base that `contested` rests on, not the direction of another file.

### D-016: The manifest repeats the deck's id pattern and status set

**Deviation.** None from SPEC.md, which gives no separate rule for the manifest's `deck_id` and `deck_status`.

**Decision.** `bundle_manifest.schema.json` repeats the deck's `id` pattern and its six-value `deck_status` enum rather than `$ref`-ing `deck.schema.json`, because those two fields sit in a manifest that is otherwise independent of the deck file. The duplication is provisional: M3 or M4 must revisit it when the deck status set settles, and either point both at one shared definition or record why they differ.

**Why.** A manifest is opened without its deck, so it carries the values it needs, but two copies drift. Recording the repetition now keeps it a choice rather than an accident. The M1 review raised it as a non-blocking finding; no code changed this round.

### D-017: The D-010 and D-012 wording corrections stay visible

**What changed.** At 3d4dd62, on the lead's direction, D-010 and D-012 were corrected in place. D-010's original sentence was "When `recipient.kind` is `group`, every item must carry it; `validate.py` then rejects an item without the marker." It became "When `recipient.kind` is `group`, the `allOf` in `deck.schema.json` rejects an item without the marker; `validate.py` only runs the schema." D-012's original text said D-003's sentence "its GitHub releases carry no uploaded assets" became "the 2.1.5 release page carries no Assets entries; its binaries are attached as file links in the release notes", followed by "No other part of D-003 changed." It now quotes the whole second sentence, including the move of "so the project's published binary tarball is the original project's own build" into "The ttf tarball linked there is the original project's own build", and closes "The rest of D-003 is unchanged."

**Decision.** The corrected entries stand. This entry records what they said before, so the wrong versions stay readable. The convention applies from here: a future correction to a register entry gets its own entry, as D-006 and D-012 did for D-003, rather than a silent in-place edit. The two corrections in D-010 and D-012 were made under this round's explicit direction and are recorded here instead of being undone.

**Why.** An append-only register that allows quiet edits to its own entries is not append-only. Keeping the earlier wording visible lets a reader see what changed and why, and the convention gives the next correction an obvious form.

## M2: knowledge tooling

### D-018: The LICENSE holder is TJ Mustard

**Deviation.** None from SPEC.md. This closes the question D-005 left open.

**Decision.** On 2026-11-11 the person confirmed the LICENSE holder is `TJ Mustard`, the seed kit's line already committed at 189d3a3. `LICENSE` stays unchanged. The marketplace owner and plugin author use the same name, and `Thomas Mustard` is not used anywhere.

**Why.** D-005 restored the seed kit's line pending the person's word. The M1 gate answer supplies that word, so this entry records the confirmation without editing D-005 or the legal file.

### D-019: Finding metadata expectations are optional source fields

**Deviation.** SPEC.md section 3 says `verify_citations.py` "compares title, year and first author against the finding" and that a guidance document's "page title matches", but the finding frontmatter in the section 3 example, `knowledge/findings/_TEMPLATE.md` and `finding.schema.json` stores only `citation`, `doi`, `pmid` and `url`. There is no expected title, year or first author to compare a source record with, and no expected page title for a guidance URL.

**Decision.** `source.title`, `source.year` (a four-digit integer) and `source.first_author` (a family name) are optional properties in `finding.schema.json` and placeholders in `_TEMPLATE.md`. `verify_citations.py` compares only the fields present, records exactly those keys in `verification.metadata_match` (empty when none is present), and quarantines a mismatch with a reason naming the field, the expected value and the value found. Title comparison ignores whitespace and case; first author is trimmed and case-folded; year is exact. For a guidance URL, `source.title` is the expected page title; when it is absent the script checks resolution and the allowlist only and prints that the title comparison was skipped. The SPEC.md example stays unchanged and remains valid, because the fields are optional.

**Provisional.** The shape is provisional until M5 writes real findings. If a real source record shows the fields are the wrong shape, M5 records the change in a new entry.

**Why.** A comparison needs a stored expectation. Optional fields let the existing example, template and shipped files stay valid while making the check meaningful when a researcher records what the source says.

### D-020: Shapes the knowledge scripts choose where the SPEC leaves them open

**Deviation.** None from a stated rule, but SPEC.md does not name the `effective-rules.yaml` field shape, the rank used to test an override, or how promotion treats the overlay copy.

**Decision.**

- `effective-rules.yaml` carries `deck_id`, `age_band`, `plugin_version`, `scopes` and `rules`. Each rule keeps its source fields, gains `categories` when it is a context rule, and carries a `provenance` block with `scope`, `file` and `plugin_version`. There is no timestamp, so the same deck and plugin version give identical bytes.
- Override legality ranks safety above age band above context above core. A rule may override a rule in the same scope or a lower one; it may not override a higher one, and no rule may override a safety rule, not even another safety rule. A shipped rule may not override an overlay rule. An override loop is reported with the rule ids that form it and stops the run; no rule is dropped silently.
- Evidence floor: a `do` rule accepts an active A, B or D finding in any scope, because D is guidance from a public-health or professional body whatever the rule's file. `must` accepts active A, B or D. `must_not` accepts active or contested A, B or D (see D-021). `contested` backs only `avoid` and `must_not`.
- `validate_rules.py` skips `_TEMPLATE.yaml` files because they are scaffolds, not shipped rules. Every other rule file is checked regardless of its `status`.
- Promotion copies overlay files into the shipped tree and leaves the overlay copies in place, because SPEC.md invariant 3 says nothing is deleted automatically. It refuses to ship a finding that is not `active` or `contested`, because invariant 1 says every shipped finding is one of those. It refuses an incoming finding whose DOI is already held in `findings/` or `quarantine/`, naming the id that holds it, which stops a second run over the same overlay from duplicating the record. The maintainer removes the overlay copies after review.
- A passing script check writes the status that check now supports: a provisional finding whose record meets the active condition becomes `active`. A record that falls short stays provisional and the run prints what is missing. `contested` is never changed by a script.

**Why.** These are the smallest choices that satisfy the SPEC's stated outcomes. Recording them keeps a later milestone from treating an unnamed output shape as an accident.

### D-021: A contested finding backs a `must_not` rule but not a `must` rule

**Contradiction.** SPEC.md section 3's status table says of `contested`: "Only `avoid` and `must_not` rules". SPEC.md section 4's evidence floor says `must` and `must_not` need an "Active finding graded A, B or D". Read together, a contested finding may back a `must_not` rule by the table and may not by the floor.

**Decision.** The status table wins, because it is the more specific statement about contested findings. A `must_not` rule may cite an active or contested finding graded A, B or D. A `must` rule still needs an active finding: contested evidence can forbid a behaviour but cannot require one. `avoid` accepts any active or contested finding, as the floor already says, and `do` keeps its active A or B, plus D for guidance. `validate_rules.py` encodes both readings of the floor and the table.

**Why.** A `must_not` says "do not do this", which is what weak or mixed evidence can still support; dropping contested from `must_not` would forbid using findings the research skill is told to ship. A `must` says "always do this", and a contested finding is by definition one the evidence does not settle.

**Carried forward.** This resolves a SPEC contradiction by reading, not by editing the SPEC. It goes to the person at the M3 gate, alongside the D-019 question, so the wording can be settled in the spec itself or the reading confirmed.





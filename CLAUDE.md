# Working in the Tuckcard repo

Tuckcard is an MIT-licensed Claude plugin that helps someone write a research-informed deck of motivational cards for a specific person or group and render it for print and lock screens. `SPEC.md` is the source of truth. Read it before changing anything, and follow it over your own defaults.

## Where things are

- `SPEC.md`: the full specification, decisions log (Appendix B) and platform facts (Appendix C).
- `BOOTSTRAP.md`: the build order and review gates. If you're building the repo from the seed kit, start there.
- `plugins/tuckcard/skills/`: the plugin. `cards-core` is the shared library; the other six skills are workflows.
- `plugins/tuckcard/skills/cards-core/knowledge/RESEARCH-GUIDE.md`: the only description of how to research a scope. Don't restate it elsewhere; point to it.
- `plugins/tuckcard/skills/cards-core/ROUNDS.md`: the approval protocol and the crisis stop.
- `reference/layouts/`: original design prototypes for the three layouts. They are the visual source for the templates.
- `local/`: the Claude Code overlay. `local/knowledge/`, `local/themes/` and `local/presets/` are tracked; `local/decks/` is private and gitignored.

## Rules for every change

1. **Follow the spec.** If the spec is silent, ambiguous or contradicts itself, stop and ask the maintainer. Don't resolve it silently. If a change would alter an approved decision, add a decisions-log entry in `SPEC.md` Appendix B in the same change.
2. **claude.ai chat is the baseline.** Every core workflow must work with skills alone: no sub-agents, no hooks, read-only skill folders, network possibly blocked. Claude Code features are enhancements.
3. **Never commit personal data.** No real decks, bundles (`*.tuckcard.zip`), renders, or files from the maintainer's private assets. CI enforces this; don't weaken the check.
4. **Clean-room design.** Don't bring in code, images, copy or assets from the maintainer's earlier personal card renderer or from any commercial card deck, and don't add screenshots of other products. Don't name or describe any other card product in docs, the README, examples or commit messages. The three layouts come from this spec and `reference/layouts/` only.
5. **Knowledge rules.** Only `active` or `contested` findings ship. Every rule passes `validate_rules.py`. Findings are paraphrased, with at most one anchor excerpt of 15 words or fewer. Nothing in `knowledge/` describes a specific person.
6. **Licenses.** Only permissive dependencies and OFL fonts. Every font ships with its license file. `THIRD_PARTY.md` is generated; regenerate it when dependencies change.
7. **Generated files** carry a "generated, don't edit" header: `index.yaml`, `effective-rules.yaml`, fit reports, bundle manifests, `THIRD_PARTY.md`.
8. **YAML** is written with ruamel.yaml so comments and key order survive. Schemas are JSON Schema 2020-12.
9. **Determinism.** Compiling the same deck with the same plugin version is byte-identical. Marks use the shared seeded random-number generator, never `Math.random()` or `random.random()`.

## Writing style for docs, skills and card copy guidance

- Plain English, short sentences, specific over vague.
- No em dashes. Use a period, comma, colon, semicolon or parentheses. En dashes are fine for ranges.
- Lead with the point. No throat-clearing.
- Never claim a deck is proven to work.

## Commands (once M0–M2 exist)

- `python plugins/tuckcard/skills/cards-core/scripts/validate.py <path>`: schema-check any file
- `python .../scripts/verify_citations.py <findings...>`: existence and retraction checks
- `python .../scripts/validate_rules.py`: rule schema, citations, evidence floor, overrides
- `python .../scripts/compile_rules.py <deck.yaml>`: write `effective-rules.yaml`
- `python tools/parity/run.py`: renderer parity across all layout × preset × theme combinations
- `claude plugin validate plugins/tuckcard`: plugin structure check

## Commits

Small, focused commits with a one-line summary of what changed and why. Run the relevant checks before committing.

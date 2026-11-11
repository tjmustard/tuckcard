# Research guide

How every agent researches a Tuckcard scope (an age band or a context), whether it's `cards-research` on claude.ai, a user in Claude Code, or the maintainer seeding the repo. This file is the single source for the procedure; `SKILL.md` files and `CLAUDE.md` point here.

Scopes: `core`, `safety`, `age/<band>`, `context/<name>`. See `SPEC.md` Sections 3 and 4.

## 1. Plan the questions

Before any search, write a question plan for the scope and show it to the user for approval (`ROUNDS.md`). Every scope gets these five questions, with scope-specific sub-questions under each:

1. Which message features help motivation or behavior for this scope?
2. Which message features backfire?
3. Which safety issues must cards avoid, or point people toward help for?
4. What does fit require? For age bands: developmental tasks, reading level, card length. For contexts: the role and setting (coach to player, manager to report, parent to child).
5. Which help resources would cards name if the user turns them on, and are they current?

Read `knowledge/gaps/<scope>.md` first so the plan doesn't repeat searches that already came up empty.

## 2. Search

Search in this order, starting broad and narrowing by population:
1. `<topic> meta-analysis`
2. `<topic> systematic review`
3. `<topic> randomized trial <population>`
4. `<topic> guidelines <issuing body>`

Rules:
- News articles, blogs, research-assistant reports and other secondary summaries can lead you to a paper, but they are never the cited source. Get metadata from the publisher, PubMed or the issuing body.
- Record the population the study actually sampled. Don't extend a finding to groups it didn't study.
- Never write findings or rules keyed to sex, ethnicity or other demographic categories. Culture enters a deck only through what the user says about the recipient.
- Prefer recent reviews when older ones exist on the same question, and check whether a classic finding has replicated.

**Stop** when every planned question has at least one active finding or a gap entry, or when you reach the run cap (about 15 new findings per run on claude.ai).

## 3. Write each finding

1. Copy `knowledge/findings/_TEMPLATE.md`.
2. One claim per file. The claim names the population and the outcome. A `source.phone` field holds at most one help number; when a source publishes several, use the one the cards will name, and a different number needs its own citation, such as a page for that number, because promotion refuses a duplicate DOI.
3. Paraphrase everything except the single anchor excerpt (15 words or fewer, from the text you checked).
4. Fill any field you couldn't extract with `unknown` or `not extracted`. Never estimate an effect size.
5. Grade by study design (A–E), then set `distance`, `direction`, `replication` and the limits.
6. Findings describe populations. They never contain details about the deck's recipient.

## 4. Save it in the right place

| Who is researching | Findings go to | ID prefix |
|---|---|---|
| Maintainer seeding the repo (Claude Code) | `cards-core/knowledge/findings/` | `F-` |
| A user in Claude Code | `local/knowledge/findings/` | `L-` |
| A user on claude.ai | `bundle/knowledge/findings/` in the working directory, packaged by `bundle.py` | `L-` |

The next ID is the highest existing ID in that location plus one. Failures move to the matching `quarantine/` folder with a `quarantine_reason`.

## 5. Verify

1. Run `python scripts/verify_citations.py <files>`. If the network is blocked (`env_probe.py` reports it), use the fetch path: open the DOI or PubMed page with your web tools and record `exists: fetch`.
2. Run the support check: read the abstract, or the full text if it's open access, and confirm the claim. Record `support` depth and the anchor.
3. Set `status` from the status rules in `SPEC.md` Section 3. Fetch-only findings stay `provisional`.
4. Before saving, deduplicate by DOI against the pool and the quarantine. A quarantined DOI can't come back under a new ID.

## 6. Record gaps

When a planned question turns up nothing usable, add a gap entry to `knowledge/gaps/<scope>.md` (template: `knowledge/gaps/_TEMPLATE.md`): the question, the searches tried, and the date. Gap entries are public and honest about where evidence is thin.

## 7. Reference findings by ID

- **Rules** cite findings in frontmatter (`cites: [F-0007, L-0002]`) and inline as `[F-0007]`.
- **Summaries for users** show author, year and a DOI link, never a bare ID.
- **Cards** never carry citations. Each card records which rules it serves (`basis`), filled in by `cards-draft`, so any line can be traced back to evidence.
- **Never cite** a provisional or quarantined finding in a rule.

## 8. Propose rules

From the findings, propose rules using `knowledge/rules/_TEMPLATE.yaml`:
- Pick the type (`do`, `avoid`, `must`, `must_not`, `format`) and respect the evidence floor: `do` needs an active A or B finding, or D for practical safety guidance; `avoid` can rest on any active or contested finding; `must` and `must_not` need active A, B or D.
- Write a one-sentence `why` for the user and a bad and good example.
- **Context rules must be age-neutral.** If a rule only makes sense for some ages ("point the player to a parent or coach"), put it in the age-band file or gate it with `when: {age_band: [...]}`.
- No safety rule may require a phone number. Point to people instead; help lines appear only if the user adds them.
- Run `python scripts/validate_rules.py`, then present the rules in approval rounds.

## 9. Hand off

Show the summary table (finding, author-year, grade, direction, status) and the approved rules, then hand back to the calling skill. On claude.ai, emit an updated bundle.

## Path B: claude.ai Research

On paid claude.ai plans with Research available:
1. Turn the approved question plan into a ready-to-paste Research prompt: the scope, the five questions with sub-questions, the search order in step 2, and a request to cite primary sources with DOIs or PMIDs.
2. The user runs Research with it.
3. In the same chat, turn the report into findings. Follow each citation back to its primary source; the report itself is a secondary source. Then continue from step 3 of this guide.

Never depend on starting Research yourself.

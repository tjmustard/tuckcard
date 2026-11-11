---
name: cards-research
license: MIT
description: "Research a Tuckcard age band or context (for example high school, athletics, managing a team): plans questions, finds and verifies sources, records gaps, and proposes card-writing rules. Use when a deck's coverage check reports a missing scope, or the user asks to research a new audience or topic."
---

# cards-research

Follow `../cards-core/knowledge/RESEARCH-GUIDE.md` step by step. It is the procedure; this file only adds the run's framing. Follow `../cards-core/ROUNDS.md` for every approval round.

On claude.ai, unpack an attached bundle first and work from `deck/deck.yaml`.

## Before starting

1. Run `python ../cards-core/scripts/env_probe.py`. Its report decides whether citations are verified by script or by fetch, and where findings are saved.
2. Identify the scopes to research (from the caller's coverage check, or from the user) and read each scope's `knowledge/gaps/<scope>.md`.
3. Web search must be available. If it isn't, say so plainly: drafting can continue only with scopes that are already covered.

## The run

1. **Question plan** (guide step 1). Show it and get approval before any search.
2. **Path choice.** If the user is on a paid claude.ai plan with Research available, offer Path B: write the ready-to-paste Research prompt (guide, Path B). Otherwise search directly.
3. **Findings** (guide steps 2–5): search, write, save, verify, deduplicate. Cap at about 15 new findings per run on claude.ai.
4. **Gaps** (guide step 6) for every planned question without usable evidence.
5. **Summary table:** finding, author-year with DOI link, grade, direction, status. Say how many are provisional and why.
6. **Rules** (guide step 8): propose, validate with `python ../cards-core/scripts/validate_rules.py`, then approval rounds of about 5–8 rules.

## Help resources

If the deck turned help resources on, verify each resource the user supplied as a grade-D finding: the URL resolves, the domain is allowlisted (or the user confirms it and the maintainer can add it later), and the name and number match the page. US resources only in v1; for other countries the user supplies them and they go through the same check.

## Hand off

- Write findings, gaps and rules to the overlay (`local/knowledge/` in Claude Code, the bundle on claude.ai), never into `cards-core`. Only `promote.py`, run by the maintainer, moves anything into the shipped files.
- Update the deck's coverage, set `status: drafting`, and hand back to the calling skill (usually `cards-draft`).
- On claude.ai, emit the bundle and remind the user to keep it private.

# Bootstrap prompt

Paste the block below into Claude Code, opened in this repository after you've unpacked the seed kit into it. Before you start, finish pre-bootstrap tasks P1 (name checks) and P2 (platform probe) from `SPEC.md` Section 10, and have the path to `private-legacy.zip` handy for M6.

---

```
You are building the Tuckcard repository from its seed kit. Read these files fully before doing anything else:

1. SPEC.md (the source of truth, including Appendix B, decisions, and Appendix C, platform facts)
2. CLAUDE.md (repo rules)
3. plugins/tuckcard/skills/cards-core/ROUNDS.md
4. plugins/tuckcard/skills/cards-core/knowledge/RESEARCH-GUIDE.md
5. every SKILL.md under plugins/tuckcard/skills/
6. reference/layouts/README.md

How to work:
- Follow SPEC.md over your own defaults. If the spec is silent, ambiguous or contradicts itself, stop and ask me. Never resolve a spec conflict silently.
- If Appendix C shows a platform fact that contradicts the design, stop and tell me before building on it.
- Build milestones in the order in SPEC.md Section 10 (M0 to M8). Keep a task list with one item per milestone and tick items off as their "done when" checks pass.
- At each review gate (M1, M3, M5, M6, M7) stop, show me what was built and the results of its checks, and wait for my explicit approval before continuing.
- Commit after each milestone passes its checks, with a short summary.
- Clean room: do not use code, images, copy or assets from my earlier personal card renderer or from any commercial card deck. Build the three layouts from SPEC.md Section 7 and reference/layouts/ only.
- Never commit personal data. The private assets for M6 stay outside the repo; ask me for the path to private-legacy.zip when you reach M6, unpack it to a gitignored temporary folder, and delete that folder when M6 is approved.
- Write in plain English with no em dashes, per CLAUDE.md.

Milestone notes:
- M0: download the shipped fonts from their original sources (Google Fonts or their GitHub repos, and liberationfonts/liberation-fonts) with their OFL license files. Verify each font's license before adding it.
- M3: the prototypes in reference/layouts/ are 480 x 480 px HTML at 5 in. Port each into templates/<layout>/ driven by layout.json, theme and preset tokens. Implement the same layouts in the Pillow renderer, and make the parity check pass for all 18 layout x preset x theme combinations.
- M5: seed the research with cards-research, following RESEARCH-GUIDE.md. Show me each scope's question plan before searching, and the proposed rules in approval rounds. If I hand you a bundle from claude.ai Research (Path B), promote it with promote.py.
- M6: build the grade-school, middle-school and college examples from the approved copy in private-legacy.zip (college uses the parents' voice). De-specify every item on the PII checklist in SPEC.md Section 9, retitle any echo of the titles in other-deck-titles.txt, lint against the shipped rules, and write each example's README listing the fixes. Run the PII scan with pii-terms.txt. Then I read every example.
- M7: run the full flow for a new, fictional high-school recipient, first in Claude Code, then help me run it on claude.ai, following the acceptance tests in Section 10.

Start by reading the files above, then summarize the plan for M0 and M1 in a few lines and begin M0.
```

# Rounds: the approval protocol

Every Tuckcard skill that asks the user to approve something (`cards-new`, `cards-research`, `cards-draft`, `cards-restyle`) follows this protocol. Skills point here instead of restating it.

## Crisis stop (always first)

If at any point the user describes someone at immediate risk (thoughts of suicide or self-harm, abuse, a medical emergency, someone in danger right now):

1. Stop card-making immediately. Don't continue the round.
2. Respond to the person directly and kindly. Give crisis resources: in the US, call or text 988 (Suicide & Crisis Lifeline) or call 911 for immediate danger; elsewhere, the local emergency number.
3. Say plainly that cards are no substitute for that help.
4. Resume only if the user asks to, and only after the immediate concern has been addressed.

This is Claude speaking to the adult making the deck. None of it goes into deck content, and it never changes the deck's `help_resources` policy.

## What a round looks like

1. **The draft.** Show the current batch: a section of intake answers, a set of proposed rules, a category of cards, or a style preview. Show the whole batch, not a diff, unless the user asks for only the changes.
2. **Numbered questions.** Two to five questions whose answers would actually change the batch. Skip questions with an obvious default; take the default and say so.
3. **Assumptions.** State the assumptions you made, labeled so the user can confirm or correct each in a word.
4. **Lint and evidence, where relevant.** For cards, show remaining lint warnings with each rule's `why`. For rules, show citations as author-year with a link.

Keep the message short. The batch is the point.

## What counts as approval

- **Approval:** "approved", or an explicit equivalent such as "looks good, move on", "yes, lock it", "approve batch 3".
- **Not approval:** answers to your questions, edits, or casual reactions such as "nice", "cool", "love it". Answers are input; apply them, show the revised batch, and ask again.
- **Unsure?** Ask: "Is this batch approved?"

Move to the next batch only after approval. When approval comes, record it (for cards: `approved_hash`, `linted_hash`, `approved_by: round`, `approved_round`).

## Batch sizes

| Skill | One round covers |
|---|---|
| `cards-new` | One of the four intake groups |
| `cards-research` | The question plan; then rules, about 5–8 per round |
| `cards-draft` | One category, about 10 cards at most |
| `cards-restyle` | One preview per affected layout, preset and theme combination |

## On claude.ai

After each approved round, update the working files. At the end of each stage (not each round), emit an updated bundle so a dropped conversation loses at most one stage. Tell the user to keep the bundle private.

## If the user goes quiet or leaves

Don't approve on their behalf. Summarize where the deck stands, emit the bundle on claude.ai, and stop.

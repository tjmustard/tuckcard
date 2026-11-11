---
id: F-0000                  # F- shipped, L- overlay; next free number in the target folder
claim: >
  One claim, naming the population and the outcome, in your own words.
direction: supports         # supports | caution | null | mixed
scopes: [core]              # core | safety/<topic> | age/<band> | context/<name>
grade: B                    # A meta-analysis/systematic review | B randomized or preregistered experiment
                            # C observational/quasi-experimental | D public-health or professional guidance
                            # E theory, expert opinion, practitioner literature
design: experiment
population: not extracted   # who was actually sampled
effect: not extracted       # metric and size when reported; never estimate
distance: adjacent          # direct | adjacent | distal: how close the setting is to reading a card
replication: unknown        # replicated | mixed | failed | unknown
source:
  citation: "Author, Author & Author (Year). Journal Volume(Issue):pages."
  title: null               # expected title; compared when present
  year: null                # expected four-digit year; compared when present
  first_author: null        # expected family name only; compared when present
  doi: null                 # 10.xxxx/...
  pmid: null
  url: null                 # for guidance documents without a DOI; domain must be on sources-allowlist.yaml
  phone: null               # optional help number, E.164 or digits with separators; when set, a card's number must equal it
verification:
  exists: none              # none | fetch | script
  metadata_match: []        # title, year, first_author
  retraction: none          # none | correction | concern | retracted
  support: unchecked        # unchecked | abstract | full_text
  anchor: ""                # one excerpt of 15 words or fewer from the text you checked
  checked_on: null          # YYYY-MM-DD
status: provisional         # provisional | active | contested | quarantined
related: []                 # IDs of supporting or contradicting findings
---
**Implication for cards.** One or two sentences, in your own words, on what this means for card copy.

**Limits.** Sample, setting, measures, anything that narrows how far this applies.

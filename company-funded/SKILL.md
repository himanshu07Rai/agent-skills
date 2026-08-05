---
name: company-funded
description: "Use when the user wants recently funded companies. Live web/RSS/search only — short company list with round, amount, date, and evidence links."
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [funding, startups, discovery, techcrunch]
    related_skills: []
---

# Recently Funded Companies

Find and list companies that recently raised funding. Output is a clean shortlist only.

## When to use

- Recently funded companies / who just raised / funding news
- A dated list of startups with round and amount

## Defaults

| Knob | Default |
|------|---------|
| Window | last ~3 months (widen if asked) |
| Count | ~15–25 after filtering noise |
| Sort | newest first |
| Sources | TechCrunch feeds/search, optional PR/HN/roundups |

## Workflow

### 1. Collect

Use web tools and/or public RSS. Parallelize when possible.

Search examples:

- `raises OR raised OR "Series A" OR "Series B" OR seed funding` + current year
- `site:techcrunch.com raises $M`

RSS (curl if extract tools unavailable):

- `https://techcrunch.com/category/startups/feed/`
- `https://techcrunch.com/category/fundraising/feed/`
- `https://techcrunch.com/tag/funding/feed/`

Optional: HN Algolia `search_by_date` with a funding query and recent `created_at` cutoff.

Prefer primary article URLs. Cap raw headlines ~40 before filtering.

### 2. Normalize

For each hit keep:

- company name (product/legal name, not founder-only or headline fluff)
- amount and round when stated
- date
- one-line what they do (if clear)
- evidence URL
- confidence: high / medium / low

Drop or demote:

- VC/PE **fund** raises (unless user wants funds)
- Macro pieces with no single company
- Outside the time window
- Duplicates (keep best evidence)
- Pure “in talks” rumor unless labeled as such

Fix noisy titles using the article title/body (e.g. company is Ellis AI, not “Repeat founder …”).

### 3. Present

Always deliver:

1. One line: window + method + count
2. Table: company | round/amount | date | one-liner | evidence URL
3. Optional “skip” bullets for funds / bad parses (brief)
4. Optional “reported / in talks” section if any

No essays. No career/job framing. No file writes unless the user asks to save a path.

## Pitfalls

1. Fund closes ≠ operating companies
2. Founder name in title ≠ company name — resolve real name
3. Mega-lab rounds drown the list — include only if relevant or user wants giants
4. Stale tag feeds — prefer items inside the window; say when a source is thin

## Verification

- [ ] Live sources only
- [ ] Table of companies with evidence links
- [ ] Noise called out briefly
- [ ] No off-topic career/pipeline content
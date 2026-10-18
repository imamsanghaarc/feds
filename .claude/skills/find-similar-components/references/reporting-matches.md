# Reporting Matches

Present at most three candidates. For each one include:

- **Name** — the saved task or component title
- **Framework** — as recorded in the workspace
- **Status** — draft, approved, needs_attention, published
- **Summary** — one sentence on what it does
- **Verdict** — directly reusable / adaptable / not worth reusing, and why

## Ordering

Order by the reported `distance` when retrieval was semantic: smaller distance
means closer in meaning. When retrieval fell back to full-text search, distance
is `null` and ordering is by text relevance only — say so, because a weaker
match is less trustworthy.

## Framing

- Lead with the single best candidate, then the alternatives.
- If nothing is a good match, say that directly instead of padding the list.
- Do not claim a match is reusable without reading its summary.
- When the user asked "have we done this before?", a confident "no" is a valid
  and useful answer.
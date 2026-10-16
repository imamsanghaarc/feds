---
name: summarize-component
description: Use when the user asks for one frontend engineering handoff note, current-status breadcrumb, or compact summary for a single component, bug, accessibility issue, or implementation thread. Triggers on phrases like "handoff note", "TL;DR this thread", "what's the status", or "where does this stand?", even if the user never says "summarize". Do NOT use for drafting customer-facing replies, triaging multiple tickets, reporting aggregate metrics, or creating generic documentation.
---

# Summarize Component

Create a concise engineering handoff for exactly one item.

## Trigger phrases
- "write a handoff note for component #42"
- "TL;DR this thread"
- "what's the status before I escalate?"
- "summarize this component"

## Execution rules
1. Load `references/handoff-template.md` and follow its section order.
2. Read only the supplied component, thread, task, or issue.
3. Keep facts separate from inference. Label anything unverified.
4. Name blockers explicitly rather than implying progress.
5. Do not invent tests, reviews, or customer feedback that were not supplied.
6. Keep the handoff under 220 words unless the user asks for detail.

## When to escalate instead
If the item has already had a real build attempt and shows an unresolved
high-impact problem, accessibility risk, or negative user sentiment, load the
`escalate-review` skill instead of writing a routine handoff.

## Trigger evaluation

### Should fire
- "handoff note for #42"
- "TL;DR this thread"
- "what's the status before I escalate?"

### Should not fire
- "draft a reassuring reply"
- "triage the whole queue"
- "daily report of ticket counts"

Description-quality check: deleting the obvious keyword "summarize" still leaves
the trigger usable.
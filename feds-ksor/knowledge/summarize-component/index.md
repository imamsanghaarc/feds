---
title: "summarize-component"
description: "Use when the user asks for a written note, handoff note, rundown, TL;DR, or current-status summary about ONE frontend component, bug, or accessibility issue. Triggers on "handoff note", "rundown", "TL;DR this thread", "what's the status", "where does this stand", "summarize this component", and "give me a note on this before I hand it off", even when the user never says "summarize". A request for a written NOTE or SUMMARY belongs here even when it mentions escalating, handing off, or a deadline. Do NOT use for packaging an unresolved issue for another engineer to act on (that is escalate-review), for drafting customer-facing replies, for triaging a batch of items, or for aggregate metrics."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: ["references\handoff-template.md"]
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
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
7. **Publish the handoff for the next skill.** When a sandbox filesystem is
   available, write the finished note to `.agents/handoff/<component-slug>.md`
   so another skill can pick it up without re-collecting context. When there is
   no filesystem, save it with `save_task` (metadata `"type": "handoff"`)
   instead, so `lookup_task` can still find it.

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
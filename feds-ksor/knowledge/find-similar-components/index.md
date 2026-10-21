---
title: "find-similar-components"
description: "Use when the user asks whether prior frontend work exists, needs a similar task, past component, saved layout pattern, or warns against duplicate effort. Triggers on "have we done this before?", "find similar components", "find related frontend work", or "what did we build before?". It searches the saved frontend workspace before new drafting. Do NOT use for generic framework documentation lookup when no saved workspace question exists."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: ["references\reporting-matches.md", "references\retrieval-notes.md"]
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Find Similar Components

Locate prior frontend work before drafting something new.

## Trigger phrases
- "have we done this before?"
- "find similar components"
- "find related frontend work"
- "what did we build before?"

## Execution
1. Extract the user's interaction, visual problem, or component need in 1-2 sentences.
2. Call `find_similar_tasks` with `limit=5`.
3. Return at most 3 candidates using `references/reporting-matches.md`.
4. Mark each result as directly reusable, adaptable, or not worth reusing.
5. If nothing matches well, say so plainly and offer to save the new work.

## Reuse rules
- Prior saved work outranks generic advice.
- Search results are suggestions, never binding specifications.
- Never silently replace the user's stated requirements with a prior implementation.
- Flag accessibility or performance choices in older matches that may now be stale.
- When several components are equally close, ask which one to build on rather
  than picking for the user.

## Retrieval notes

Load `references/retrieval-notes.md` if the result looks wrong: it explains why a
query can fall back to full-text search or return nothing, and what that means
for the confidence of the answer.

## Trigger evaluation

### Should fire
- "have we built this before?"
- "find similar components"
- "what did we build before?"

### Should not fire
- "find the latest accessibility docs"
- "how does Tailwind implement a navbar?"
- "quickly explain a CSS flexbox layout"

Description-quality check: the description still says when to fire even if the
keyword "similar" is deleted.
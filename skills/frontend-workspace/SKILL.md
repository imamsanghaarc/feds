---
name: frontend-workspace
description: Use to safely save, search, list, review, publish, or compare frontend tasks and components with WCAG notes, layouts, and implementation patterns through the scoped MCP server. Triggers on 'remember this component', 'find a similar component', 'what did we build before', 'list my frontend tasks', 'review this component', 'store frontend implementation details', 'publish this approved component'. Do NOT use for runtime database migrations, broad SQL, ad-hoc schema changes, unbounded database browsing, or approving your own publication.
---
# Frontend Workspace Skill

FEDS uses Neon Postgres as its durable system of
record and accesses it only through the scoped `frontend-workspace` MCP server.

## Purpose
Safe, scoped knowledge work for frontend tasks and components, with no path to
raw database, schema, or migration access.

## When to Use
- "Save this component for later."
- "Find components similar to a responsive navbar."
- "What frontend tasks do I already have?"
- "Review the accessibility state of a saved component."
- "Publish the component I already approved."

## Do Not Use
- Runtime database migrations or schema changes.
- Broad SQL writes or any `run_sql` style call.
- Unbounded database browsing.
- Database administration.
- Marking a component approved in order to publish it.
- Storing secrets, credentials, or PII in component notes.

## Tools
- `lookup_task(name, status?)` — exact lookup by name, optionally by status.
- `list_tasks(status?, framework?, limit=20)` — browse saved work; use this when
  the user asks what exists rather than naming one item.
- `find_similar_tasks(description, framework?, limit=5)` — semantic reuse search.
- `save_task(name, task, framework, wcag_notes, responsiveness_notes)` — saves and
  audits. Re-saving the same name updates the existing record rather than
  duplicating it.
- `record_review(name, status, reviewer, notes)` — records a human quality
  outcome (`approved`, `rejected`, `needs_attention`).
- `publish_task(name, target)` — promotes an **already approved** task to
  `staging` or `production`. It refuses anything not approved, and production
  additionally requires an operator opt-in.

## Constraints
- Embeddings are 768-dimensional and every stored vector records the model that
  produced it; search only ever compares vectors from one model.
- Keep search limits reasonable, default 5.
- Every significant action writes one audit row and one capability metric row.
- Publication requires a recorded human review first.
- Schema changes happen offline only, never at runtime.

## Execution Workflow
1. Decide which action applies: lookup, list, search, save, review, or publish.
2. Call the matching MCP tool and respect its parameters.
3. Include framework, WCAG, and responsiveness detail when saving.
4. Treat prior work as suggestions, not authoritative specifications.
5. Flag accessibility choices in older matches that may now be stale.
6. Before publishing, confirm the task status is `approved`.

## Verification Checklist
- No broad SQL or raw database access.
- Search limits are reasonable for the request.
- Writes carry accessibility and responsiveness context.
- Audit and capability rows accompany significant actions.
- Duplicate names are updated, not duplicated.
- Missing WCAG detail triggers a clarification request before saving.
- Nothing is published without a recorded approval.

## Common Pitfalls
- Silently replacing user requirements with a prior implementation.
- Saving incomplete accessibility data.
- Treating search results as authoritative.
- Approving your own work in order to unblock publication.
- Using private or customer data in shared notes.
- Bypassing the MCP server for conversational convenience.

## Edge Cases
- No prior match: report that there is no strong precedent.
- Framework specified: filter relevance accordingly.
- WCAG or responsiveness detail missing: ask before saving.
- Same name exists: `save_task` updates it; summarize the delta.
- Raw database access requested: refuse and use the scoped tools.

## Example
Input: "Remember this responsive navbar; it passes keyboard navigation but fails
high contrast in dark mode."
Action: call `save_task` with the WCAG note, then report the outcome and the next
accessibility correction.
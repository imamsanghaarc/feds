---
name: escalate-review
description: Prepare a frontend engineering escalation package for a human reviewer. Use only when there has been one real build or review attempt and at least one true escalation condition exists: unresolved high-impact issue, negative user sentiment, accessibility risk, or explicit human-review request. Do NOT use for routine drafting, simple summaries, generic documentation lookup, or component creation.
---

# Escalate Review

Package frontend work for human review.

## Trigger conditions

All of these must hold:

1. At least one genuine build or review attempt has already happened.
2. At least one of the following is true:
   - sentiment is clearly negative, or the user is visibly frustrated
   - there is risk of public-facing impact
   - there is an accessibility, WCAG, or legal-adjacent concern
   - the user explicitly asked for human review

If either condition fails, do not escalate. Write the ordinary answer instead.

## Execution

1. Load `references/escalation-package.md` and follow its section order.
2. Gather evidence from the workspace with `lookup_task` or `find_similar_tasks`
   rather than describing work you have not checked.
3. State plainly what remains unresolved and who needs to decide.

## Rules

- Do not escalate to satisfy a bias toward escalating.
- Do not escalate an ordinary ask.
- Keep the package factual and bounded.
- Reference `find-similar-components` findings when they exist.
- An accessibility concern is always worth escalating, even without negative
  sentiment.
- Never publish on the user's behalf; publication is a separate approved action.

## Trigger evaluation

### Should fire
- "user is frustrated and says this keeps failing"
- "QC blocked this on WCAG grounds"
- "please hand this to another engineer"
- "the public-facing quality path is unclear"

### Should not fire
- "summarize this thread"
- "find if we built a sidebar before"
- "draft a frontend code snippet"
- "just tell me what framework to use"

Description-quality check: the description still says when to fire even if
"escalate" is deleted.
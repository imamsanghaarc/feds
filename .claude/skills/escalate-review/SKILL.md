---
name: escalate-review
description: Prepare a frontend engineering escalation package for a human reviewer or another engineer to act on. Use when ANY of these is true: a QA or review process blocked the work; the user is visibly frustrated or sends negative sentiment; there is an accessibility, WCAG, or legal-adjacent risk; the user asks to hand it off, hand it over, get a second opinion, or send it for human review; or a high-impact issue is still unresolved. Triggers on "hand this off", "hand this over", "another engineer", "get a second opinion", "send for review", "QC blocked this", "escalate this". Do NOT use for routine drafting, for a written note or summary about a task (that is summarize-component), for generic documentation lookup, or for creating a component.
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
3. **Consume the previous skill's work instead of redoing it.** If a handoff
   note exists at `.agents/handoff/<component-slug>.md`, attach it as the
   package's Summary section verbatim — do not re-summarize from scratch. If no
   file exists, look for the note as a saved task (`lookup_task`, type
   `"handoff"`); only when neither exists should you gather the facts yourself.
4. State plainly what remains unresolved and who needs to decide.

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
---
name: replace-with-kebab-case-name
description: One line on what this skill does. Use when <trigger conditions — quote the exact phrases a user might say>. Do NOT use for <the neighbouring skill this could be confused with, and how it differs>.
---

# Skill Title

One sentence: the outcome this skill produces.

## When to use

- <condition that must be true>
- <trigger phrases, quoted — this is what the skill index lets the model match on>

## Steps

1. <do this>
2. <do that>
3. <finish with the concrete deliverable>

## Output

<the exact shape of a good answer: sections, checks, file names, code style>

## Constraints

- <what not to do, what to verify before finishing>
- Keep frontend advice aligned to Core Web Vitals: LCP ≤ 2.5s, INP ≤ 200ms,
  CLS ≤ 0.1 (p75 field thresholds).

<!--
HOW TO USE THIS TEMPLATE
1. Copy this directory to .claude/skills/<your-skill-name>/
   The skill index discovers SKILL.md by glob — there is no registration step.
2. Directory name == frontmatter `name` == what `load_skill` is called with
   (kebab-case).
3. The model picks skills from name + description alone, so write the
   "Do NOT use for" line for every skill that could be confused with this one.
4. Long material goes in references/*.md inside this directory — load_skill
   appends them automatically when this skill is loaded, so they cost nothing
   until a task actually needs them. Never inline the corpus into SKILL.md.
5. Run the gate:  uv run python run_tests.py
   Optional quota-bound trigger scoring: uv run python eval_triggers.py
-->

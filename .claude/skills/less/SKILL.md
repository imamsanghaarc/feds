---
name: less
description: Use for Less variables, mixins, guards, nesting, and compilation. Triggers on 'Less', 'LESS', 'mixin', '@import', '.less', 'Less compiler'. Do NOT use when standard CSS or project convention selects another preprocessor or stack.
---

# Less Skill

## Purpose
Maintain Less systems safely while documenting paths to standard or better-supported CSS.

## When to Use
- Maintain .less source
- Debug Less compilation
- Review variable and mixin scope
- Migrate Less to CSS or Sass
- Configure output and linting

## Do Not Use
- Greenfield standardization without dependency review
- Markup semantics (use HTML)
- JavaScript behavior

## Expert Concepts
- Less language grammar and compiler versions
- Variables, interpolation, mixins, guards
- Nesting and parent selector strategy
- Imports and scope
- Output options and source maps
- Runtime CSS variables versus compiled variables

## Best Practices
- Keep nesting depth bounded
- Namespace mixins to avoid global collisions
- Prefer native CSS variables for runtime themes
- Use documented import-once behavior
- Inspect compiled CSS size and selectors
- Pin compiler version and output settings

## Execution Workflow
1. Assess Less dependency and business need
2. Catalog mixins and variables
3. Compile and audit generated CSS
4. Reduce global state
5. Migrate one module at a time
6. Add reproducible build checks

## Verification Checklist
- Compiler version is pinned
- Generated CSS reviewed
- No accidental global selector leakage
- Runtime theme vars are not unexpectedly compiled away
- Import order explicitly intentional
- Source maps valid

## Common Pitfalls
- Legacy import ordering bugs
- Mixin guard complexity
- Global variable mutation
- Color function output drift
- Tooling abandonment risk
- Unnecessary preprocessor layer

## Tooling and Review
- Less documentation, Stylelint, compiler integration, visual regression

## Example
```
@card-gap: 1rem;

.card {
  display: grid;
  gap: @card-gap;
  &--compact {
    gap: @card-gap / 2;
  }
}
```
## Edge Cases
- Less and Sass migration can expose variable evaluation differences
- Browser-facing CSS may still need postprocessing
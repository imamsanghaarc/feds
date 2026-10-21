---
title: "sass-scss"
description: "Use for Sass/SCSS variables, mixins, partials, nesting, and compilation. Triggers on 'Sass', 'SCSS', 'mixin', '@use', '@forward', 'preprocessor', '.scss'. Do NOT use when modern plain CSS already solves it, or for markup behavior and framework runtime configuration."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Sass / SCSS Skill

## Purpose
Use preprocessing with clear module boundaries and a strict path toward standard CSS.

## When to Use
- Maintain legacy Sass architecture
- Implement tokenized nesting and mixins
- Migrate @import to @use/@forward
- Generate compact CSS output
- Review preprocessing performance

## Do Not Use
- New projects where native CSS nesting and variables suffice
- Markup behavior (use JavaScript)
- Framework runtime configuration

## Expert Concepts
- SCSS versus indented Sass syntax
- Module system: @use, @forward, @import deprecation
- Variables, mixins, functions, partials
- Nesting limits and source mapping
- Output style, compression, debugging
- Bundler and task runner integration

## Best Practices
- Prefer native CSS features when available
- Enforce a nesting depth limit
- Avoid @import in new Sass modules
- Use @use/@forward for namespaced imports
- Keep global variables minimal and documented
- Set deterministic output and source maps
- Review generated CSS size

## Execution Workflow
1. Determine whether Sass is needed
2. Define module and token boundaries
3. Replace @import with explicit Sass modules
4. Refactor deeply nested selectors
5. Build and inspect generated CSS
6. Add lint and visual regression checks

## Verification Checklist
- No nesting above agreed depth
- Generated CSS has no unexpected global selectors
- Output has correct source maps
- Mixin output is documented contract
- Migration removes @import from target files
- Bundler task reproducible

## Common Pitfalls
- Deep nesting producing high specificity
- @import duplication and global variable leaks
- Output bloat from repeated mixin output
- Source mapping drift
- Build tool split between Sass versions
- Onboarding friction from Sass-only concepts

## Tooling and Review
- Sass docs, Stylelint, Sass migrator, browser-compat review, bundler config validation

## Example
```
// _card.scss
@mixin card($gap: 1rem) {
  display: grid;
  gap: $gap;
  padding: $gap;
}

// main.scss
@use 'card';

.card { @include card; }
```
## Edge Cases
- Advanced @at-root behavior varies by toolchain
- Legacy indented Sass needs conversion before migration
- Output conventions need team agreement
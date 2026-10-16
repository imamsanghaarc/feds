---
name: handlebars
description: Use for Handlebars helpers, partials, and HTML template generation. Triggers on 'Handlebars', 'HBS', 'helper', 'partial', 'compile', 'template'. Do NOT use for application state, framework components, business calculations, or modern JSX render trees.
---

# Handlebars Skill

## Purpose
Build safe and predictable HTML templates with Handlebars while avoiding logic-heavy views.

## When to Use
- Email or server-rendered HTML templates
- Partial and helper systems
- Review XSS and data binding
- Compile template bundles
- Migrate legacy template code

## Do Not Use
- Complex client application state (use framework components)
- Business calculations
- Framework-specific component syntax

## Expert Concepts
- Template context, paths, lookups
- HTML escaping by default and raw triple braces
- Helpers, partials, block helpers
- Compiled and precompiled templates
- Runtime options and data framing
- Caching and bundle organization

## Best Practices
- Keep templates presentation-only
- Escape all output unless explicitly justified
- Name helpers and partials clearly
- Avoid runtime helper overload in hot render paths
- Review naming collisions and depth
- Test compiled templates with representative data

## Execution Workflow
1. Define template purpose and data contract
2. Design partial and helper surfaces
3. Review template syntax
4. Compile and render smoke tests
5. Validate escaping and accessibility
6. Document helper contracts

## Verification Checklist
- No unescaped untrusted output except explicit safe values
- Template context typed or documented
- Partials avoid circular includes
- Missing data shows clear fallback UI
- Helper errors cannot crash render without handling
- Output is WCAG-reviewable

## Common Pitfalls
- Overloaded helpers hiding business logic
- Raw triple braces XSS risk
- Template fragility from deep property chains
- Build mismatch with runtime compile settings
- Whitespace inconsistencies across platforms
- Large nested partial graphs

## Tooling and Review
- handlebars docs, helper unit tests, compiled fixtures, browser/email tests

## Example
```
{{#if user}}
  <h1>Hello, {{user.name}}</h1>
{{else}}
  <p>Please sign in.</p>
{{/if}}
```
## Edge Cases
- Precompiled templates require compile/runtime version alignment
- Stateful helpers can make output non-deterministic
- Email templates demand client-tested markup
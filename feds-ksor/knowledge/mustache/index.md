---
title: "mustache"
description: "Use for logic-less Mustache templates, partials, and cross-runtime rendering. Triggers on 'Mustache', 'logic-less template', 'partial', 'tag', 'render'. Do NOT use when templates require complex logic, interactive applications, or framework component workflows."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Mustache Skill

## Purpose
Keep Mustache templates logic-light, portable, cleanly escaped, and aligned with view-model design.

## When to Use
- Render cross-language template views
- Refactor logic-heavy templates
- Partial composition
- Review output escaping
- Generate template bundles

## Do Not Use
- Complex view logic
- Interactive client applications
- Framework components

## Expert Concepts
- Logic-less tags and lambdas
- Sections, inverted sections, partials
- HTML escaping behavior
- Whitespace handling
- View model preparation
- Cross-runtime implementation differences

## Best Practices
- Move logic into view models
- Escape by default and audit raw output
- Name partials with clear ownership
- Keep section depth understandable
- Test rendering across runtimes
- Document partial contracts

## Execution Workflow
1. Define view model and required fields
2. Author template and partials
3. Review tags and escaping
4. Render with representative data
5. Test cross-runtime parity
6. Document missing and empty states

## Verification Checklist
- No hidden business rules in template
- Escaping defaults except documented safe values
- Missing variables have defined behavior
- Partial names resolve consistently
- Whitespace output intentional
- View model serializes all required fields

## Common Pitfalls
- Logic leakage into templates
- Raw or lambda output mismatch
- Rendering differences across implementations
- Partial name collisions
- Empty-data edge cases
- Lambda output XSS risk

## Tooling and Review
- Mustache spec, runtime rendering tests, sanitization review

## Example
```
{{#products}}
  <article>
    <h2>{{ title }}</h2>
    {{#description}}<p>{{ . }}</p>{{/description}}
  </article>
{{/products}}
```
## Edge Cases
- Implementation lambdas can reduce portability
- Whitespace control becomes significant in tests
- View-model ownership must stay explicit
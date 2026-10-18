---
name: pug
description: Use for Pug server-rendered HTML templates, mixins, includes, and output. Triggers on 'Pug', 'Jade', 'template engine', 'pug filter', 'mixin'. Do NOT use when direct HTML is clearer, when client templating is required, or when framework components are established.
---

# Pug Skill

## Purpose
Author safe, maintainable, accessible HTML generation using Pug while respecting escaping and build context.

## When to Use
- Server-side template rendering
- Email template generation
- Static site template authoring
- Review output HTML and filters
- Debug indentation-driven bugs

## Do Not Use
- Client component templates (use JSX/TSX)
- Real-time rendering without server or build
- Framework-specific template syntax

## Expert Concepts
- Indentation-driven AST and output HTML
- Includes, extends, mixins, blocks
- Attributes, conditionals, iteration
- Filters and JavaScript execution
- Escaping and XSS implications
- Pretty output versus engine whitespace handling

## Best Practices
- Keep generated markup semantic and accessible
- Escape interpolation and block untrusted content
- Use explicit attribute quoting
- Avoid executing user-controlled template strings
- Inspect rendered HTML in CI
- Prefer filters with documented dependencies

## Execution Workflow
1. Define rendered UI requirement
2. Design mixins and layout hierarchy
3. Transpile and inspect HTML
4. Validate semantics and accessibility
5. Review filter dependencies
6. Test edge-case content
7. Add visual or screenshot checks

## Verification Checklist
- No unescaped untrusted values in HTML output
- Generated headings and landmarks valid
- Mixins documented and reusable
- Whitespace output intentional
- No fragile tab or space assumptions
- Compile path deterministic

## Common Pitfalls
- Indentation changes whole output
- XSS through unescaped interpolation
- Filter dependency causes hidden build breaks
- Unreadable HTML from excessive mixins
- Dev/build parity issues
- Whitespace sensitivity bugs

## Tooling and Review
- Pug docs, template smoke tests, email compatibility review

## Example
```
mixin button(label, href)
  a.button(href=href)= label

main.grid
  h1 Dashboard
  +button('View metrics', '/metrics')
```
## Edge Cases
- Server data and filters can create generated-path differences
- Email clients may constrain pretty formatting
- Generated HTML still needs performance review
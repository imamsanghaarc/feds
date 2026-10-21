---
title: "css"
description: "Use for CSS layout, responsive design, tokens, animation, and visual accessibility. Triggers on 'CSS', 'Flexbox', 'Grid', 'media query', 'custom properties', 'animations'. Do NOT use as the primary skill for markup structure, application behavior, TypeScript, or generated utility classes without reviewing output."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# CSS Skill

## Purpose
Design robust, maintainable, accessible, and performance-conscious CSS.

## When to Use
- Design responsive layouts
- Create design tokens and custom properties
- Implement animations and motion
- Handle cross-browser CSS
- Review visual performance and overflow

## Do Not Use
- Markup semantics (use HTML)
- Business logic (use JavaScript)
- Generated utility classes without inspecting final output

## Expert Concepts
- Cascade, specificity, inheritance, layers, and scoping
- Custom properties and token systems
- Flexbox, Grid, container queries, and logical flow
- Color gamut, OKLCH, contrast, theme adaptation
- Modern selectors, nesting, and :has where available
- Animation, transform, containment, rendering performance

## Best Practices
- Prefer low-specificity selectors and predictable naming
- Use custom properties for repeated values and theme changes
- Use container queries rather than viewport-only rules where appropriate
- Use logical properties for international layouts
- Animate transform and opacity instead of geometry
- Respect reduced motion and contrast preferences
- Use cascade layers to avoid ordering surprises

## Execution Workflow
1. Define layout and token model
2. Build mobile-first base styles
3. Add states and responsive adaptations
4. Review contrast, motion, and overflow
5. Measure paint and layout cost
6. Record browser support and fallbacks

## Verification Checklist
- No uncontrolled global overrides
- Focus outline remains visible and usable
- No unexpected horizontal overflow in target viewports
- Contrast meets WCAG target
- Reduced-motion state remains useful
- Font and layout shifts are minimized

## Common Pitfalls
- High-specificity cascade fights
- Hard-coded values instead of tokens
- Animating layout geometry
- Unbounded preprocessor nesting
- Mobile fixes breaking desktop layouts
- Unvetted third-party style overrides

## Tooling and Review
- MDN CSS reference, Stylelint, Lighthouse, browser-compat data, contrast analyzers

## Example
```
/* Mobile-first card pattern. */
.card {
  --card-gap: 1rem;
  display: grid;
  gap: var(--card-gap);
  padding: var(--card-gap);
}

@media (min-width: 48rem) {
  .card { grid-template-columns: 1fr 2fr; }
}

.card:focus-within {
  outline: 2px solid CanvasText;
  outline-offset: 2px;
}
```
## Edge Cases
- Email HTML may need inline CSS and tables
- Shadow DOM changes cascade assumptions
- Print styles can conflict with screen visibility
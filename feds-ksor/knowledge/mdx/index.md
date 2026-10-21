---
title: "mdx"
description: "Use for Markdown files that contain JSX components. Triggers on 'MDX', 'JSX in Markdown', 'content components', 'MDX loader', 'MDXProvider', 'content site'. Do NOT use when plain Markdown is sufficient, for application runtime behavior, or for Handlebars/EJS-style templating."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# MDX Skill

## Purpose
Combine editorial content with type-checked, accessible, and hygienic UI components.

## When to Use
- Author docs or blog content with components
- Build component-driven content systems
- Debug MDX compilation
- Design content contracts and schemas

## Do Not Use
- Plain documentation only
- Application runtime behavior (use JavaScript)
- Server-rendered templates like Handlebars or EJS

## Expert Concepts
- Markdown and JSX boundaries plus compile transforms
- Component props from frontmatter and content data
- Provider scoping and bundle output
- Accessibility of interactive content in prose
- Content security and SSR or client rendering
- Version compatibility across MDX releases

## Best Practices
- Keep content components presentational and reusable
- Validate props with TypeScript
- Use explicit approved component names
- Avoid arbitrary JavaScript in editorial content
- Provide accessible fallbacks for rich widgets
- Test resulting markup, heading hierarchy, and styles

## Execution Workflow
1. Define authoring requirements
2. Choose MDX version and loader pipeline
3. Define allowed component set
4. Add types, schemas, and validation
5. Test rendered HTML and accessibility
6. Document author workflow

## Verification Checklist
- No unsanitized user-controlled MDX
- Heading semantics remain intact after compilation
- Component props are type-checked
- Bundle only includes approved components
- Content renders in SSR and client where applicable
- Code blocks retain syntax highlighting

## Common Pitfalls
- JSX-like prose causes compile errors
- Global component injection creates surprises
- Bundle bloat from rich widgets
- Frontmatter schema drift
- Dark mode or rich media without fallback
- Markdown-as-application-state fragility

## Tooling and Review
- MDX docs, remark/rehype, loader integrations, linting

## Example
```
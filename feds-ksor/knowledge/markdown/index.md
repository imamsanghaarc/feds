---
title: "markdown"
description: "Use for README, ADR, changelog, docs, and GFM content. Triggers on 'Markdown', 'MD', 'README', 'docs', 'documentation', 'changelog', 'ADR'. Do NOT use for executable UI, template logic, API contracts, or structured data exchange."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Markdown Skill

## Purpose
Write clear, portable, accessible documentation in Markdown while maintaining renderer compatibility.

## When to Use
- Create README or project docs
- Write changelog or ADR records
- Structure learning material
- Render docs in GitHub or CMS
- Review headings and link quality

## Do Not Use
- Component runtime (use JSX or TSX)
- Config format needing marked syntax extensions
- Security-sensitive template output

## Expert Concepts
- CommonMark baseline and renderer differences
- Headings, lists, tables, code fences, links
- Alt text, relative links, anchor stability
- Front matter and metadata
- Documentation accessibility
- Content lifecycle and ownership

## Best Practices
- Use semantic heading hierarchy and stable anchors
- Fence code with language labels
- Provide alt text for informative images
- Keep tables simple and understandable on mobile
- Avoid unsupported HTML unless justified
- Use relative repository paths where possible

## Execution Workflow
1. Decide audience and document job
2. Build outline and navigation
3. Write examples and tables
4. Review links and accessibility
5. Validate with markdownlint
6. Add maintenance ownership

## Verification Checklist
- One H1 per document or documented renderer pattern
- No broken local links
- Code samples have language or purpose
- Informative images have meaningful alt text
- Headings concise and unique
- Update workflow documented

## Common Pitfalls
- Renderer-specific extensions assumed universal
- Deep heading nesting from pasted content
- Fragile anchor links
- Inaccessible tables on mobile
- Secrets or internal URLs in public docs
- Stale examples

## Tooling and Review
- CommonMark, GFM, markdownlint, Vale, optional Mermaid

## Example
```
# Responsive Navigation Bar

## Purpose

Describe component behavior and accessibility commitments.

## Verification

```sh
npm run test:a11y
```
```
## Edge Cases
- Diagram widgets may be unsupported in some renderers
- Localization needs an anchor strategy
- Machine-generated API docs need manual accessibility review
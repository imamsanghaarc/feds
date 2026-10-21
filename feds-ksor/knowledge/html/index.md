---
title: "html"
description: "Use for HTML markup structure, forms, media, metadata, and accessibility. Triggers on 'HTML', 'markup', 'page structure', 'form fields', 'meta tags', 'semantic elements'. Do NOT use as the primary skill for CSS-only styling, JavaScript behavior, framework component logic, broad SQL, or deployment configuration."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# HTML Skill

## Purpose
Produce semantic, accessible, fast, standards-compliant HTML that communicates document meaning as well as content.

## When to Use
- Create page or component skeleton
- Define form controls and validation hooks
- Add landmark and heading hierarchy
- Implement responsive media and metadata
- Improve SEO, crawler, or accessibility semantics

## Do Not Use
- Pure visual styling (use CSS)
- Application behavior (use JavaScript)
- Build-tool configuration unrelated to markup

## Expert Concepts
- WHATWG HTML Living Standard and semantic content categories
- Document, body, landmarks, headings, sections, and lists
- Forms, constraint validation, labels, fieldsets, input types, autocomplete
- Responsive media, dimensions, lazy loading, priority hints
- Metadata, language, canonical URL, viewport, structured data
- Progressive enhancement and noscript-friendly baselines

## Best Practices
- Use the most specific native element before adding div, span, or ARIA
- Keep one clear heading hierarchy per document
- Always associate labels with controls and use autocomplete tokens
- Include intrinsic image dimensions and loading hints
- Use metadata and permission-related elements deliberately
- Validate with html-validate and axe-based checks

## Execution Workflow
1. Identify UI intent and state
2. Choose semantic elements and groupings
3. Add accessible names, relationships, and controls
4. Add metadata, media hints, and fallback content
5. Validate headings, links, constraints, and document language
6. Hand layout to CSS and behavior to JavaScript

## Verification Checklist
- No skipped heading levels without explicit UI reason
- Every form control has a programmatic label or fieldset legend
- Informative images include meaningful alt; decorative images use empty alt
- Landmarks are understandable and not redundant
- No invalid or obsolete elements for the target environment
- Critical content renders without JavaScript

## Common Pitfalls
- Div or span soup that erases semantic meaning
- ARIA used where native semantics already exist
- Missing dimensions causing CLS
- Script-dependent core content
- Invalid nesting such as button inside anchor
- Missing autocomplete or sensitive-form security tokens

## Tooling and Review
- MDN HTML reference, html-validate, axe, Lighthouse, Playwright DOM assertions

## Example
```
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Account settings</title>
  </head>
  <body>
    <main>
      <h1>Account settings</h1>
      <form action="/account" method="post" novalidate>
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="email" required />
      </form>
    </main>
  </body>
</html>
```
## Edge Cases
- Email-client HTML may need table compatibility and inline CSS
- Custom elements require documented constructor and progressive fallback
- Multilingual and right-to-left pages need lang and dir handling
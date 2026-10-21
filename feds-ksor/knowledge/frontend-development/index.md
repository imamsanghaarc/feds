---
title: "frontend-development"
description: "Use for frontend website development, responsive implementation, component creation, CSS styling, JavaScript functionality, or React/Vue/Angular work. Triggers on 'build UI', 'responsive page', 'web interface', 'component', 'JavaScript functionality', 'React' or 'Vue'. Do NOT use for broad backend, database migrations, schema changes, deployment approval, or non-UI application logic."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Frontend Development Skill

## Purpose
Enable the Digital FTE to perform frontend tasks including website creation, UI implementation, responsive design, accessibility improvements, and web performance optimization.

## When to Use
- A user asks for a responsive navigation bar, form, card, modal, page, or component.
- A user needs HTML, CSS, JavaScript, React, Vue, or Angular implementation.
- A user wants accessibility compliance checked or improved.
- A user wants Core Web Vitals, bundle size, or rendering performance guidance.
- A user mentions frontend development, web interfaces, UI implementation, or component creation.

## Do Not Use
- Broad backend implementation, database queries, or schema changes.
- Deployment approval, release management, or infrastructure work.
- Data modeling or authentication code that does not affect the UI.
- Unscoped network or file operations requested by the user.

## What It Produces
- Responsive, accessible page or component code.
- Framework-specific implementation in React, Vue, or Angular when requested.
- CSS styling and layout specifications.
- JavaScript interactivity and event handling.
- Performance and accessibility review notes.

## Execution Workflow
1. Review task requirements and identify missing constraints.
2. Select the appropriate semantic HTML, styling method, and framework pattern.
3. Implement or specify the UI component.
4. Add keyboard, focus, color-contrast, and screen-reader behavior.
5. Optimize for LCP, INP, CLS, bundle size, and runtime work.
6. Return code, usage instructions, verification steps, and remaining risks.

## Verification Checklist
- The component responds to the requested viewport range.
- Keyboard and focus behavior are explicit.
- Contrast targets are stated or corrected.
- The implementation does not block on JavaScript for critical content.
- Performance impact is measured or justified.
- The output is compatible with the chosen framework or plain HTML/CSS/JS.

## Common Pitfalls
- Treating visual CSS as a substitute for semantic markup.
- Depending on JavaScript for core content.
- Missing intrinsic image dimensions and causing CLS.
- Overusing ARIA where native HTML already provides semantics.
- Hardcoding values instead of reusable tokens.
- Shipping styling or code with no stated browser support.

## Tooling and Review
- MDN HTML, CSS, and JavaScript references.
- Stylelint, ESLint, Prettier, Vitest, Playwright, and Lighthouse where appropriate.
- Accessibility checks through axe, keyboard traversal, and screen-reader review.
- Core Web Vitals assessment for user-facing changes.

## Example
Use when the request is: "Create a responsive navigation bar with React." Return a semantic `nav`, accessible menu button, keyboard behavior, responsive CSS, and tests for open/close and focus return.

## Edge Cases
- If the request omits framework or design preferences, ask for them before implementation.
- If a design system or style guide is referenced, follow it instead of inventing a new visual pattern.
- If accessibility is a primary requirement, prioritize WCAG AA compliance.
- If the task spans frontend and backend, keep UI work separate from data access implementation.
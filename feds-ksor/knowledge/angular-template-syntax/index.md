---
title: "angular-template-syntax"
description: "Use for Angular bindings, directives, control flow, forms, and templates. Triggers on 'Angular template', '*ngIf', 'directive', 'signal', 'two-way binding'. Do NOT use as a replacement for TypeScript component architecture, business logic, or general DOM APIs."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Angular Template Syntax Skill

## Purpose
Build secure, accessible, performant Angular templates with clear binding and lifecycle boundaries.

## When to Use
- Author component templates
- Implement bindings and directives
- Migration to control flow syntax
- Review template sanitization
- Debug change detection behavior

## Do Not Use
- Relying on template logic as a service
- General application logic
- CSS styling decisions

## Expert Concepts
- Interpolation, property binding, and event binding
- Structural directives and built-in control flow
- Template reference variables
- Signal and RxJS interaction in templates
- Sanitizer, bypassSecurityTrust*, and DOM security
- Change detection and OnPush patterns

## Best Practices
- Keep template expressions simple and side-effect free
- Prefer typed properties and signals for UI state
- Use semantic elements in rendered output
- Handle forms with explicit validation and errors
- Avoid dangerous sanitization bypass without review
- Track performance and lazy loading

## Execution Workflow
1. Define template state and public API
2. Choose bindings and control flow
3. Implement events and forms
4. Review sanitization and security
5. Validate accessibility and performance
6. Test change detection and interactions

## Verification Checklist
- No expensive or side-effecting template expressions
- Sanitization bypass is documented and justified
- Forms provide accessible errors
- Animations and triggers respect motion settings
- TrackBy or structural strategy avoids repeated rendering
- Template output semantics are reviewed

## Common Pitfalls
- Complex expressions in templates
- Security bypass misuse
- Change detection surprises
- Accessibility missing in dynamic regions
- Template reference variable type assumptions
- Overbinding events

## Tooling and Review
- Angular CLI, template type checking, axe, Lighthouse, Angular devtools

## Example
```
<section [attr.aria-labelledby]="headingId">
  @if (tasks.length) {
    <ul>
      @for (task of tasks; track task.id) {
        <li>{{ task.label }}</li>
      }
    </ul>
  } @else {
    <p>No tasks available.</p>
  }
</section>
```
## Edge Cases
- Angular version differences in template syntax are significant
- Signal and RxJS interplay needs careful boundary choices
- Security bypass values must never be user-controlled
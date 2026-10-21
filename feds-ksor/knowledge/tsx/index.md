---
title: "tsx"
description: "Use for TypeScript component syntax and typed props, events, and refs. Triggers on 'TSX', 'typed props', 'React TypeScript', 'generic component', 'component types'. Do NOT use as a substitute for runtime validation, accessibility review, or project configuration."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# TSX Skill

## Purpose
Write strongly typed, maintainable, accessible component syntax connected to real render behavior.

## When to Use
- Type component props and events
- Build reusable typed components
- Refactor JS components to TS
- Debug TSX compiler errors
- Design generic component APIs

## Do Not Use
- Runtime response validation
- Framework build configuration
- Markup-only documentation

## Expert Concepts
- TSX syntax and compiler option requirements
- Props, events, refs, and generic components
- Discriminated union components
- Context and state typing
- Inference versus explicit types in render output
- Compilation and runtime separation

## Best Practices
- Type props as public component contracts
- Use discriminated unions for variant components
- Prefer inference for internal values and explicit types for APIs
- Validate external data at runtime
- Keep refs typed to the actual element
- Document generic constraints

## Execution Workflow
1. Define component variants and public API
2. Model props and events
3. Implement typed refs and context
4. Add runtime validation boundaries
5. Run tsc and component tests
6. Document usage examples

## Verification Checklist
- No implicit any in props
- Ref types match attached elements
- Generic components retain inference at call sites
- Variants cannot accept invalid combinations
- Runtime boundary schemas exist where needed
- Rendered markup remains semantic

## Common Pitfalls
- Complex context reducing maintainability
- Generic APIs with poor ergonomics
- Refs typed to broad HTMLElement everywhere
- Using type assertions instead of fixing model
- Assuming TSX types guarantee render behavior
- Conditional variant mistakes

## Tooling and Review
- TypeScript TSX compiler, typescript-eslint, React Testing Library, Storybook, Vitest

## Example
```
type ButtonProps =
  | { variant: 'link'; href: string; children: React.ReactNode }
  | { variant: 'action'; onClick: () => void; children: React.ReactNode };

export function Button(props: ButtonProps) {
  if (props.variant === 'link') return <a href={props.href}>{props.children}</a>;
  return <button type="button" onClick={props.onClick}>{props.children}</button>;
}
```
## Edge Cases
- TSX generic inference issues can require explicit type arguments
- Framework-specific children types may need update when libraries release
- Type-only props don't validate arbitrary runtime JSON
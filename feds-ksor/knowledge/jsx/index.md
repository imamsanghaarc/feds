---
title: "jsx"
description: "Use for JSX component trees, props, lists, keys, and accessible markup. Triggers on 'JSX', 'React', 'JSX component element', 'conditional render', 'map to li', 'keys'. Do NOT use as the primary skill for framework build setup, CSS styling, or general business logic."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# JSX Skill

## Purpose
Author readable UI expressions that compile to robust JavaScript and remain accessible.

## When to Use
- Create component render trees
- Render conditional and list content
- Design props and child composition
- Review keys and ref handling
- Improve accessibility in component markup

## Do Not Use
- Framework project configuration
- Business logic outside UI boundaries
- CSS implementation

## Expert Concepts
- JSX transforms and pragma/runtime configuration
- Expressions, props, children, and composition
- Conditional rendering and list mapping
- Keys, refs, and component identity
- Accessibility and semantic HTML in components
- Fragments and null rendering

## Best Practices
- Return semantic HTML from components
- Use stable keys based on identity rather than index when identity exists
- Avoid overextracting components before reuse is real
- Keep render branches simple and explicit
- Prop types or TypeScript protect public components
- Review generated HTML and screen-reader output

## Execution Workflow
1. Define component responsibility and public props
2. Choose semantic render output
3. Implement state and events
4. Review keys, focus, and refs
5. Type or validate props
6. Test render, keyboard, and screen-reader behavior

## Verification Checklist
- No unkeyed dynamic lists
- Semantic roles are correct in rendered output
- Props use expected types or documented shapes
- Conditional branches leave accessible names
- Refs are forwarded documented
- No unnecessary re-render sources

## Common Pitfalls
- Index keys on reorderable lists
- Div soup in component markup
- Runaway prop drilling without composition
- Accessibility missing in reusable UI
- Rendered output not inspected
- Assuming JSX is HTML

## Tooling and Review
- React docs, eslint-plugin-jsx-a11y, TypeScript, component tests, Storybook

## Example
```
export function UserList({ users }) {
  return (
    <ul aria-labelledby="users-heading">
      {users.map((user) => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}
```
## Edge Cases
- JSX transform differs by bundler and runtime
- Server and client component expectations differ by framework
- Dynamic component references can hide rendered element semantics
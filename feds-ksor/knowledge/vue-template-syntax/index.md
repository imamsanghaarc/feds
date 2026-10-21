---
title: "vue-template-syntax"
description: "Use for Vue directives, bindings, slots, events, and SFC templates. Triggers on 'Vue template', 'v-if', 'v-for', 'v-model', 'slot', 'directive', 'Vue SFC'. Do NOT use as a replacement for Composition API architecture, global state design, or general DOM APIs."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Vue Template Syntax Skill

## Purpose
Create secure, accessible, maintainable Vue templates with disciplined state and reactivity boundaries.

## When to Use
- Build SFC template sections
- Use v-if, v-for, v-model, or slots
- Review directive usage and escaping
- Migrate Options API template patterns
- Debug reactivity and rendering

## Do Not Use
- Putting complex business logic in templates
- Cross-component state architecture in markup
- General typing outside SFC context

## Expert Concepts
- Interpolation, directives, modifiers, and event handling
- Reactivity and computed usage in template output
- Slot scoping, props, and emit contracts
- Vue rendering and reconciliation
- v-html safety and escaping
- Accessibility and dynamic regions

## Best Practices
- Use computed properties rather than complex expressions
- Provide keys with stable identity in v-for
- Escape by default and audit v-html
- Keep slots accessible and discoverable
- Handle loading, errors, and empty states
- Review bundle and rendering cost

## Execution Workflow
1. Define component data contract and props
2. Render semantic template output
3. Handle events, forms, and slots
4. Review v-html and data sources
5. Validate accessibility and performance
6. Test template interaction and updates

## Verification Checklist
- No unkeyed v-for lists
- No unnecessary complex directive expressions
- v-html preceded by sanitization
- Props and emits documented
- Accessibility audiences reviewed for slots
- State transitions render correct output

## Common Pitfalls
- Reactivity surprises in nested objects
- v-html XSS
- Index keys on reordered lists
- Render function escape assumptions
- Template state outside component lifecycle
- Overuse of watchers instead of computed

## Tooling and Review
- Vue SFC compiler, ESLint plugin Vue, Vue devtools, accessibility tooling, Vite

## Example
```
<section aria-labelledby="tasks-heading">
  <template v-for="task in tasks" :key="task.id">
    <article>
      <h3>{{ task.title }}</h3>
      <p>{{ task.description }}</p>
    </article>
  </template>
</section>
```
## Edge Cases
- Vue 2/3 syntax differences are relevant
- Template compiler transform settings can change output
- Client-side hydration can affect dynamic regions
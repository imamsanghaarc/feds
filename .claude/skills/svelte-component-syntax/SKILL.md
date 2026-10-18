---
name: svelte-component-syntax
description: Use for Svelte markup, reactivity, each blocks, props, slots, and stores. Triggers on 'Svelte', 'reactive component', '$:', 'each', 'slot', 'Svelte component'. Do NOT use as the primary framework runtime, state architecture, or deployment skill.
---

# Svelte Component Syntax Skill

## Purpose
Build compact, accessible, performant Svelte components with clear reactivity and composition boundaries.

## When to Use
- Write Svelte markup and directives
- Use each blocks and reactivity
- Review template output and stores
- Migrate component patterns
- Debug update behavior

## Do Not Use
- Complex global state without architecture
- Framework deployment and routing
- CSS implementation unless paired with style scope

## Expert Concepts
- Declarative markup and reactivity
- Each block and keying
- Component props, events, slots
- Store subscriptions and auto-subscriptions
- Conditional classes and accessibility
- Compile-time transformations

## Best Practices
- Keep templates readable and semantic
- Use keys with stable identity in each
- Move derived logic to reactive declarations
- Clean up subscriptions and side effects
- Use stores at appropriate component boundaries
- Test output and browser behavior

## Execution Workflow
1. Design component API and state boundary
2. Author markup and reactive declarations
3. Handle events and props
4. Review each keying and slots
5. Validate accessibility and updates
6. Test interactions and performance

## Verification Checklist
- Each block has stable keys when reordering
- Reactive statements are not hidden infinite loops
- Props and events documented
- Store subscriptions cleaned up
- Template output semantic
- Bundle size reviewed

## Common Pitfalls
- Reactivity confusion from reassignment
- Global store dependencies
- Index keys in reorderable lists
- Overrender due to broad state
- Slot accessibility gaps
- Compile output assumptions

## Tooling and Review
- Svelte compiler, SvelteKit tools, Vitest, Testing Library, ESLint plugins

## Example
```
<section aria-labelledby="tasks-heading">
  <ul>
    {#each tasks as task (task.id)}
      <li>{task.label}</li>
    {/each}
  </ul>
  <slot name="footer" />
</section>
```
## Edge Cases
- Svelte 4 and 5 reactivity differences are substantial
- Store global state can obscure component ownership
- Compile-time transformations make output bundle needs review
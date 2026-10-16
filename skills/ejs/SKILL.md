---
name: ejs
description: Use for EJS server-side HTML templates, includes, escaping, and caching. Triggers on 'EJS', 'embedded JavaScript template', 'scriptlet tags', 'server rendering'. Do NOT use for client rendering, modern component architecture, or privileged security-sensitive templating.
---

# EJS Skill

## Purpose
Author server-side EJS safely, with explicit escaping, scriptlet boundaries, and template hygiene.

## When to Use
- Server-rendered HTML with EJS
- Debug include or cache issues
- Review escape levels
- Configure build and development
- Migrate legacy EJS

## Do Not Use
- Client-side state management
- Modern component architecture
- Security-sensitive untrusted template editing

## Expert Concepts
- Scriptlet versus output tag boundaries
- HTML escaping with <%= and raw <%-
- Include and layout patterns
- Async support and promise handling
- Caching and compile options
- Delimiter and whitespace configuration

## Best Practices
- Escape output by default and reserve raw output for reviewed values
- Keep template logic shallow
- Validate include paths and data contracts
- Avoid untrusted or dynamic template source
- Test rendered HTML with real context
- Make development and production cache behavior explicit

## Execution Workflow
1. Define render data and output
2. Build template and include tree
3. Review scriptlets and escaping
4. Compile and render smoke tests
5. Validate output semantics and accessibility
6. Document caching and delimiters

## Verification Checklist
- No raw output of untrusted values
- Includes resolve under fixed root
- Async scriptlets awaited correctly
- No application logic hidden in templates
- Template syntax valid under configured delimiters
- Cache behavior does not serve stale private data

## Common Pitfalls
- XSS through <%-
- Opening delimiter collisions
- Cache bypass or stale data
- Template injection if constructing EJS dynamically
- Deep asynchronous control flow
- Whitespace confusion around scriptlets

## Tooling and Review
- EJS docs, renderer smoke tests, security review

## Example
```
<main>
  <h1><%= title %></h1>
  <% if (items.length) { %>
    <ul>
      <% items.forEach(item => { %><li><%= item.label %></li><% }) %>
    </ul>
  <% } %>
</main>
```
## Edge Cases
- EJS async rendering requires configured async option awareness
- Template interpolation with HTML URLs needs escaping plus protocol safety
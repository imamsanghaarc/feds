---
name: javascript
description: Use for browser behavior, events, DOM logic, fetching data, modular UI code, and progressive enhancement. Triggers on 'JavaScript', 'JS', 'event handler', 'DOM', 'fetch', 'promise', 'module'. Do NOT use as the primary skill for markup semantics, visual CSS styling, compile-time type contracts, or backend persistence.
---

# JavaScript Skill

## Purpose
Build accessible, testable, secure, and progressively enhanced JavaScript behavior.

## When to Use
- Add interactivity to existing markup
- Handle form events and validation
- Fetch or update data without full reload
- Modularize UI behavior
- Debug async, DOM, or focus issues

## Do Not Use
- Markup structure (use HTML)
- Visual design (use CSS)
- Compile-time type contracts (use TypeScript)

## Expert Concepts
- ES modules, lexical scope, closures, prototypes
- DOM event delegation, custom events, focus management
- Async/await, promise combinators, AbortController, cancellation
- Fetch, Workers, Streams, observers
- Progressive enhancement, hydration, graceful degradation
- Accessibility behavior such as keyboards and live regions

## Best Practices
- Begin with baseline HTML and enhance behavior intentionally
- Use event delegation where suitable rather than many handlers
- Batch DOM reads and writes to avoid layout thrash
- Abort or ignore stale responses on unmount
- Use Intl APIs for locale-sensitive formatting
- Send actionable validation errors and preserve fallbacks
- Keep modules small, explicit, and tested

## Execution Workflow
1. Define desired interaction and no-JS fallback
2. Choose minimal DOM hooks
3. Add state transitions and validation
4. Manage loading, empty, and error UI
5. Test keyboard and screen-reader paths
6. Optimize bundle and runtime behavior

## Verification Checklist
- No unhandled promise rejections in normal flows
- Handlers can be removed and remain safe
- Focus returns sensibly after dismissal
- Responses are checked with response.ok
- Async operations cancel or ignore stale results
- No console errors except documented diagnostics

## Common Pitfalls
- Assuming DOM order guarantees
- Memory leaks from retained listeners
- XSS from unsanitized innerHTML
- Race conditions in async rendering
- Ignoring reduced motion or locale
- Overfetching without pagination

## Tooling and Review
- MDN references, ESLint, Prettier, Vitest, Playwright, Lighthouse

## Example
```
const form = document.querySelector('[data-profile-form]');

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector('[type="submit"]');
  submit?.setAttribute('disabled', '');

  try {
    const response = await fetch('/api/profile', {
      method: 'POST',
      body: new FormData(form),
    });
    if (!response.ok) throw new Error(response.statusText);
  } finally {
    submit?.removeAttribute('disabled');
  }
});
```
## Edge Cases
- No-JS paths must retain server submission
- Weak networks need retry and messaging policies
- Third-party scripts can alter expected DOM shape
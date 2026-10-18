---
name: complete-frontend-developer-reference
description: Use for broad frontend architecture, web fundamentals, HTTP and DNS, browser rendering and event loop, HTML, CSS, JavaScript, TypeScript, browser APIs, frameworks, tooling, testing, accessibility, performance, SEO, security, compatibility, i18n, design, deployment, and production gotchas. Triggers on 'frontend guide', 'how the web works', 'complete frontend guide', 'frontend architecture', 'HTML CSS JavaScript deep dive', 'browser rendering', 'frontend glossary', 'frontend learning roadmap'. Do NOT use for one-file fixes covered by narrower language or framework skills, backend-only implementation, database administration, exact browser-support claims without verification, or unscoped internet research.
---
# Complete Front-End Developer Reference Skill

## Purpose
Use the supplied Complete Front-End Developer Guide as a structural reference for end-to-end frontend knowledge. Answer in layers: concept, implementation, verification, and production implications. Prefer MDN, web.dev, and official library documentation when syntax, defaults, browser support, or framework behavior may have changed.

## When to Use
- A user asks how the web works, how browsers render pages, or how the event loop behaves.
- A user needs fundamentals, HTTP, URLs, DNS, hosting, caching, CORS, HTTP headers, cookies, sessions, tokens, or real-time transport.
- A user asks about semantic HTML, forms, media, tables, widgets, scripts, resource hints, metadata, SEO, Open Graph, or accessibility semantics.
- A user asks about CSS box model, selectors, specificity, cascade, layout, flexbox, grid, responsive design, typography, color, effects, transforms, transitions, animations, overflow, logical properties, print, or modern CSS features.
- A user asks about JavaScript execution, objects, arrays, classes, modules, async behavior, browser APIs, storage, rendering performance, Web APIs, security, testing, or DOM interaction.
- A user asks about TypeScript, frameworks, routing, state management, data fetching, forms, Node, package managers, build tools, linting, testing, deployment, monitoring, i18n, design systems, or backend/auth integration.
- A user asks for a frontend architecture checklist, learning roadmap, glossary, or common gotchas.

## Do Not Use
- Narrow HTML, CSS, JavaScript, TypeScript, JSX, TSX, Markdown, JSON, YAML, TOML, SQL, GraphQL, CSV, or template syntax fixes that have a dedicated skill.
- Backend service design, database schema decisions, persistent storage administration, or secret management.
- Exact compatibility guarantees without checking current MDN or official docs.
- Research tasks that only need a generic answer.

## Topic Coverage
Web fundamentals, HTTP, browser rendering, event loop, standards, HTML structure and semantics, links and buttons, images and media, forms, tables, interactive widgets, scripts and metadata, CSS syntax, selectors, specificity, cascade, box model, display, positioning, stacking, flexbox, grid, responsive design, typography, color, effects, transforms, transitions and animation, overflow, logical properties, print, modern CSS, architecture, preprocessors, accessibility, performance, SEO, security, compatibility, progressive enhancement, i18n, APIs, authentication, tooling, testing, deployment, monitoring, career and roadmap, and common gotchas.

## Execution Workflow
1. Identify the topic category and the user's experience level.
2. State the concept in plain language first; include exact terminology when useful.
3. Provide implementation guidance with semantic structure, compatibility notes, and production constraints.
4. Distinguish guaranteed standards behavior from widely supported behavior and experimental behavior.
5. Include accessibility, keyboard, screen-reader, color, and motion considerations for all user-facing work.
6. Include performance implications such as layout thrashing, expensive paint, network cost, bundle weight, and rendering time.
7. Include security implications such as XSS, injection, CSRF, CSP, CORS, least privilege, credential handling, and data disclosure.
8. End with verification steps, common pitfalls, and references to official documentation.

## Output Contract
- For a definition question, provide a concise but exact explanation.
- For implementation guidance, provide runnable or framework-agnostic code patterns and explain trade-offs.
- For a broad architecture question, provide a prioritized checklist and a sensible default stack.
- For production guidance, mention observability, caching, accessibility, permissions, failure handling, and rollback implications.
- For compatibility questions, label behavior as broad, limited, experimental, or vendor-specific.
- For security or auth topics, include threat model notes and least-privilege recommendations.

## Verification Checklist
- The topic category was identified rather than answering at the wrong abstraction level.
- Standards behavior is distinguished from browser quirks.
- Compatibility claims are qualified or verified against current sources.
- Accessibility is included even for visual or performance questions.
- Performance advice avoids unnecessary layout and paint where possible.
- Security advice covers injection, disclosure, transport, and permissions.
- Output includes at least one concrete verification or testing step.
- Tooling advice does not recommend deprecated or unsupported syntax.

## Common Pitfalls
- Confusing style with semantic structure.
- Treating hover-only interactions as keyboard-equivalent.
- Calling experimental CSS or APIs baseline without checking support.
- Overlooking mobile viewport, safe areas, or browser chrome.
- Animating layout properties instead of transform and opacity.
- Ignoring contrast, motion sensitivity, RTL, or text magnification.
- Assuming caching or redirect behavior without checking headers.
- Leaking credentials, tokens, or internal information in client code.
- Mixing client-side validation with server authorization.

## Edge Cases
- Legacy browser requirements: use a progressive enhancement or supported polyfill strategy.
- RTL or multilingual scope: prefer logical properties, `start`/`end` alignment, and locale-specific resources.
- Touch-only environments: remove the 300 ms tap delay with `touch-action: manipulation` and keep target sizes generous.
- Print output: provide separate styles or print-safe colors and page breaks.
- Motion sensitivity: respect `prefers-reduced-motion`.
- High contrast or forced colors: support system colors and keep focus outlines visible.
- Slow networks: reduce initial payloads and loading order first.
- Unauthenticated public data: use appropriate caching directives and verify privacy impact.

## Example
User request: "Explain why `vh` behaves poorly on mobile and what to use instead." Return: the mobile viewport chrome behavior, the `dvh`, `svh`, and `lvh` variants, a fallback pattern, safe-area handling, responsive verification steps, and a note that exact browser support should be checked.

## Trigger Test Cases
- Should fire: "Use the frontend developer reference for broad browser and rendering gotchas."
- Should fire: "How does the browser render a page and where do LCP issues come from?"
- Should fire: "Give me a prioritized frontend architecture checklist for this dashboard."
- Should not fire: "Fix this exact CSS overflow bug." (Use `css` instead.)
- Should not fire: "Generate SQL migration scripts." (Use `sql` and backend-only guidance instead.)
---

_Use the user's guidance as the structural basis for answers, and verify evolving syntax, browser support, headers, algorithms, and framework behavior against official documentation._
PY
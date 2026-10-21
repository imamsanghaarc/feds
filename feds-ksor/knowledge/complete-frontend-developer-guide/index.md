---
title: "complete-frontend-developer-guide"
description: "Use for broad frontend architecture, browser behavior, HTTP, HTML/CSS/JS semantics, TypeScript, frameworks, data fetching, forms, testing, accessibility, performance, SEO, security, compatibility, i18n, and production gotchas. Triggers on 'frontend guide', 'how web works', 'complete frontend guide', 'frontend architecture and gotchas', 'frontend best practices', 'browser rendering'. Do NOT use for generic documentation search, one-file fixes covered by narrower skills, backend service design, database administration, or unscoped internet research."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Complete Front-End Developer Guide Skill

## Purpose
Provide a structured way to answer broad, senior-level frontend questions with the account from "The Complete Front-End Developer Guide," while checking current browser support, library versions, and official documentation before applying any implementation detail.

## When to Use
- A user asks how the web works, how browsers render pages, or how the event loop behaves.
- A user needs the breadth of HTML, CSS, JavaScript, TypeScript, browser APIs, frameworks, tooling, testing, accessibility, performance, SEO, security, i18n, and deployment.
- A user wants a roadmap or architecture-level explanation rather than a single isolated language task.
- "Use the frontend guide for this architecture answer."
- "What does the complete front-end developer guide say about this?"
- "Give me a senior frontend checklist for this feature."

## Do Not Use
- Generic framework documentation lookup where a specialized language or framework skill is more accurate.
- Single-file CSS, HTML, JavaScript, TypeScript, JSON, YAML, SQL, or template syntax fixes.
- Backend API implementation, deployment operations, or secret management.
- Unverified compatibility advice without checking current browser support.

## Covered Areas
Web fundamentals, HTTP and DNS, browser rendering, event loop, HTML, CSS, JavaScript core language, browser APIs, TypeScript, frameworks/libraries, routing, state, data fetching, forms, Node and tooling, testing, accessibility, performance, SEO and metadata, security, compatibility and progressive enhancement, i18n, design and UX, backend and authentication integration, other languages/formats, deployment/hosting/monitoring, career resources, common gotchas, glossary, and learning roadmap.

## Source Note
Use the user-provided guide as the structural basis for broad frontend answers. For exact syntax, browser support, and current library behavior, prefer MDN, web.dev, and official library documentation over memory.

## How to Answer Broad Guide Questions
1. Identify the request area from the covered list.
2. Answer with the guide's structure first, then refine with current official guidance.
3. Separate standards language, widely supported browser behavior, and experimental behavior.
4. Include verification steps, not just definitions.
## Execution Workflow
1. Identify the concern category: fundamentals, markup, styling, scripting, APIs, frameworks, data fetching, tooling, testing, accessibility, performance, SEO, security, compatibility, i18n, design, backend integration, deployment, or gotchas.
2. Load relevant `references/complete-front-end-developer-guide.md` sections rather than stuffing all of them into context.
3. Cross-check browser, syntax, and compatibility guidance with MDN, web.dev, and official library docs when they may have changed.
4. Separate guaranteed standards behavior, widely supported behavior, and emerging behavior.
5. Return a practical answer with implementation, verification, accessibility, and performance implications.
6. Include refactor and migration guidance when the change affects existing production code.

## Output Contract
- Match depth to the question: concise for definitions, comprehensive for architecture or implementation.
- Name the relevant browsers, standards, APIs, tools, or headers involved.
- Flag version-sensitive or experimental features and recommend feature detection or polyfills.
- Include accessibility, keyboard, screen-reader, and motion preferences where relevant.
- Include Core Web Vitals or measurement guidance for performance-sensitive changes.
- Include security, CSP, CORS, cookie, and input-validation implications where appropriate.
- Include maintenance, refactoring, and debug notes when asked.

## Verification Checklist
- The answer identifies which guide areas were consulted.
- Information is current; evolving browser, spec, and library guidance was verified when necessary.
- Experimental or browser-specific behavior is marked accordingly.
- Accessibility is not omitted even for "visual" or "performance" discussions.
- Performance advice focuses on transform/opacity compositing, avoidable layout, network, and render work where possible.
- Security advice covers injection, disclosure, transport, and permission risks.
- Output distinguishes required semantic structure from styling-only advice.

## Common Pitfalls
- Confusing visual styling with semantic structure.
- Copying tiny compatibility notes without checking current support.
- Overlooking mobile latency, keyboard interaction, and screen-reader behavior.
- Treating framework convenience as a substitute for platform understanding.
- Assuming cache or network guarantees from one anecdotal result.
- Mixing progressive-enhancement failures with product bugs.

## Edge Cases
- If a feature is browser-specific, provide a support decision and fallback path.
- If the user needs current official documentation, say so and point to MDN or library docs explicitly.
- If multiple guide topics overlap, load only the most relevant sections and avoid dumping the entire guide.
- If the request is narrow, defer to the appropriate specialized skill.
- If modern experimental CSS or browser APIs are requested, label them and test in the target browser matrix.

## Example
User request: "Explain why `vh` behaves poorly on mobile and what to use instead." Return: `dvh`/`svh`/`lvh` explanation, safe-area considerations, fallback, and responsive test steps. Reference the guide's viewport section rather than the whole document.

## Trigger Test Cases
- Should fire: "Use the complete frontend developer guide for mobile layout gotchas."
- Should fire: "How does the browser rendering pipeline work and where do LCP issues come from?"
- Should fire: "Give a broad frontend architecture checklist for a dashboard."
- Should not fire: "Fix this exact CSS overflow bug." (Use `css` instead.)
- Should not fire: "Generate SQL for migration scripts." (Use `sql` and backend-only guidance instead.)
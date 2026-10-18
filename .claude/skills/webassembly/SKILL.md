---
name: webassembly
description: Use for Wasm module design, JS/Wasm boundaries, performance optimization, and native ports. Triggers on 'WebAssembly', 'Wasm', 'wasm-bindgen', 'Emscripten', 'binary module'. Do NOT use for ordinary DOM UI logic or optimization work that lacks measured performance targets.
---

# WebAssembly Skill

## Purpose
Apply WebAssembly only where measurable performance or capability gains justify complexity, with safe integration.

## When to Use
- Optimize compute-heavy workflows
- Port native code to browser
- Review memory and load tradeoffs
- Design JavaScript and WASM boundaries
- Evaluate SIMD, threads, or streaming compilation

## Do Not Use
- Ordinary DOM UI logic
- Premature optimization without measurements
- Anything solvable with standard JavaScript at target latency

## Expert Concepts
- Wasm module format, sections, imports, exports
- Memory, tables, globals, and linear memory model
- JS interop and boundary marshalling
- Streaming compilation and caching
- Threads, SIMD, exceptions, and proposal support
- Security model and CSP wasm-unsafe-eval considerations

## Best Practices
- Establish a measured performance target first
- Keep the Wasm boundary coarse to reduce marshalling cost
- Use typed arrays and documented memory layout
- Stream and cache compiled modules
- Provide a JavaScript fallback where cost allows
- Review bundle, download, and cold-start impact

## Execution Workflow
1. Define measurable problem and baseline
2. Choose language and binding tool
3. Design memory and API boundary
4. Implement and profile across browsers
5. Evaluate fallback and progressive enhancement
6. Document support matrix and risks

## Verification Checklist
- Module bytes and start-up timing are measured
- No memory leak grows unbounded over usage
- Fallback works where Wasm fails to load
- Module invocation stays off main-thread tasks where useful
- Security headers and CSP constraints are documented
- Generated glue code is reviewed

## Common Pitfalls
- Using Wasm for small or already-fast code
- Excessive boundary churn
- Linear memory safety mistakes
- Large download negating performance
- CSP incompatibilities
- Debugging difficulty in optimized builds

## Tooling and Review
- MDN WebAssembly, wasm-pack, Emscripten, browser profiling, Lighthouse

## Example
```
const response = await fetch('/wasm/image-processor.wasm');
const { instance } = await WebAssembly.instantiateStreaming(response, { env: {} });
const result = instance.exports.process_image(width, height, quality);
```
## Edge Cases
- Threads and SIMD require cross-origin isolation or feature gating
- WASM output may bloat app bundle if shared across routes
- Server-rendering of Wasm-dependent logic needs fallback planning
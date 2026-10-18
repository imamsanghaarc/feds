---
name: typescript
description: Use for TypeScript types, strict contracts, APIs, tsconfig, and migrations. Triggers on 'TypeScript', 'TS', 'interface', 'generic', 'type error', 'strict mode', 'tsx types'. Do NOT use as a validator of runtime data, a framework template syntax skill, or a substitute for tests.
---

# TypeScript Skill

## Purpose
Model UI and data contracts precisely while keeping runtime behavior explicit and safe.

## When to Use
- Define component props and API types
- Migrate JavaScript to TypeScript
- Debug type errors
- Design strict shared packages
- Author declaration files

## Do Not Use
- Runtime JSON validation (combine with JSON/schema skill)
- Framework template syntax
- CSS implementation

## Expert Concepts
- Structural typing, branded types, discriminated unions
- Strict compiler options and null-state tracking
- Generics, inference, variance
- Type-only imports and erasable syntax
- Declaration emit and package exports
- External boundary validation

## Best Practices
- Enable strict mode and noUncheckedIndexedAccess when feasible
- Prefer unknown over any at boundaries
- Model runtime states with discriminated unions
- Use type-only imports for erasable module code
- Keep declarations as public API contracts
- Validate external values at runtime
- Migrate incrementally by module

## Execution Workflow
1. Define true states and allowed operations
2. Add internal and public types
3. Handle null and edge states
4. Add runtime validation at boundaries
5. Run tsc and targeted tests
6. Document breaking changes

## Verification Checklist
- No implicit any on public boundaries
- No undocumented non-null assertions
- No unchecked array or record access in critical logic
- Declarations match public intent
- External data has runtime schema
- Build remains free of tsc errors

## Common Pitfalls
- Treating types as runtime safety
- Overly complex inference and unreadable errors
- CommonJS/ESM declaration mismatches
- Mutable assertions hiding invariants
- Global namespace collisions
- Breaking APIs without changelog

## Tooling and Review
- TypeScript handbook, typescript-eslint, tsc, API Extractor, tsd, Vitest

## Example
```
type Status = 'draft' | 'published' | 'archived';

interface ComponentProps {
  readonly id: string;
  readonly status: Status;
  readonly onSave: (title: string) => Promise<void>;
}

export function publish(props: ComponentProps): ComponentProps {
  if (props.status !== 'draft') throw new Error('Invariant failed.');
  return { ...props, status: 'published' };
}
```
## Edge Cases
- Runtime data may require tagged schema validation
- tsc setting changes can alter inferred public APIs
- JavaScript interop may require declaration shimming
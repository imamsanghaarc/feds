---
name: graphql
description: Use for GraphQL operations, schema fields, variables, and pagination. Triggers on 'GraphQL', 'query', 'mutation', 'fragment', 'SDL', 'schema', 'resolver'. Do NOT use as a general REST API design, backend service invention, or unchecked broad-data fetching skill.
---

# GraphQL Skill

## Purpose
Use GraphQL deliberately with safe operation boundaries, predictable schema evolution, and performance awareness.

## When to Use
- Author GraphQL operations in frontend clients
- Design or review schema and fragments
- Manage pagination and variables
- Review complexity and denial controls
- Debug caching or type alignment

## Do Not Use
- N+1-prone resolver designs without backend coordination
- Sending broad operations to production
- Security review that substitutes operation names for authorization

## Expert Concepts
- Schema, operations, variables, fragments
- Queries, mutations, subscriptions
- Connections and cursor pagination
- Field selection, aliases, directives
- Generated types and type safety
- Errors, validation, and persisted queries

## Best Practices
- Request only required fields
- Use fragments with explicit ownership
- Set depth and complexity controls
- Normalize and update caches predictably
- Validate variables at runtime and type levels
- Prefer persisted operations in production

## Execution Workflow
1. Define data need and access level
2. Select operation shape and variables
3. Add pagination and filter inputs
4. Review cache impact and normalization
5. Validate complexity and rate constraints
6. Test queries against representative datasets

## Verification Checklist
- No unbounded recursive or nested operations
- Variables have input schemas
- Persisted operation IDs verified in production
- Cache updates avoid stale data
- Error telemetry preserves useful messages
- Authorization is not inferred from operation existence

## Common Pitfalls
- Overfetching through nested selection
- Complexity limits too weak
- Fragment sprawl
- Client cache staleness
- Mass mutations without confirmation or idempotency
- Server resolver coupling

## Tooling and Review
- GraphQL schema linting, generated types, operation documents, Lighthouse network review

## Example
```
query TaskSummary($id: ID!) {
  task(id: $id) {
    id
    title
    status
    owner {
      id
      name
    }
  }
}
```
## Edge Cases
- Backend batching and caching behavior may be opaque
- Client-generated types can drift from schema version
- Persisted query service differs by provider
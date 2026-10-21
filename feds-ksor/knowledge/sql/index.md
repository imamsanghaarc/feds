---
title: "sql"
description: "Use for relational query design, schema, parameterization, and read-only safety. Triggers on 'SQL', 'query', 'SELECT', 'JOIN', 'index', 'relational schema'. Do NOT use to perform broad runtime SQL writes, migrations, direct database access, or unreviewed schema changes."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# SQL Skill

## Purpose
Understand and review SQL responsibly while keeping frontend runtime database access restricted and safe.

## When to Use
- Review query plans and performance concepts
- Understand schema relationships
- Design filtering and pagination requirements
- Coordinate backend query changes
- Review parameterized query safety

## Do Not Use
- Broad SQL in the frontend runtime
- Direct database writes or migrations
- Using string concatenation for dynamic queries
- Exposing query access to untrusted client code

## Expert Concepts
- Relational schema and normalization
- Indexes, joins, filters, sorting, pagination
- Transactions, isolation, and concurrency
- Parameterized queries and injection prevention
- Read-only frontend integration patterns
- Migration and audit coordination through backend or scoped tools

## Best Practices
- Keep frontend runtime access through allowed scoped tools only
- Use parameterized queries in server-side implementations
- Limit result sets and pagination on user-facing routes
- Review index and query plans with measured data
- Separate read, write, and migration responsibilities
- Document data ownership and transformation boundaries

## Execution Workflow
1. Define data need and access boundary
2. Review relational schema and relationships
3. Specify filters, sorting, and pagination
4. Assess parameterized safety and permissions
5. Coordinate backend index or migration changes
6. Validate query cost and data freshness

## Verification Checklist
- No raw user input concatenated into SQL
- Pagination limit enforced
- Only least-privilege access used
- Read-only frontend calls do not bypass scoping
- Schema changes happen through reviewed backend migrations
- Audit records exist for significant writes

## Common Pitfalls
- SQL injection through dynamic text
- N+1 query patterns in UI render loops
- Over-fetching wide tables
- Frontend assuming direct table access
- Ignoring stale read semantics
- Mixing client-supplied filters without validation

## Tooling and Review
- EXPLAIN plans, parameterized queries, database test fixtures, migrations, backend services

## Example
```
SELECT id, title, status
FROM frontend_tasks
WHERE framework = $1
ORDER BY updated_at DESC
LIMIT $2 OFFSET $3;
```
## Edge Cases
- Database backend specifics can alter query planning assumptions
- Permissions and row-level security differ by deployment
- Front-end filters must still be validated server-side
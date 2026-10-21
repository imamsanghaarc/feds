---
title: "json"
description: "Use for JSON schemas, payloads, configuration, serialization, and validation. Triggers on 'JSON', 'payload', 'schema', 'config file', 'response body', 'serialization'. Do NOT use for JSON5-only features, YAML/TOML config, GraphQL operations, Protobuf schema, or SQL queries."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# JSON Skill

## Purpose
Treat JSON as a strict transport contract and preserve reliability across clients and services.

## When to Use
- Define API request and response payloads
- Create configuration files
- Validate JSON data
- Design schema evolution
- Debug serialization issues

## Do Not Use
- JSON5-only features such as comments
- YAML or TOML configuration
- GraphQL operations or Protobuf schema

## Expert Concepts
- RFC 8259 grammar, UTF-8, double-quoted strings, no comments
- Numbers, booleans, null, arrays, objects
- Duplicate-key and parser differences
- Schema versioning and contract evolution
- Number range, precision, and ordering realities
- Streaming or chunked transport considerations

## Best Practices
- Validate external JSON with a named schema before use
- Use stable fields and documented optionality
- Represent absence consistently (null versus missing)
- Version contracts and preserve compatibility
- Set size, depth, and parsing limits
- Sanitize user data before rendering

## Execution Workflow
1. Define sender and receiver needs
2. Select schema version and fields
3. Add required and nullable semantics
4. Write round-trip tests
5. Validate parsing and performance
6. Document breaking and non-breaking changes

## Verification Checklist
- No comments or trailing commas in conventional JSON
- Duplicate keys have a defined policy
- Schema accepts only documented values
- Undefined is consistently omitted or explicit null
- Number values fit target consumer limits
- Encoding remains UTF-8

## Common Pitfalls
- Parser differences for duplicate keys
- Large integer precision loss
- PII in logs
- NaN or Infinity leaks from JavaScript
- Unbounded payload memory pressure
- Client/server schema drift

## Tooling and Review
- JSON Schema, AJV, Zod or Valibot, jq, OpenAPI generators

## Example
```
{
  "component": "navigation-bar",
  "framework": "react",
  "status": "published",
  "wcag": {
    "level": "AA",
    "checked": ["keyboard", "contrast", "focus-order"]
  }
}
```
## Edge Cases
- Very large IDs may need strings rather than numeric JSON
- OpenAPI round-tripping can rename or omit fields
- Multibyte validation requires UTF-8 normalization
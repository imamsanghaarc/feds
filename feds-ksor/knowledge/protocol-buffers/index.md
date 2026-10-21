---
title: "protocol-buffers"
description: "Use for protobuf schemas, messages, field numbering, and compatibility. Triggers on 'Protocol Buffers', 'Protobuf', '.proto', 'protobufjs', 'message'. Do NOT use for human-readable APIs where transparency is more important than binary contracts."
owner: "feds-team"
audience: ["public"]
status: "draft"
sources: []
freshness: "2026-10-21"
lifecycle: "active"
tags: ["feds", "skill", "frontend"]
version: "1.0.0"
---

# Protocol Buffers Skill

## Purpose
Design version-safe binary contracts with explicit schema evolution and generated code hygiene.

## When to Use
- Author .proto definitions
- Review backward and forward compatibility
- Generate typed clients and servers
- Debug binary serialization
- Migrate schema fields

## Do Not Use
- Human-first documentation without binary needs
- Hand-edit generated code
- Using serialization as authorization or integrity alone

## Expert Concepts
- Message, field numbers, scalar and message types
- Reserved fields and reserved numbers
- Backward and forward compatibility
- Oneof, repeated, map, enums
- Package imports and naming
- Generated code and wire format

## Best Practices
- Reserve removed field numbers and names
- Use field numbers with long-term planning
- Avoid changing field types incompatibly
- Deprecate with compatibility windows
- Test generated code in both old and new clients
- Keep default values explicit in semantics

## Execution Workflow
1. Define contract and participants
2. Design message fields and numbering
3. Check compatibility with existing releases
4. Generate and lint code
5. Test serialization round trips
6. Document rollout and retention

## Verification Checklist
- Removed fields are reserved
- Required numeric semantics documented
- Oneof handling tested
- Generated clients compile against schema changes
- Size and performance budget considered
- Rollback compatibility validated

## Common Pitfalls
- Reusing field numbers
- Incompatible type changes
- Enum default issues
- Excessive nesting
- Generated code drift
- Assuming JSON and protobuf parity without checks

## Tooling and Review
- buf, protoc, protobuf compiler plugins, compatibility checks, generated-code tests

## Example
```
syntax = "proto3";
package frontend;

message Task {
  string id = 1;
  string title = 2;
  Status status = 3;
  reserved 4, 5;
  reserved "legacy_owner";
}

enum Status {
  STATUS_UNSPECIFIED = 0;
  STATUS_DRAFT = 1;
  STATUS_PUBLISHED = 2;
}
```
## Edge Cases
- Proto namespaces and generated package paths can conflict
- Runtime parsing behavior differs by language implementation
- Binary migration needs staged deploy review
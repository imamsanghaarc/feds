---
name: toml
description: Use for TOML config, tables, arrays, and tool manifests. Triggers on 'TOML', '.toml', 'Cargo.toml', 'pyproject.toml', 'TOML config'. Do NOT use when rich hierarchical documents are clearer in JSON or YAML, or for dynamic logic.
---

# TOML Skill

## Purpose
Create deterministic, unambiguous tool configuration with correct TOML table, array, and key representation.

## When to Use
- Author pyproject.toml or tool config
- Configure Cargo-like manifests
- Review dependency and task definitions
- Migrate ambiguous config
- Debug TOML parse behavior

## Do Not Use
- Application runtime logic
- Content formats with rich nesting better served elsewhere
- Dynamic code execution patterns

## Expert Concepts
- Tables, arrays, array of tables
- Keys, strings, integers, floats, booleans
- Strict typing and date/time values
- Version differences between TOML 1.0/1.1
- Tool-specific schema conventions
- Dependency and feature representation

## Best Practices
- Follow the consuming tool schema and version expectations
- Use quoted keys only when needed
- Keep tables organized by subsystem
- Avoid unnecessary deep nesting
- Validate in CI and lockfiles
- Quote strings that may be interpreted by custom tools

## Execution Workflow
1. Identify tool and schema requirement
2. Author tables and arrays clearly
3. Validate with native parser
4. Review effective normalized configuration
5. Test across CI and local
6. Document migration and known defaults

## Verification Checklist
- Parser uses expected TOML spec version
- Dependency entries resolve correctly
- Arrays remain consistently typed
- Duplicate tables are absent
- Task or feature names align with scripts
- Secrets are not committed through values

## Common Pitfalls
- TOML version mismatch
- Array-of-tables mistakes
- Ambiguity in inline versus standard tables
- Overlong flat key chains
- Tool extension variations
- Whitespace and multiline string mistakes

## Tooling and Review
- tomllib or native parser, plugged/toml tools, schema validators, tool-specific docs

## Example
```
[project]
name = "frontend-worker"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 100
target-version = "py311"

```
## Edge Cases
- Tool ecosystem support for newer TOML features varies
- Dependency sources may have vendor-specific tables
- Default values depend on invoking tool
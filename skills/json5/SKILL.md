---
name: json5
description: Use for JSON5 config with comments, trailing commas, and relaxed syntax. Triggers on 'JSON5', 'config with comments', 'trailing comma config', 'JSON superset'. Do NOT use when transporting data into strict JSON, YAML, TOML, or database-bound converters.
---

# JSON5 Skill

## Purpose
Make configuration approachable while keeping machine validation and downstream compatibility explicit.

## When to Use
- Author human-edited configuration
- Document sample payloads
- Migrate JSON config to flexible format
- Validate JSON5 linters
- Debug parser compatibility

## Do Not Use
- Strict JSON transport to JSON-only services
- Runtime event payloads without conversion
- Replacing YAML/TOML ecosystems arbitrarily

## Expert Concepts
- JSON5 superset versus RFC 8259
- Comments, trailing commas, keys, escaping
- Numbers and quoting flexibility
- Parser interoperability
- Bundler and tooling support
- Validation and canonical export

## Best Practices
- Document which consumer accepts JSON5
- Keep transport payloads strict JSON when crossing services
- Validate structure with a schema when available
- Normalize JSON5 to JSON before storage or APIs
- Avoid surprising nonstandard number syntax unless supported
- Review linter and formatter behavior

## Execution Workflow
1. Define configuration owner and consumer
2. Choose JSON5 versus related formats
3. Author and document relaxations
4. Validate syntax and schema
5. Normalize to JSON for transport
6. Test parser compatibility

## Verification Checklist
- Target tools parse the file natively
- Canonical exports remain valid JSON
- Comments explain non-obvious options
- Trailing commas do not break downstream parsers
- Schema reflects all allowed fields
- Config versioning documented

## Common Pitfalls
- JSON5 in JSON-only consumers
- Assuming every parser handles every feature
- Loss of formatting context in canonical export
- Inconsistent comment conventions
- Mixed policy for key quoting
- Security-sensitive values in example configs

## Tooling and Review
- JSON5 parser, JSON Schema after normalization, linting configs, tests

## Example
```
// Development-friendly config.
{
  legacy: false,
  features: [
    "beta-search", // enabling this changes ranking globally
    "new-layout",
  ],
  threshold: 0.75,
}
```
## Edge Cases
- Tooling lineage differs and minification compatibility matters
- Some platforms reject comments despite relaxed syntax
- Normalization step must be deterministic
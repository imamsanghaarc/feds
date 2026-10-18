---
name: yaml
description: Use for YAML config, manifests, CI files, anchors, and safe parsing. Triggers on 'YAML', '.yml', 'YAML config', 'manifest', 'pipeline', 'front matter'. Do NOT use for arbitrary code execution, executable logic, or transport without schema and parser validation.
---

# YAML Skill

## Purpose
Write clear, safe, interoperable YAML while avoiding parser ambiguity and implicit type surprises.

## When to Use
- Edit configuration files and manifests
- Build CI/CD pipelines in YAML
- Write document front matter
- Review Hydra/Kubernetes-style config
- Debug parse or type behavior

## Do Not Use
- Arbitrary code execution via unsafe loaders
- API transport without normalization
-  Complex templating language replacement

## Expert Concepts
- YAML specification versions
- Scalars, mappings, sequences
- Anchors, aliases, merge keys
- Implicit typing such as Norway problem
- Safe versus unsafe loaders
- Server-side include and template integration

## Best Practices
- Quote ambiguity-prone scalars such as yes/no/on/off and versions
- Use safe parsers only
- Keep anchors understandable and shallow
- Validate schema and required keys
- Prefer explicit types or quoted values when parser inference matters
- Format consistently and inspect diff output

## Execution Workflow
1. Define configuration purpose and owner
2. Choose safe parser and schema tool
3. Author with clear quoting
4. Validate syntax and schema
5. Test in target environment
6. Document migration and roll-out

## Verification Checklist
- No unexpected boolean or null inference
- Anchors resolve without circular or surprising merges
- Schema matches declared version
- Safe parser prevents code execution
- CI validates file before merge
- Secrets are not embedded directly

## Common Pitfalls
- Unsafe deserialization
- Implicit type coercion
- Anchor complexity
- Multi-document and separator confusion
- Line-length or tabs issues
- Whitespace-sensitive bugs

## Tooling and Review
- yamllint, JSON Schema, language-specific safe loaders, deployment validators

## Example
```
team:
  name: "platform"
  enabled: true
  labels: ["alpha", "frontend"]
  threshold: "0.75"  # quoted to avoid parser-specific numeric behavior

```
## Edge Cases
- YAML 1.1 and 1.2 differ in important scalar inference cases
- Kubernetes-style consumers may transform merge keys
- Templating overlays can alter rendered configuration
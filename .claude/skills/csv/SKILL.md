---
name: csv
description: Use for CSV parsing, quoting, delimiters, encoding, and tabular cleanup. Triggers on 'CSV', 'comma-separated values', 'tabular import', 'CSV quoting', 'CSV transform'. Do NOT use when a typed schema or API format should be used for transport or code generation.
---

# CSV Skill

## Purpose
Treat CSV as a constrained interoperability format and preserve field, quoting, encoding, and semantic integrity.

## When to Use
- Import or export tabular data
- Review dialect and parser behavior
- Validate square and typed fields
- Transform CSV for frontend or backend
- Debug quoting and encoding issues

## Do Not Use
- API contracts where explicit schema is better
- Treating CSV as a database
- Opening untrusted files without isolation

## Expert Concepts
- RFC 4180 and dialect differences
- Header, records, columns
- Quoting, escaping, line endings
- Encoding and BOM handling
- Field typing and null representation
- Streaming and memory constraints

## Best Practices
- Document expected dialect and delimiter
- Use a CSV library rather than string splitting
- Quote fields containing delimiters or newlines
- Normalize encoding and document it
- Validate row counts and required columns
- Stream large files instead of reading whole input

## Execution Workflow
1. Define source and schema
2. Inspect dialect, encoding, delimiter, line endings
3. Parse with appropriate library
4. Validate rows and types
5. Transform and emit with consistent quoting
6. Test round trip and error rows

## Verification Checklist
- No unquoted multiline or delimiter fields
- Row and column counts monitored
- Encoding and BOM normalized
- Invalid rows isolated rather than silently ignored
- Dates and numbers use agreed representation
- Output conforms to consumer expectation

## Common Pitfalls
- Field splitting on embedded commas
- Encoding mojibake
- BOM creating invalid header names
- Silent column shifting
- Mixed line endings
- Treating empty strings as null inconsistently

## Tooling and Review
- CSV parsers for target language, csvkit, schema validators, encoding checkers

## Example
```
name,framework,status,notes
"Navigation Bar",react,published,"Handles keyboard, focus, and screen-reader behavior"
"Settings Form",angular,draft,"Needs contrast and live-region review"

```
## Edge Cases
- Government or spreadsheet-generated CSV can contain nonstandard dialects
- Large files can exhaust client memory
- Locale-dependent decimal separators need explicit normalization
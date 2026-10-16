---
name: stylus
description: Use for Stylus mixins, variables, and flexible CSS compilation. Triggers on 'Stylus', '.styl', 'styl', 'composable mixin', 'Stylus compiler'. Do NOT use for greenfield styling where maintainability, hiring, support, and toolchain maturity matter most.
---

# Stylus Skill

## Purpose
Maintain Stylus only with explicit readability, syntax, and migration controls.

## When to Use
- Maintain legacy .styl files
- Review optional braces and colons
- Evaluate Stylus dependency risks
- Migrate to CSS or another preprocessor
- Debug compiled output

## Do Not Use
- Greenfield standardization without support evaluation
- Markup or behavior unrelated to styles

## Expert Concepts
- Indentation-based optional CSS syntax
- Variables, interpolation, mixins
- Functions and instance methods
- Conditionals and iteration
- Imports and namespacing
- Compiler versions and output

## Best Practices
- Establish required braces and colon policy
- Pin compiler and Node tool version
- Keep mixins documented and side-effect free
- Avoid optional syntax in shared critical files
- Audit compiled CSS
- Plan migration to standard or better-supported tooling

## Execution Workflow
1. Inventory Stylus surface
2. Standardize required syntax
3. Compile with pinned tooling
4. Refactor risky modules
5. Inspect generated CSS
6. Add CI reproducibility

## Verification Checklist
- No mixed invisible syntax conventions
- Compiler version documented
- Generated output matches baseline
- Build reproducible in clean environment
- Migration decision accepted or funded
- Team conventions published

## Common Pitfalls
- Optional syntax harming readability
- Version drift causing compiler failure
- Mixins hidden in global scope
- Team expertise decline
- Migration cost deferred
- Unexpected variable precedence

## Tooling and Review
- Stylus documentation, lint scripts, pinned toolchain, migration review

## Example
```
card(gap = 1rem)
  display grid
  gap gap
  padding gap

.card
  card()
```
## Edge Cases
- Stylus toolchain is smaller than Sass or native CSS options
- Implicit syntax raises review difficulty
- Migration should preserve source maps and visual output
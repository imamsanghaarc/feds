---
name: liquid
description: Use for Liquid templates, Shopify sections, filters, loops, and rendering. Triggers on 'Liquid', 'Shopify', 'filter', 'section', 'render', 'template drop'. Do NOT use as server application logic outside platform constraints or as database migration/configuration work.
---

# Liquid Skill

## Purpose
Build merchant-safe, accessible, performant Liquid templates with strict output and asset assumptions.

## When to Use
- Shopify theme or Liquid rendering work
- Build reusable sections and blocks
- Optimize filter-heavy templates
- Review theme data boundaries
- Debug render and URL output

## Do Not Use
- Server application logic outside platform constraints
- Security boundaries handled only in client code
- Low-level database writes

## Expert Concepts
- Objects, drops, filters, tags
- Render and include semantics
- Section and block lifecycle
- Rendering cost and caching
- Asset and responsive image handling
- HTML escaping and output safety

## Best Practices
- Escape output and avoid unreviewed raw output
- Limit nested render and filter chains
- Cache stable snippets where allowed
- Represent loading and empty states
- Use responsive image variants
- Document shop, locale, and market assumptions

## Execution Workflow
1. Define template scope and available data
2. Build section and block contracts
3. Review filter performance
4. Render with representative store data
5. Validate accessibility and performance
6. Audit escaping and assets

## Verification Checklist
- No unescaped untrusted output
- Sections render with documented settings
- Performance acceptable on key pages
- Image dimensions prevent CLS
- Missing data has fallback UI
- Dependencies are documented

## Common Pitfalls
- Filter chain overhead
- Platform data shape drift
- Theme assumptions fragility
- Complex nested block schemas
- Market or locale URL mistakes
- Raw output XSS risk

## Tooling and Review
- Liquid docs, theme inspector, Lighthouse, theme check

## Example
```
{% if collections.featured.products.size > 0 %}
<section aria-labelledby="featured-heading">
  <h2 id="featured-heading">Featured</h2>
  {% for product in collections.featured.products %}
    <article>{{ product.title | escape }}</article>
  {% endfor %}
</section>
{% endif %}
```
## Edge Cases
- Platform changes can alter available objects
- Merchant data may include unexpected HTML
- Heavy block schemas impact authoring workflow
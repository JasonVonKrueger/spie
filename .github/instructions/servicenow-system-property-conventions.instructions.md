---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow system properties or property-driven configuration; enforce property naming, stability, and value conventions."
---
# ServiceNow System Property Conventions

- Name properties with a reverse-domain or product-prefixed pattern like `<company>.<product>.<area>.<setting>`.
- Use lowercase names with dots as separators.
- Keep property names stable once published.
- Store boolean values as `true` or `false`.
- Use short, clear values and document expected types.
- Group related properties by prefix.
- Avoid using properties as a substitute for good design.

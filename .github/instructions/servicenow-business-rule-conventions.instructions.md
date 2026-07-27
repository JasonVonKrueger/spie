---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow Business Rules or helpers that create them; enforce naming, trigger choice, recursion safety, and delegation patterns."
---
# ServiceNow Business Rule Conventions

- Name Business Rules with the pattern `<Table> - <Trigger or Outcome> - <Short Purpose>`.
- Prefer before rules for validation and field defaults.
- Use after rules for integration or downstream side effects.
- Avoid recursive updates.
- Keep script logic short and delegate reusable logic to Script Includes when possible.

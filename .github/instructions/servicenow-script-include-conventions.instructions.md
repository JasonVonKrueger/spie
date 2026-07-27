---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow Script Includes or helpers that create them; enforce naming, reuse, method design, and client-callable discipline."
---
# ServiceNow Script Include Conventions

- Use Script Include names that describe the helper or service purpose.
- Prefer CompanyPrefixFeatureHelper, CompanyPrefixFeatureService, or CompanyPrefixFeatureValidator naming patterns.
- Put reusable logic in Script Includes instead of repeating it in Business Rules or UI Actions.
- Keep methods focused and single-purpose.
- Prefer server-side validation and business logic in Script Includes.
- Mark Script Includes as client callable only when client-side access is required.
- Add comments only where logic is non-obvious.

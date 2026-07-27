---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow update sets or update-set tooling; enforce update-set naming, scope, review, and promotion conventions."
---
# ServiceNow Update Set Conventions

- Name update sets with the pattern `<APP or DOMAIN> - <SHORT PURPOSE> - <ENV or TICKET>`.
- Keep update sets small and scoped to one change theme.
- Do not mix unrelated work in the same update set.
- Add a clear description before marking an update set complete.
- Always review preview errors before promotion.
- Close or clone update sets only after validation is complete.
- Use a dedicated update set for hotfixes and emergency changes.
